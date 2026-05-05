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
import io
import ssl
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# SSL context fix for some environments
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

load_dotenv()

# =================================================================
# [설정] 미래 성장 섹터 자동 탐지를 위한 키워드 그룹
# =================================================================
CORE_GROWTH_KEYWORDS = ['AI', '인공지능', '로봇', '반도체', '배터리', '2차전지', '바이오', '우주', '항공', '방산', '에너지', '자율주행', '양자', '플랫폼', '혁신']
OLD_ECONOMY_KEYWORDS = ['음식료', '섬유', '의복', '종이', '목재', '건설', '유통', '시멘트', '가구']

US_SECTOR_ETFS = {
    'XLK': 'Technology', 'XLV': 'Healthcare', 'XLC': 'Communication Services',
    'XLY': 'Consumer Discretionary', 'XLF': 'Financials', 'XLI': 'Industrials',
    'XLP': 'Consumer Staples', 'XLE': 'Energy', 'XLB': 'Materials',
    'XLRE': 'Real Estate', 'XLU': 'Utilities'
}

# 1. 네이버 금융 테마 수집 및 성장 섹터 자동 판별
def get_automated_growth_themes():
    print("성장 주도 테마 자동 탐지 중...")
    url = 'https://finance.naver.com/sise/theme.nhn'
    headers = {'User-Agent': 'Mozilla/5.0'}
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

    scored_themes = []
    for theme in all_themes:
        score = theme['change']
        for kw in CORE_GROWTH_KEYWORDS:
            if kw in theme['name']:
                score += 5.0
                break
        for kw in OLD_ECONOMY_KEYWORDS:
            if kw in theme['name'] and theme['change'] < 5.0:
                score -= 10.0
                break
        scored_themes.append({**theme, 'score': score})
    
    df = pd.DataFrame(scored_themes)
    top_display = df.sort_values(by='change', ascending=False).head(10)
    growth_focus = df.sort_values(by='score', ascending=False).head(20)
    return top_display, growth_focus

# 2. 테마 내 종목 상세 수집
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
                stocks.append({'code': code, 'name': name, 'volume': volume})
    df = pd.DataFrame(stocks)
    return df.sort_values(by='volume', ascending=False).head(10) if not df.empty else df

# [추가] 국내 주도 테마 종목 수집
def get_top_theme_stocks(top_themes):
    print("\n--- [국내 주도 테마 종목 수집] ---")
    results = []
    for _, theme in top_themes.iterrows():
        try:
            print(f"🔥 테마 분석 중: {theme['name']}")
            theme_stocks = get_stocks_in_theme(theme['link'])
            for _, s in theme_stocks.head(5).iterrows():
                code = s['code']
                adv = get_naver_financials_advanced(code)
                if not adv: continue
                
                # 상승여력 계산
                upside_str = "N/A"
                if adv['target_price'] != "N/A" and adv['current_price'] > 0:
                    try:
                        upside_val = ((float(adv['target_price']) / adv['current_price']) - 1) * 100
                        upside_str = f"{upside_val:+.2f}%"
                    except: pass

                results.append({
                    'category': 'domestic_theme',
                    'theme': theme['name'],
                    'name': s['name'],
                    'code': code,
                    'volume': s['volume'],
                    'change_1m': get_1m_return(code),
                    'per': adv['per'],
                    'pbr': adv['pbr'],
                    'dividend': adv['dividend'],
                    'upside': upside_str,
                    'fair_value': adv['target_price'],
                    'opinion': adv['opinion'],
                    'grades': adv['grades'],
                    'is_profitable': "Pass (주도 테마)",
                    'time': datetime.now().strftime('%Y-%m-%d %H:%M')
                })
        except: continue
        if len(results) >= 30: break
    return results

# 3. 네이버 금융 수집 (상세 지표 및 등급 산출용)
def get_naver_financials_advanced(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5, verify=False)
        soup = BeautifulSoup(res.text, 'lxml')
        current_price = 0
        price_tag = soup.select_one('.no_today .blind')
        if price_tag:
            current_price = float(price_tag.text.strip().replace(',', ''))

        per = soup.select_one('#_per').text.strip() if soup.select_one('#_per') else "N/A"
        pbr = soup.select_one('#_pbr').text.strip() if soup.select_one('#_pbr') else "N/A"
        dvd_tag = soup.select_one('#_dvd')
        dvd = dvd_tag.text.strip() if dvd_tag else "N/A"
        
        target_price = "N/A"
        opinion = "N/A"
        aside = soup.select_one('.aside_invest_info')
        if aside:
            rows = aside.select('tr')
            for row in rows:
                th = row.select_one('th')
                if not th: continue
                th_text = th.text.replace(' ', '').replace('\n', '')
                if '투자의견' in th_text or '목표주가' in th_text:
                    ems = row.select('em')
                    if len(ems) >= 2:
                        target_price = ems[1].text.strip().replace(',', '')
                        span = row.select_one('td span')
                        opinion = span.text.strip() if span else ems[0].text.strip()
                    elif len(ems) == 1:
                        target_price = ems[0].text.strip().replace(',', '')
                    break

        # [추가] 2차: 하단 컨센서스 테이블 (cns_report) 에서 보완 (데이터가 없을 경우)
        if target_price == "N/A":
            cns_table = soup.select_one('.cns_report')
            if cns_table:
                tp_tag = cns_table.select_one('em')
                if tp_tag: target_price = tp_tag.text.strip().replace(',', '')
                op_tag = cns_table.select_one('strong')
                if op_tag: opinion = op_tag.text.strip()

        grades = {"profit": "보통", "health": "보통", "growth": "보통"}
        table = soup.select_one('.section.cop_analysis table')
        if table:
            rows = table.select('tr')
            for row in rows:
                th = row.select_one('th')
                if not th: continue
                txt = th.text.strip()
                tds = row.select('td')
                if not tds or len(tds) < 4: continue
                val_txt = tds[3].text.strip().replace(',', '')
                try:
                    val = float(val_txt)
                    if 'ROE' in txt:
                        if val > 15: grades["profit"] = "최고"
                        elif val > 10: grades["profit"] = "우수"
                        elif val < 0: grades["profit"] = "주의"
                    elif '부채비율' in txt:
                        if val < 60: grades["health"] = "최고"
                        elif val < 100: grades["health"] = "우수"
                        elif val > 200: grades["health"] = "주의"
                    elif '영업이익률' in txt:
                        if val > 20: grades["growth"] = "최고"
                        elif val > 10: grades["growth"] = "우수"
                except: pass

        return {"current_price": current_price, "per": per, "pbr": pbr, "dividend": dvd, "target_price": target_price, "opinion": opinion, "grades": grades}
    except Exception:
        return None

def check_ma_turnaround(code, is_us=False):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=250)
    try:
        if is_us:
            ticker = yf.Ticker(code)
            df = ticker.history(period="1y")
            if len(df) < 120: return False, 0
            df = df[['Close']].rename(columns={'Close': '종가'})
            volume = ticker.info.get('volume', 0)
        else:
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
        current_ok = (recent['MA5'] > recent['MA20']) and (recent['MA20'] > recent['MA60'])
        past_bad = (past_60['MA120'] > past_60['MA60']) or (past_60['MA60'] > past_60['MA5'])
        return (current_ok and past_bad), volume
    except Exception:
        return False, 0

def get_1m_return(code, is_us=False):
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
    print("\n--- [국내 바닥권 성장 가치주 정밀 탐색] ---")
    results = []
    processed_codes = set()
    
    # fund_df나 cap_df가 비어있을 경우에 대한 대비
    has_krx_data = not fund_df.empty and not cap_df.empty
    merged_df = fund_df.join(cap_df) if has_krx_data else pd.DataFrame()

    print(f"미래 성장 섹터 내 바닥권 우량주 분석 시작...")
    for _, theme in growth_themes.iterrows():
        try:
            theme_stocks = get_stocks_in_theme(theme['link'])
            for _, s in theme_stocks.iterrows():
                code = s['code']
                if code in processed_codes: continue
                
                # 기본 정보 수집 (KRX 데이터가 없으면 네이버에서 상세 수집)
                adv = get_naver_financials_advanced(code)
                if not adv or adv['grades']['profit'] == '주의': continue
                
                # 밸류에이션 필터
                per, pbr, div = 0, 0, "N/A"
                if has_krx_data and code in merged_df.index:
                    row = merged_df.loc[code]
                    per, pbr = float(row['PER']), float(row['PBR'])
                    div = f"{float(row['DIV']):.2f}%" if row['DIV'] != 0 else "N/A"
                else:
                    # KRX 데이터 실패 시 네이버 데이터 활용
                    try:
                        per = float(adv['per']) if adv['per'] != "N/A" else 999
                        pbr = float(adv['pbr']) if adv['pbr'] != "N/A" else 999
                        div = adv['dividend']
                    except: continue

                # 가치주 조건: PER 25 이하, PBR 1.5 이하 (완화)
                if 0 < per < 25 and 0 < pbr < 1.5:
                    end_date = datetime.now().strftime("%Y%m%d")
                    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
                    df_ohlcv = stock.get_market_ohlcv(start_date, end_date, code)
                    if df_ohlcv.empty: continue
                    
                    max_p, curr_p = df_ohlcv['종가'].max(), df_ohlcv['종가'].iloc[-1]
                    is_at_bottom = curr_p <= (max_p * 0.75) # 바닥권 조건 약간 완화
                    is_turnaround, _ = check_ma_turnaround(code)
                    vol_spike = False
                    if len(df_ohlcv) > 20:
                        vol_spike = df_ohlcv['거래량'].iloc[-5:].mean() > (df_ohlcv['거래량'].iloc[-20:].mean() * 1.3)
                    
                    target_p = adv['target_price']
                    upside_val = ((float(target_p) / curr_p) - 1) * 100 if target_p != "N/A" and curr_p > 0 else 0
                    
                    if (is_at_bottom and (is_turnaround or vol_spike)) or (upside_val > 25):
                        results.append({
                            'category': 'domestic_value',
                            'theme': theme['name'], 
                            'name': s['name'], 'code': code,
                            'volume': int(df_ohlcv['거래량'].iloc[-1]), 'change_1m': get_1m_return(code),
                            'per': f"{per:.2f}", 'pbr': f"{pbr:.2f}", 'dividend': div,
                            'upside': f"{upside_val:+.2f}%" if upside_val != 0 else "N/A", 'fair_value': target_p,
                            'opinion': adv['opinion'], 'grades': adv['grades'], 'is_profitable': "Pass (바닥권 우량주)",
                            'time': datetime.now().strftime('%Y-%m-%d %H:%M')
                        })
                        processed_codes.add(code)
                        print(f"💎 바닥권 보석 발견: {s['name']} (상승여력: {upside_val:.1f}%)")
                
                if len(results) >= 30: break
            if len(results) >= 30: break
        except: continue
    return results

def get_us_leading_sectors():
    print("\n미국 주도 섹터 분석 중...")
    sector_returns = {}
    for symbol, name in US_SECTOR_ETFS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")
            if not hist.empty:
                sector_returns[name] = (hist['Close'].iloc[-1] / hist['Close'].iloc[0]) - 1
        except: continue
    return [s[0] for s in sorted(sector_returns.items(), key=lambda x: x[1], reverse=True)[:3]]

def scan_us_tickers(tickers, index_name, leading_sectors, limit=30): # limit 30으로 상향
    results = []
    print(f"{index_name} 스캔 중...")
    for t in tickers:
        ticker_str = t.replace('.', '-')
        try:
            ticker = yf.Ticker(ticker_str)
            info = ticker.info
            
            # 섹터 정보를 테마로 활용
            sector = info.get('sector', index_name)
            
            pe, pb = info.get('trailingPE'), info.get('priceToBook')
            # 필터 완화: PE 50 이하, PB 10 이하
            if not pe or pe > 50 or not pb or pb > 10: continue
            
            high_52, curr_p = info.get('fiftyTwoWeekHigh', 0), info.get('currentPrice', 0)
            # 52주 고점 대비 필터 완화: 고점 대비 10% 이상 하락 (0.90)
            if high_52 > 0 and curr_p > (high_52 * 0.90): continue
            
            is_turnaround, volume = check_ma_turnaround(ticker_str, is_us=True)
            target_p = info.get('targetMeanPrice', "N/A")
            upside_val = ((target_p / curr_p) - 1) * 100 if target_p != "N/A" and curr_p > 0 else 0
            
            # 상승여력 20% 이상 또는 턴어라운드 신호
            if not (is_turnaround or upside_val > 20): continue
            
            grades = {"profit": "보통", "health": "보통", "growth": "보통"}
            roe = info.get('returnOnEquity', 0)
            if roe > 0.15: grades["profit"] = "최고"
            elif roe > 0.10: grades["profit"] = "우수"
            if info.get('debtToEquity', 150) < 60: grades["health"] = "최고"
            elif info.get('debtToEquity', 150) < 100: grades["health"] = "우수"

            # 카테고리 설정 (지수별)
            cat = 'us_sp'
            if 'NASDAQ' in index_name: cat = 'us_ndq'
            elif 'Russell' in index_name: cat = 'us_rsl'

            results.append({
                'category': cat,
                'theme': sector, # 섹터명을 테마로 사용
                'name': info.get('shortName', ticker_str), 'code': ticker_str,
                'volume': volume, 'change_1m': get_1m_return(ticker_str, is_us=True),
                'per': f"{pe:.2f}", 'pbr': f"{pb:.2f}",
                'dividend': f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "N/A",
                'upside': f"{upside_val:+.2f}%", 'fair_value': str(target_p),
                'opinion': info.get('recommendationKey', "N/A").replace('_', ' ').title(),
                'grades': grades, 'is_profitable': "Pass (성장/턴어라운드)",
                'time': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
            if len(results) >= limit: break
        except: continue
    return results

def get_russell1000_tickers():
    print("Russell 1000 종목 리스트 수집 중...")
    try:
        url = 'https://en.wikipedia.org/wiki/Russell_1000_Index#Components'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        res = requests.get(url, headers=headers, verify=False, timeout=10)
        tables = pd.read_html(io.StringIO(res.text))
        for table in tables:
            if 'Symbol' in table.columns:
                return [str(t).replace('.', '-') for t in table['Symbol'].tolist()]
    except Exception as e:
        print(f"Russell 1000 수집 오류: {e}")
    return []

def main():
    dart_api_key = os.getenv('DART_API_KEY')
    if dart_api_key:
        dart.set_api_key(api_key=dart_api_key)
        corp_list = dart.get_corp_list()
    else: corp_list = None

    top_themes, growth_focus = get_automated_growth_themes()
    results = []
    
    print("시장 투자지표 수집 중...")
    fund_df, cap_df = pd.DataFrame(), pd.DataFrame()
    for i in range(1, 10): # 최근 10일간의 데이터를 뒤져서 가장 최신 영업일 데이터 찾기
        search_date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
        try:
            # KRX API는 가끔 차단되므로 딜레이 부여
            time.sleep(0.5)
            temp_fund = stock.get_market_fundamental_by_ticker(search_date, market="ALL")
            temp_cap = stock.get_market_cap_by_ticker(search_date, market="ALL")
            if not temp_fund.empty and not temp_cap.empty:
                fund_df, cap_df = temp_fund, temp_cap
                print(f"[{search_date}] 데이터 수집 성공")
                break
        except Exception as e:
            print(f"[{search_date}] 데이터 수집 시도 실패: {e}")
            continue

    results.extend(get_top_theme_stocks(top_themes))
    results.extend(find_undervalued_turnaround_stocks(fund_df, cap_df, growth_focus))

    leading_sectors = get_us_leading_sectors()
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers, verify=False)
        sp500_tickers = pd.read_html(io.StringIO(res.text))[0]['Symbol'].tolist()
    except: sp500_tickers = []
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get('https://en.wikipedia.org/wiki/Nasdaq-100#Components', headers=headers, verify=False)
        ndx_tickers = pd.read_html(io.StringIO(res.text))[5]['Ticker'].tolist() # 인덱스 5로 수정
    except: ndx_tickers = []

    russell_tickers = get_russell1000_tickers()

    if sp500_tickers: results.extend(scan_us_tickers(sp500_tickers, 'S&P 500', leading_sectors))
    if ndx_tickers: results.extend(scan_us_tickers(ndx_tickers, 'NASDAQ 100', leading_sectors))
    if russell_tickers:
        # 러셀 1000에서 성장 테마와 일치하는 종목들을 찾기 위해 상위 700개를 우선 스캔 (확대)
        results.extend(scan_us_tickers(russell_tickers[:700], 'Russell 1000', leading_sectors, limit=30))

    with open('data.json', 'w', encoding='utf-8') as f:
        import json
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 분석 완료! {len(results)}개 종목 저장됨.")

if __name__ == "__main__":
    main()
