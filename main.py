import requests
from bs4 import BeautifulSoup
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
    
    for _, theme in top_themes.iterrows():
        print(f"[{theme['name']}] 테마 종목 분석 중...")
        stocks_df = get_stocks_in_theme(theme['link'])
        
        for _, s in stocks_df.iterrows():
            is_profitable = "Skipped"
            if corp_list:
                is_profitable = check_profitability(corp_list, s['code'])
            
            results.append({
                'theme': theme['name'],
                'name': s['name'],
                'code': s['code'],
                'volume': s['volume'],
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
