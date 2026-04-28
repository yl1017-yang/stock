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

load_dotenv()

# 1. 네이버 금융 테마 수집
def get_naver_themes():
    print("네이버 금융 테마 수집 중...")
    url = 'https://finance.naver.com/sise/theme.nhn'
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'lxml')
    
    theme_data = []
    # 테이블에서 테마명, 상승률 정보 추출
    rows = soup.select('table.type_1 tr')
    for row in rows:
        cols = row.select('td')
        if len(cols) > 0:
            name_tag = cols[0].select_one('a')
            if name_tag:
                name = name_tag.text.strip()
                link = name_tag['href']
                change_rate = cols[1].text.strip()
                theme_data.append({
                    'name': name,
                    'link': 'https://finance.naver.com' + link,
                    'change': float(change_rate.replace('%', '').replace('+', ''))
                })
    
    # 상승률 상위 10개 반환
    df = pd.DataFrame(theme_data)
    return df.sort_values(by='change', ascending=False).head(10)

# 2. 테마 내 종목 상세 수집 (거래량 포함)
def get_stocks_in_theme(theme_link):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(theme_link, headers=headers)
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
        res = requests.get(url, headers=headers, timeout=5)
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
        res = requests.get(url, headers=headers, timeout=5)
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

def check_ma_turnaround(code):
    """
    최근 120영업일 OHLCV 데이터를 통해 
    이동평균선 (5, 20, 60, 120일) 이 역배열에서 정배열로 전환 추세인지 확인.
    """
    end_date = datetime.today()
    start_date = end_date - timedelta(days=200) # 영업일 기준 120일을 넉넉히 가져옴
    
    try:
        # 일별 종가 데이터 (수정주가는 안됨)
        # 시간 단축을 위해 KOSPI/KOSDAQ 상관없이 ticker 기반 직접 조회
        ohlcv = stock.get_market_ohlcv(start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"), code)
        if len(ohlcv) < 120:
            return False, 0
            
        df = ohlcv[['종가']].copy()
        df['MA5'] = df['종가'].rolling(window=5).mean()
        df['MA20'] = df['종가'].rolling(window=20).mean()
        df['MA60'] = df['종가'].rolling(window=60).mean()
        df['MA120'] = df['종가'].rolling(window=120).mean()
        
        # 결측치 제거
        df = df.dropna()
        if len(df) < 10:
            return False, 0
            
        recent = df.iloc[-1]
        past_60_days = df.iloc[-60] # 약 3개월 전
        
        # 3개월 전에는 장기 이평선이 위에 있거나(역배열 성향), 
        # 최근에는 정배열(5 > 20 > 60 > 120)로 진입했는지 체크
        
        # 1) 현재가 정배열 성향 (완벽하지 않아도 단기가 중기를 뚫음)
        current_trend_good = (recent['MA5'] > recent['MA60']) and (recent['MA20'] > recent['MA120'])
        
        # 2) 과거에는 역배열 (120 > 60 > 20)
        past_trend_bad = (past_60_days['MA120'] > past_60_days['MA60']) or (past_60_days['MA60'] > past_60_days['MA20'])
        
        if current_trend_good and past_trend_bad:
            # 거래량도 대략 리턴
            return True, ohlcv.iloc[-1]['거래량']
            
        return False, ohlcv.iloc[-1]['거래량']
    except Exception as e:
        print(f"MA Check Error {code}: {e}")
        return False, 0

def find_undervalued_turnaround_stocks(fund_df, cap_df):
    """
    1차 필터링: PER, PBR, DIV, Market Cap
    2차 필터링: MA 턴어라운드 및 영업이익.
    """
    print("\n--- [저평가 턴어라운드(1차 필터링)] ---")
    
    # 1. PER, PBR, Market Cap 조건 필터링
    # cap_df에는 시가총액(상장시가총액) 필드가 있음. fund_df에는 PER, PBR 필드 존재.
    valid_stocks = []
    
    # 두 DataFrame 합치기 (인덱스가 code)
    if fund_df.empty or cap_df.empty:
        print("벌크 데이터가 없어 저평가 검색을 건너뜁니다.")
        return []
        
    merged_df = fund_df.join(cap_df)
    
    # 1차 필터 (예: 시총 1000억 이상, PER 0~15, PBR 0~1.5)
    # pykrx의 시가총액은 단위가 '원'입니다. 1,000억 = 100,000,000,000
    cond = (
        (merged_df['상장시가총액'] >= 100000000000) &
        (merged_df['PER'] > 0) & (merged_df['PER'] < 15) &
        (merged_df['PBR'] > 0) & (merged_df['PBR'] < 1.5)
    )
    
    filtered_df = merged_df[cond]
    print(f"1차 기본 재무 필터 통과 종목 수: {len(filtered_df)}")
    
    # 속도를 위해 시가총액/PER 등 점수를 매겨 상위 50~100개만 2차 분석
    # 저평가 매력이 높은(PER 낮은 순)으로 정렬
    sorted_filtered = filtered_df.sort_values(by='PER').head(60)
    
    results = []
    print("\n--- [저평가 턴어라운드(2차 필터링 - 심층 분석)] ---")
    for code, row in sorted_filtered.iterrows():
        try:
            name = stock.get_market_ticker_name(code)
            
            # MA 턴어라운드 체크
            is_turnaround, volume = check_ma_turnaround(code)
            if not is_turnaround:
                continue
                
            # 영업이익 우상향 체크 (DART보다 가벼운 네이버 기반)
            is_profit_up = check_operating_profit_upward(code)
            if not is_profit_up:
                continue
                
            # 통과된 종목
            results.append({
                'theme': '가치투자(저평가 턴어라운드)',
                'name': name,
                'code': code,
                'volume': int(volume),
                'per': str(row['PER']),
                'pbr': str(row['PBR']),
                'dividend': str(row['DIV']) if 'DIV' in row and row['DIV'] != 0 else "N/A",
                'is_profitable': "Pass (흑자상승)",
                'time': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
            
            print(f"💡 통과: {name} ({code}) - PER: {row['PER']}, PBR: {row['PBR']}")
            
            # 최종 10개까지만 모이면 종료
            if len(results) >= 10:
                break
                
            time.sleep(0.5) # API 과부하 방지
        except Exception as e:
            continue
            
    return results

def scan_us_tickers(tickers, theme_name, limit=10):
    results = []
    for t in tickers:
        ticker_str = t.replace('.', '-')
        try:
            ticker = yf.Ticker(ticker_str)
            info = ticker.info
            
            pe = info.get('trailingPE')
            pb = info.get('priceToBook')
            
            if pe is None or pb is None or pe <= 0 or pb <= 0: continue
            if pe >= 20 or pb >= 3: continue
            
            hist = ticker.history(period="6mo")
            if len(hist) < 120: continue
            
            df = hist[['Close']].copy()
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA60'] = df['Close'].rolling(window=60).mean()
            df['MA120'] = df['Close'].rolling(window=120).mean()
            df = df.dropna()
            if len(df) < 10: continue
            
            recent = df.iloc[-1]
            past_60 = df.iloc[-60]
            
            current_trend_good = (recent['MA5'] > recent['MA60']) and (recent['MA20'] > recent['MA120'])
            past_trend_bad = (past_60['MA120'] > past_60['MA60']) or (past_60['MA60'] > past_60['MA20'])
            
            if not (current_trend_good and past_trend_bad):
                continue
                
            q_fin = ticker.quarterly_financials
            if q_fin is None or q_fin.empty:
                continue
                
            if 'Operating Income' in q_fin.index:
                op_income = q_fin.loc['Operating Income'].dropna().tolist()
                if len(op_income) >= 3:
                    if op_income[0] <= 0 or op_income[0] < op_income[1]: 
                        continue
            else:
                continue

            results.append({
                'theme': theme_name,
                'name': info.get('shortName', ticker_str),
                'code': ticker_str,
                'volume': int(hist.iloc[-1]['Volume']),
                'per': f"{pe:.2f}",
                'pbr': f"{pb:.2f}",
                'dividend': f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "N/A",
                'is_profitable': "Pass (흑자상승)",
                'time': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
            print(f"🇺🇸 통과: {ticker_str} (PE: {pe:.2f}, PB: {pb:.2f})")
            
            if len(results) >= limit: break
            time.sleep(0.1)
        except Exception as e:
            continue
            
    return results

def find_us_turnaround_stocks():
    print("\n--- [미국 저평가 턴어라운드 검증 (S&P 500 + NASDAQ 100)] ---")
    headers = {'User-Agent': 'Mozilla/5.0'}
    import io
    
    sp500_tickers = []
    ndx_tickers = []
    
    try:
        res = requests.get('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies', headers=headers)
        sp500 = pd.read_html(io.StringIO(res.text))[0]
        sp500_tickers = sp500['Symbol'].tolist()[:300]
    except Exception as e:
        print(f"S&P 500 리스트 조회 실패: {e}")

    try:
        res_ndx = requests.get('https://en.wikipedia.org/wiki/Nasdaq-100', headers=headers)
        tables = pd.read_html(io.StringIO(res_ndx.text))
        for t in tables:
            if 'Ticker' in t.columns:
                ndx_tickers = t['Ticker'].tolist()
                break
            elif 'Symbol' in t.columns:
                ndx_tickers = t['Symbol'].tolist()
                break
    except Exception as e:
        print(f"NASDAQ 100 리스트 조회 실패: {e}")

    results = []
    
    if sp500_tickers:
        print("\nS&P 500 스캔 시작...")
        results.extend(scan_us_tickers(sp500_tickers, 'S&P 500 (턴어라운드)', 10))
        
    if ndx_tickers:
        print("\nNASDAQ 100 스캔 시작...")
        existing_codes = [r['code'] for r in results]
        ndx_tickers = [t for t in ndx_tickers if t.replace('.', '-') not in existing_codes]
        results.extend(scan_us_tickers(ndx_tickers, 'NASDAQ 100 (턴어라운드)', 10))
        
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

    # 테마 수집
    top_themes = get_naver_themes()
    print(f"상위 10개 테마: {list(top_themes['name'])}")
    
    results = []
    
    # 투자지표(PER, PBR 등) 및 시가총액 수집 (1단계: 전체 벌크 수집)
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
                print(f"{search_date} 기준 벌크 데이터를 사용합니다.")
                break
        except Exception:
            continue

    # [신규 추가] 저평가 턴어라운드 종목 검색
    undervalued_stocks = find_undervalued_turnaround_stocks(fund_df, cap_df)
    results.extend(undervalued_stocks)

    # [신규 추가] 미국 저평가 턴어라운드 종목 검색
    us_undervalued_stocks = find_us_turnaround_stocks()
    results.extend(us_undervalued_stocks)

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
                'per': per,
                'pbr': pbr,
                'dividend': dvd,
                'is_profitable': is_profitable,
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
