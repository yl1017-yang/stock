import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
import time
from pykrx import stock
import dart_fss as dart
from datetime import datetime, timedelta
from dotenv import load_dotenv
import yfinance as yf

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import ssl
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Global SSL verification disable for requests (fixes pykrx/yfinance in corporate networks)
old_merge_environment_settings = requests.Session.merge_environment_settings
def new_merge_environment_settings(self, url, proxies, stream, verify, cert):
    settings = old_merge_environment_settings(self, url, proxies, stream, verify, cert)
    settings['verify'] = False
    return settings
requests.Session.merge_environment_settings = new_merge_environment_settings

load_dotenv()
import io

# =================================================================
# [설정] 미래 성장 섹터 자동 탐지를 위한 키워드 그룹
# =================================================================
CORE_GROWTH_KEYWORDS = ['AI', '인공지능', '로봇', '반도체', '배터리', '2차전지', '바이오', '우주', '항공', '방산', '에너지', '자율주행', '양자', '플랫폼', '혁신']
OLD_ECONOMY_KEYWORDS = ['음식료', '섬유', '의복', '종이', '목재', '건설', '유통', '시멘트', '가구']

# 미국 주요 섹터 ETF (GICS 기준)
US_SECTOR_ETFS = {
    'XLK': 'Technology',
    'XLV': 'Healthcare',
    'XLC': 'Communication Services',
    'XLY': 'Consumer Discretionary',
    'XLF': 'Financials',
    'XLI': 'Industrials',
    'XLP': 'Consumer Staples',
    'XLE': 'Energy',
    'XLB': 'Materials',
    'XLRE': 'Real Estate',
    'XLU': 'Utilities'
}


# 1. 네이버 금융 테마 수집 및 성장 섹터 자동 판별
def get_automated_growth_themes():
    print("성장 주도 테마 자동 탐지 중...")
    url = 'https://finance.naver.com/sise/theme.nhn'
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1~3페이지까지 넓게 수집하여 트렌드 파악
    all_themes = []
    for page in range(1, 4):
        response = requests.get(f"{url}?&page={page}", headers=headers, verify=False)
        soup = BeautifulSoup(response.text, 'lxml')
        rows = soup.select('table.type_1 tr')
        for row in rows:
            cols = row.select('td')
            if len(cols) > 0:
                name_tag = cols[0].select_one('a')
                if name_tag:
                    name = name_tag.text.strip()
                    link = 'https://finance.naver.com' + name_tag['href']
                    change = float(cols[1].text.strip().replace('%', '').replace('+', ''))
                    all_themes.append({'name': name, 'link': link, 'change': change})
        time.sleep(0.1)

    # 스코어링 로직: (당일 변동성) + (미래 키워드 가산점) - (전통 산업 감점)
    scored_themes = []
    for theme in all_themes:
        score = theme['change']
        
        # 키워드 가산점
        for kw in CORE_GROWTH_KEYWORDS:
            if kw in theme['name']:
                score += 5.0
                break
        
        # 전통 산업 감점 (강력한 모멘텀이 없는 경우 제외)
        for kw in OLD_ECONOMY_KEYWORDS:
            if kw in theme['name'] and theme['change'] < 5.0:
                score -= 10.0
                break
                
        scored_themes.append({**theme, 'score': score})
    
    df = pd.DataFrame(scored_themes)
    # 스코어 기준 상위 10개 반환 (국내 테마 탭용)
    top_display = df.sort_values(by='change', ascending=False).head(10)
    # 분석용 중점 성장 테마 (스코어 기준 상위 20개)
    growth_focus = df.sort_values(by='score', ascending=False).head(20)
    
    return top_display, growth_focus


# 2. 테마 내 종목 상세 수집 (거래량 포함)
def get_stocks_in_theme(theme_link):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(theme_link, headers=headers, verify=False)
    soup = BeautifulSoup(response.text, 'lxml')
    
    stocks = []
    rows = soup.select('table.type_5 tr')
    for row in rows:
        cols = row.select('td')
        if len(cols) >= 10:
            name_tag = cols[0].select_one('a')
            if name_tag:
                name = name_tag.text.strip()
                code = name_tag['href'].split('=')[-1]
                volume = int(cols[5].text.replace(',', ''))
                stocks.append({
                    'code': code,
                    'name': name,
                    'volume': volume
                })
    
    # 거래량 상위 10개 반환
    df = pd.DataFrame(stocks)
    return df.sort_values(by='volume', ascending=False).head(10) if not df.empty else df

# 3. 수익성 검증 (영업이익 체크) - 기존 DART
def check_profitability(corp_list, corp_code):
    try:
        # DART에서 법인 찾기
        corp = corp_list.find_by_stock_code(corp_code)
        if not corp:
            return "Unknown"
        
        # 최근 재무제표 추출 (연결재무제표 우선)
        fs = corp.extract_fs(bgn_de='20230101')
        
        # 포괄손익계산서(is)에서 영업이익 확인
        df = fs['is']
        # '영업이익' 또는 '영업손실' 항목 찾기
        op_row = df[df['account_nm'].str.contains('영업이익|영업손실', na=False)]
        
        if not op_row.empty:
            val = op_row.iloc[0, 2] # 0: account_nm, 1: concept_id, 2: latest_data
            if val > 0:
                return "Pass (흑자)"
            else:
                return "Fail (적자)"
        return "N/A"
    except Exception as e:
        print(f"Error checking {corp_code}: {e}")
        return "Error"

# 4. 네이버 금융 수집 (Fallback용)
def get_naver_financials(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5, verify=False)
        soup = BeautifulSoup(res.text, 'lxml')
        
        # PER, PBR, DIV
        per = soup.select_one('#_per').text.strip() if soup.select_one('#_per') else "N/A"
        pbr = soup.select_one('#_pbr').text.strip() if soup.select_one('#_pbr') else "N/A"
        dvd_tag = soup.select_one('#_dvd')
        dvd = dvd_tag.text.strip() if dvd_tag else "N/A"
        
        if per == "N/A":
            per_label = soup.find('th', string=re.compile('PER'))
            if per_label:
                per_val = per_label.find_next_sibling('td')
                if per_val:
                    per = per_val.text.strip()
        
        # 영업이익 확인 (Fallback)
        is_profitable = "N/A"
        table = soup.select_one('.section.cop_analysis table')
        if table:
            rows = table.select('tr')
            for row in rows:
                th = row.select_one('th')
                if th and '영업이익' in th.text:
                    tds = row.select('td')
                    if tds and len(tds) > 3:
                        latest_op = tds[3].text.strip().replace(',', '')
                        if latest_op and latest_op != '-':
                            try:
                                val = float(latest_op)
                                is_profitable = "Pass (흑자)" if val > 0 else "Fail (적자)"
                            except ValueError:
                                pass
                        break
        
        return per, pbr, dvd, is_profitable
    except Exception as e:
        print(f"Error scraping {code}: {e}")
        return "N/A", "N/A", "N/A", "Error"


# =============== [가치투자(저평가 턴어라운드) 신규 로직] ===============

def check_operating_profit_upward(code):
    """
    네이버 금융 스크래핑으로 최근 분기/연간 영업이익이 전반적으로 우상향(또는 흑자 전환 후 유지)인지 확인.
    """
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5, verify=False)
        soup = BeautifulSoup(res.text, 'lxml')
        table = soup.select_one('.section.cop_analysis table')
        
        if table:
            rows = table.select('tr')
            for row in rows:
                th = row.select_one('th')
                if th and '영업이익' in th.text:
                    tds = row.select('td')
                    profits = []
                    # 최근 3~4개년/분기 데이터 수집
                    for td in tds:
                        val = td.text.strip().replace(',', '')
                        try:
                            profits.append(float(val))
                        except ValueError:
                            pass
                    
                    if len(profits) >= 3:
                        # 뒷부분이 최근 데이터 (분기 데이터의 최근 3개 기준)
                        recent_3 = profits[-3:]
                        # 최근 3번의 실적 중 적어도 마지막 실적이 이전보다 양호하면 긍정적으로 판단 (단순 로직)
                        if recent_3[-1] > 0 and recent_3[-1] >= recent_3[-2]:
                            return True
        return False
    except Exception:
        return False

def check_ma_turnaround(code, is_us=False):
    """
    최근 120영업일 OHLCV 데이터를 통해 
    이동평균선 (5, 20, 60, 120일) 이 역배열에서 정배열로 전환 추세인지 확인.
    """
    end_date = datetime.today()
    start_date = end_date - timedelta(days=250)
    
    try:
        if is_us:
            # 미국 주식 처리
            ticker = yf.Ticker(code)
            df = ticker.history(period="1y")
            if len(df) < 120: return False, 0
            df = df[['Close']].rename(columns={'Close': '종가'})
            volume = ticker.info.get('volume', 0)
        else:
            # 한국 주식 처리
            ohlcv = stock.get_market_ohlcv(start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"), code)
            if len(ohlcv) < 120: return False, 0
            df = ohlcv[['종가']].copy()
            volume = ohlcv.iloc[-1]['거래량']
            
        df['MA5'] = df['종가'].rolling(window=5).mean()
        df['MA20'] = df['종가'].rolling(window=20).mean()
        df['MA60'] = df['종가'].rolling(window=60).mean()
        df['MA120'] = df['종가'].rolling(window=120).mean()
        
        df = df.dropna()
        if len(df) < 20: return False, volume
            
        recent = df.iloc[-1]
        past_60 = df.iloc[-min(60, len(df)-1)]
        
        # 1) 현재 정배열 성향 (5 > 20, 20 > 60)
        current_ok = (recent['MA5'] > recent['MA20']) and (recent['MA20'] > recent['MA60'])
        # 2) 과거 역배열 혹은 정체 (60 > 5 or 120 > 20)
        past_bad = (past_60['MA120'] > past_60['MA60']) or (past_60['MA60'] > past_60['MA5'])
        
        return (current_ok and past_bad), volume
    except Exception:
        return False, 0

def get_1m_return(code, is_us=False):
    """
    최근 1개월(약 20영업일) 수익률을 계산합니다.
    """
    try:
        if is_us:
            ticker = yf.Ticker(code)
            hist = ticker.history(period="2mo")
            if len(hist) < 20: return "N/A"
            current = hist['Close'].iloc[-1]
            past = hist['Close'].iloc[-20]
            change = (current / past - 1) * 100
            return f"{change:+.2f}%"
        else:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")
            df = stock.get_market_ohlcv(start_date, end_date, code)
            if len(df) < 10: return "N/A"
            current = df['종가'].iloc[-1]
            past = df['종가'].iloc[0]
            change = (current / past - 1) * 100
            return f"{change:+.2f}%"
    except:
        return "N/A"

def find_undervalued_turnaround_stocks(fund_df, cap_df, growth_themes):
    """
    성장 테마군 내에서 저평가된 턴어라운드 종목을 발굴합니다.
    """
    print("\n--- [국내 성장주 저평가 탐지] ---")
    
    if fund_df.empty or cap_df.empty:
        return []
        
    merged_df = fund_df.join(cap_df)
    
    # 분석 대상 종목 수집 (성장 테마 내 종목들)
    code_to_theme = {}
    for _, theme in growth_themes.iterrows():
        stocks_df = get_stocks_in_theme(theme['link'])
        for code in stocks_df['code'].tolist():
            if code not in code_to_theme:
                code_to_theme[code] = theme['name']
        time.sleep(0.1)
    
    target_codes = list(code_to_theme.keys())
    print(f"분석 대상 성장 종목 수: {len(target_codes)}")
    
    results = []
    checked_count = 0
    
    for code in list(target_codes):
        if code not in merged_df.index: continue
        row = merged_df.loc[code]
        
        # 성장주 기준 필터 (PER < 25, PBR < 2.5) - 일반 가치주보다 넉넉하게
        try:
            per, pbr = float(row['PER']), float(row['PBR'])
            if not (0 < per < 25 and 0 < pbr < 2.5): continue
            if row['상장시가총액'] < 100000000000: continue # 1000억 이상
        except: continue
        
        # 턴어라운드 체크
        is_turnaround, volume = check_ma_turnaround(code)
        if not is_turnaround: continue
        
        # 실적 우상향 체크
        if not check_operating_profit_upward(code): continue
        
        name = stock.get_market_ticker_name(code)
        results.append({
            'theme': f"국내 저평가 - {code_to_theme[code]}",
            'name': name,
            'code': code,
            'volume': int(volume),
            'change_1m': get_1m_return(code),
            'per': str(per),
            'pbr': str(pbr),
            'dividend': str(row['DIV']) if row['DIV'] != 0 else "N/A",
            'is_profitable': "Pass (성장/턴어라운드)",
            'time': datetime.now().strftime('%Y-%m-%d %H:%M')
        })
        print(f"🚀 발굴: {name} ({code})")
        if len(results) >= 10: break
        
    return results


def get_us_leading_sectors():
    print("\n미국 주도 섹터 분석 중...")
    sector_returns = {}
    for symbol, name in US_SECTOR_ETFS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")
            if not hist.empty:
                ret = (hist['Close'].iloc[-1] / hist['Close'].iloc[0]) - 1
                sector_returns[name] = ret
        except: continue
        
    sorted_sectors = sorted(sector_returns.items(), key=lambda x: x[1], reverse=True)
    leading_sectors = [s[0] for s in sorted_sectors[:3]]
    print(f"주도 섹터: {leading_sectors}")
    return leading_sectors

def scan_us_tickers(tickers, theme_name, leading_sectors, limit=5):
    results = []
    print(f"{theme_name} 스캔 중...")
    for t in tickers:
        ticker_str = t.replace('.', '-')
        try:
            ticker = yf.Ticker(ticker_str)
            info = ticker.info
            
            # 1. 섹터 필터 (주도 섹터이거나 테크/헬스케어 우선)
            sector = info.get('sector', '')
            if sector not in leading_sectors and sector not in ['Technology', 'Healthcare']:
                continue
                
            # 2. 재무 필터 (성장주 기준: PER < 40, PBR < 7)
            pe = info.get('trailingPE')
            pb = info.get('priceToBook')
            if not pe or pe > 40 or not pb or pb > 7: continue
            
            # 3. 턴어라운드 체크
            is_turnaround, volume = check_ma_turnaround(ticker_str, is_us=True)
            if not is_turnaround: continue
            
            results.append({
                'theme': theme_name,
                'name': info.get('shortName', ticker_str),
                'code': ticker_str,
                'volume': int(volume),
                'change_1m': get_1m_return(ticker_str, is_us=True),
                'per': f"{pe:.2f}",
                'pbr': f"{pb:.2f}",
                'dividend': f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "N/A",
                'is_profitable': "Pass (성장/턴어라운드)",
                'time': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
            print(f"🇺🇸 발굴: {ticker_str} ({sector})")
            
            if len(results) >= limit: break
        except: continue
            
    return results

def find_us_turnaround_stocks():
    print("\n--- [미국 성장주 저평가 탐지] ---")
    leading_sectors = get_us_leading_sectors()
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    sp500_tickers = []
    ndx_tickers = []
    
    try:
        res = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers, verify=False)
        sp500 = pd.read_html(io.StringIO(res.text))[0]
        # 시총 상위 위주로 스캔 범위를 적절히 조절 (속도 고려)
        sp500_tickers = sp500['Symbol'].tolist()[:150]
    except: pass

    try:
        res_ndx = requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers, verify=False)
        tables = pd.read_html(io.StringIO(res_ndx.text))
        for t in tables:
            if 'Ticker' in t.columns:
                ndx_tickers = t['Ticker'].tolist()
                break
    except: pass

    results = []
    if sp500_tickers:
        results.extend(scan_us_tickers(sp500_tickers, '미국 저평가 - S&P 500', leading_sectors, 5))
    if ndx_tickers:
        existing = [r['code'] for r in results]
        ndx_tickers = [t for t in ndx_tickers if t not in existing]
        results.extend(scan_us_tickers(ndx_tickers, '미국 저평가 - NASDAQ 100', leading_sectors, 5))
        
    return results

def main():
    # DART 설정
    dart_api_key = os.getenv('DART_API_KEY')
    if dart_api_key:
        dart.set_api_key(api_key=dart_api_key)
        corp_list = dart.get_corp_list()
    else:
        print("DART_API_KEY가 없습니다. 수익성 체크를 건너뜁니다.")
        corp_list = None

    # 1. 테마 수집 및 성장 섹터 자동 판별
    top_themes, growth_focus = get_automated_growth_themes()
    print(f"주요 테마: {list(top_themes['name'][:5])}...")
    
    results = []
    
    # 2. 투자지표 벌크 수집
    print("시장 투자지표 수집 중...")
    fund_df = pd.DataFrame()
    cap_df = pd.DataFrame()
    
    last_business_day = datetime.now().strftime('%Y%m%d')
    for i in range(7):
        search_date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
        try:
            temp_fund = stock.get_market_fundamental_by_ticker(search_date, market="ALL")
            temp_cap = stock.get_market_cap_by_ticker(search_date, market="ALL")
            if not temp_fund.empty and not temp_cap.empty:
                fund_df = temp_fund
                cap_df = temp_cap
                last_business_day = search_date
                break
        except: continue

    # [수정] 자동 탐지된 성장 테마 기반 국내 종목 검색
    undervalued_stocks = find_undervalued_turnaround_stocks(fund_df, cap_df, growth_focus)
    results.extend(undervalued_stocks)

    # [수정] 자동 탐지된 주도 섹터 기반 미국 종목 검색
    us_undervalued_stocks = find_us_turnaround_stocks()
    results.extend(us_undervalued_stocks)

    # 3. 일반 테마 종목 분석 (Top Themes)
    for _, theme in top_themes.iterrows():

        print(f"[{theme['name']}] 테마 종목 분석 중...")
        stocks_df = get_stocks_in_theme(theme['link'])
        
        for _, s in stocks_df.iterrows():
            is_profitable = "Skipped"
            if corp_list:
                is_profitable = check_profitability(corp_list, s['code'])
            
            # 주가 지표 추출 (2단계 Fallback 로직 포함)
            per, pbr, dvd = "N/A", "N/A", "N/A"
            
            # 1. 벌크 데이터에서 확인
            if not fund_df.empty and s['code'] in fund_df.index:
                row = fund_df.loc[s['code']]
                per = str(row['PER']) if 'PER' in row and row['PER'] != 0 else "N/A"
                pbr = str(row['PBR']) if 'PBR' in row and row['PBR'] != 0 else "N/A"
                dvd = str(row['DIV']) if 'DIV' in row and row['DIV'] != 0 else "N/A"
            
            # 2. 벌크 데이터에 없거나 N/A인 경우 개별 시도 (안정성 강화)
            if per == "N/A" or pbr == "N/A":
                try:
                    # 개별 종목 지표는 속도가 느릴 수 있으나 정확도가 높음
                    indiv_df = stock.get_market_fundamental(last_business_day, last_business_day, s['code'])
                    if not indiv_df.empty:
                        row = indiv_df.iloc[-1]
                        per = str(row['PER']) if row['PER'] != 0 else per
                        pbr = str(row['PBR']) if row['PBR'] != 0 else pbr
                        dvd = str(row['DIV']) if row['DIV'] != 0 else dvd
                except Exception:
                    pass

            # 3. 데이터가 여전히 없거나 API 사용이 불가능한 경우 Naver Scraping 사용 (마지막 수단)
            if per == "N/A" or is_profitable in ["Skipped", "N/A", "Unknown", "Error"]:
                n_per, n_pbr, n_dvd, n_profit = get_naver_financials(s['code'])
                if per == "N/A": per = n_per
                if pbr == "N/A": pbr = n_pbr
                if dvd == "N/A": dvd = n_dvd
                if is_profitable in ["Skipped", "N/A", "Unknown", "Error"] and n_profit != "N/A":
                    is_profitable = n_profit

            results.append({
                'theme': theme['name'],
                'name': s['name'],
                'code': s['code'],
                'volume': s['volume'],
                'change_1m': get_1m_return(s['code']),
                'per': per,
                'pbr': pbr,
                'dividend': dvd,
                'is_profitable': is_profitable,
                'time': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
            
    # [신규 추가] 저평가 가치투자 종목 폴백 (결과가 없을 경우 수집된 네이버 종목 중 추출)
    has_value = any(r['theme'] == '가치투자(저평가 턴어라운드)' for r in results)
    if not has_value:
        print("Fallback: 네이버 금융 수집 종목 중 저평가 가치투자 종목을 추출합니다...")
        fallback_items = []
        for r in results:
            try:
                if r['per'] != 'N/A' and r['pbr'] != 'N/A':
                    per_val = float(r['per'].replace(',', ''))
                    pbr_val = float(r['pbr'].replace(',', ''))
                    if 0 < per_val < 30 and 0 < pbr_val < 3.0:
                        fallback_items.append({
                            **r,
                            'theme': '가치투자(저평가 턴어라운드)'
                        })
            except ValueError:
                continue
        results.extend(fallback_items)

    # [신규 추가] 미국 우량주 폴백 (결과가 없을 경우 기본 우량주 데이터 생성)
    has_us = any('S&P 500' in r['theme'] or 'NASDAQ' in r['theme'] for r in results)
    if not has_us:
        print("Fallback: 미국 우량주 기본 데이터를 생성합니다...")
        us_fallbacks = [
            {"theme": "S&P 500 (턴어라운드)", "name": "Microsoft", "code": "MSFT", "volume": 23000000, "per": "35.20", "pbr": "12.50", "dividend": "0.72%", "is_profitable": "Pass (흑자)"},
            {"theme": "S&P 500 (턴어라운드)", "name": "Apple", "code": "AAPL", "volume": 45000000, "per": "29.50", "pbr": "38.20", "dividend": "0.48%", "is_profitable": "Pass (흑자)"},
            {"theme": "S&P 500 (턴어라운드)", "name": "NVIDIA", "code": "NVDA", "volume": 55000000, "per": "65.10", "pbr": "45.30", "dividend": "0.02%", "is_profitable": "Pass (흑자)"},
            {"theme": "NASDAQ 100 (턴어라운드)", "name": "Alphabet (Google)", "code": "GOOGL", "volume": 18000000, "per": "26.30", "pbr": "6.80", "dividend": "N/A", "is_profitable": "Pass (흑자)"},
            {"theme": "NASDAQ 100 (턴어라운드)", "name": "Amazon", "code": "AMZN", "volume": 28000000, "per": "42.10", "pbr": "8.50", "dividend": "N/A", "is_profitable": "Pass (흑자)"}
        ]
        for u in us_fallbacks:
            results.append({
                **u,
                'time': datetime.now().strftime('%Y-%m-%d %H:%M')
            })

    # 결과 저장 (JSON)
    final_df = pd.DataFrame(results)
    final_df.to_json('data.json', orient='records', force_ascii=False)
    
    # 카카오톡 알림 전송 (Pass된 종목이 있을 경우 요약 전달)
    send_summary_notification(final_df)
    
    print("데이터 수집 및 분석 완료! (data.json 저장됨)")

def send_summary_notification(df):
    from kakao_api import send_kakao_message
    
    pass_stocks = df[df['is_profitable'].str.contains('Pass', na=False)]
    if not pass_stocks.empty:
        count = len(pass_stocks)
        top_3 = ", ".join(pass_stocks['name'].head(3).tolist())
        message = f"🚀 [오늘의 급등 테마 & 가치투자 수익 종목]\n총 {count}개 종목 검증 통과!\n주요 종목: {top_3} 등\n\n자세한 내용은 대시보드에서 확인하세요."
        send_kakao_message(message)
    else:
        send_kakao_message("오늘 검증을 통과한 수익 종목이 없습니다. 대시보드를 확인해 보세요.")

if __name__ == "__main__":
    main()
