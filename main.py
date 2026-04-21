import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import os
from pykrx import stock
import dart_fss as dart
from datetime import datetime, timedelta
from dotenv import load_dotenv

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

# 3. 수익성 검증 (영업이익 체크)
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
            # 가장 최신 컬럼(보통 첫 번째 데이터 컬럼)의 값 확인
            # 데이터 컬럼은 보통 '2023', '2024' 등 연도 형태
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
    
    # 투자지표(PER, PBR 등) 수집 (1단계: 전체 벌크 수집)
    print("시장 투자지표 수집 중...")
    fund_df = pd.DataFrame()
    last_business_day = datetime.now().strftime('%Y%m%d')
    for i in range(7):
        search_date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
        try:
            temp_df = stock.get_market_fundamental_by_ticker(search_date, market="ALL")
            if not temp_df.empty:
                fund_df = temp_df
                last_business_day = search_date
                print(f"{search_date} 기준 벌크 데이터를 사용합니다.")
                break
        except Exception:
            continue

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
        message = f"🚀 [오늘의 급등 테마 수익 종목]\n총 {count}개 종목 검증 통과!\n주요 종목: {top_3} 등\n\n자세한 내용은 대시보드에서 확인하세요."
        send_kakao_message(message)
    else:
        send_kakao_message("오늘 검증을 통과한 수익 종목이 없습니다. 대시보드를 확인해 보세요.")

if __name__ == "__main__":
    main()
