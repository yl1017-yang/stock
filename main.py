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
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Windows 콘솔에서 이모지/한글 로그가 깨지거나 출력 실패하는 문제를 줄인다.
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# 일부 실행 환경에서 SSL 인증서 검증 때문에 외부 수집이 실패하는 문제를 완화한다.
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

load_dotenv()

# =================================================================
# [설정] 미래 성장 테마 탐지 기준
# =================================================================
# 성장 키워드는 미래 테마를 강제로 고정하는 값이 아니라 1차 안전장치다.
# 실제 성장 테마 후보는 아래 4단계를 합산해 자동 선별한다.
# 1) 기본 키워드 가산점 유지
# 2) 네이버 테마 상승률/상대강도 기반 자동 후보 점수 추가
# 3) 뉴스/LLM 보조 점수는 옵션으로만 반영
# 4) 검증 조건을 통과한 테마만 growth_focus에 포함
CORE_GROWTH_KEYWORDS = [
    'AI', '인공지능', '온디바이스 AI', '피지컬 AI', '휴머노이드',
    '로봇', '반도체', 'HBM', 'CXL', '데이터센터',
    '전력', '전력기기', '전력인프라', '냉각',
    '배터리', '2차전지', '전고체', 'ESS',
    '바이오', '우주', '항공', '방산',
    '에너지', 'SMR', '원전',
    '자율주행', '양자', '양자보안', '플랫폼', '혁신'
]
OLD_ECONOMY_KEYWORDS = ['음식료', '섬유', '의복', '종이', '목재', '건설', '유통', '시멘트', '가구']
OPTIONAL_THEME_CONTEXT_KEYWORDS = [
    '인프라', '클라우드', '보안', '자동화', '스마트팩토리', '모빌리티',
    '친환경', '재생에너지', '수소', '탄소', '의료AI', '유전자', '첨단소재'
]

US_SECTOR_ETFS = {
    'XLK': 'Technology', 'XLV': 'Healthcare', 'XLC': 'Communication Services',
    'XLY': 'Consumer Discretionary', 'XLF': 'Financials', 'XLI': 'Industrials',
    'XLP': 'Consumer Staples', 'XLE': 'Energy', 'XLB': 'Materials',
    'XLRE': 'Real Estate', 'XLU': 'Utilities'
}

# 성장 키워드 점수는 보수적인 안전장치다. 키워드가 있으면 성장 후보 가능성이 높다고 보고 가산한다.
def get_theme_keyword_score(theme_name):
    score = 0
    if any(kw in theme_name for kw in CORE_GROWTH_KEYWORDS):
        score += 5.0
    if any(kw in theme_name for kw in OPTIONAL_THEME_CONTEXT_KEYWORDS):
        score += 2.0
    if any(kw in theme_name for kw in OLD_ECONOMY_KEYWORDS):
        score -= 8.0
    return score

# 네이버 테마 시장 데이터만으로 자동 후보 점수를 계산한다.
# 키워드에 없는 새 테마라도 상승률이 강하고 시장 관심이 붙으면 growth_focus 후보에 들어갈 수 있다.
def get_auto_theme_market_score(theme_change, change_rank, total_count):
    if total_count <= 0:
        return 0

    percentile = change_rank / total_count
    score = 0
    if theme_change >= 8:
        score += 4.0
    elif theme_change >= 5:
        score += 3.0
    elif theme_change >= 3:
        score += 2.0
    elif theme_change > 0:
        score += 1.0

    if percentile <= 0.05:
        score += 2.0
    elif percentile <= 0.10:
        score += 1.5
    elif percentile <= 0.20:
        score += 1.0

    return score

# 뉴스/LLM 점수는 보조 신호다. 기본값은 꺼져 있으며, 켜져 있어도 단독으로 최종 채택하지 않는다.
# 실제 API 연결 전까지는 테마명 주변 키워드와 환경 변수 기반 가산점만 제공하는 안전한 확장 지점으로 둔다.
def get_optional_theme_context_score(theme_name):
    if os.getenv('ENABLE_THEME_CONTEXT_SCORE', '').lower() != 'true':
        return 0
    return 2.0 if any(kw in theme_name for kw in OPTIONAL_THEME_CONTEXT_KEYWORDS) else 0

# 최종 검증 단계다. 키워드, 자동 시장 점수, 보조 점수 중 하나만 맹신하지 않고
# 구경제 감점과 최소 시장 강도를 함께 확인한 테마만 저평가 탐색 대상으로 사용한다.
def is_verified_growth_theme(theme):
    if any(kw in theme['name'] for kw in OLD_ECONOMY_KEYWORDS) and theme['change'] < 5:
        return False
    return (
        theme['keyword_score'] >= 5
        or theme['auto_market_score'] >= 4
        or (theme['context_score'] >= 2 and theme['auto_market_score'] >= 2)
    )

# 1. 네이버 금융 테마 수집 및 성장 섹터 자동 판별
# 화면용 급등 테마(top_display)는 단순 상승률 기준으로 유지하고,
# 저평가 탐색용 성장 테마(growth_focus)는 4단계 검증 점수로 자동 선별한다.
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

    ranked_themes = sorted(all_themes, key=lambda item: item['change'], reverse=True)
    total_count = len(ranked_themes)
    scored_themes = []
    for rank, theme in enumerate(ranked_themes, start=1):
        keyword_score = get_theme_keyword_score(theme['name'])
        auto_market_score = get_auto_theme_market_score(theme['change'], rank, total_count)
        context_score = get_optional_theme_context_score(theme['name'])
        score = theme['change'] + keyword_score + auto_market_score + context_score
        scored_themes.append({
            **theme,
            'score': score,
            'keyword_score': keyword_score,
            'auto_market_score': auto_market_score,
            'context_score': context_score
        })
    
    df = pd.DataFrame(scored_themes)
    if df.empty:
        return df, df

    top_display = df.sort_values(by='change', ascending=False).head(10)
    verified_df = df[df.apply(lambda row: is_verified_growth_theme(row), axis=1)]
    growth_focus = verified_df.sort_values(by='score', ascending=False).head(20)
    return top_display, growth_focus

# 2. 테마 내 종목 상세 수집
# 테마 상세 페이지에서 거래량 상위 종목을 가져와 이후 지표 수집 대상으로 사용한다.
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

# 3. 국내 주도 테마 종목 수집
# "국내 테마" 탭에 노출할 단기 주도 테마 종목을 구성한다.
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
                    'current_price': adv['current_price'],
                    'opinion': adv['opinion'],
                    'grades': adv['grades'],
                    'is_profitable': "Pass (주도 테마)",
                    'time': datetime.now().strftime('%Y-%m-%d %H:%M')
                })
        except: continue
        if len(results) >= 30: break
    return results

# 4. 네이버 금융 수집 (상세 지표 및 등급 산출용)
# 현재가, PER/PBR, 배당, 목표가, 투자의견, 간단 재무 등급을 한 번에 수집한다.
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

        # 재무제표 요약값을 4단계 등급으로 단순화해 카드 배지에 사용한다.
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

# 5. 이동평균 기반 턴어라운드 신호 확인
# 현재는 성장 저평가 핵심 필터에서는 직접 쓰지 않지만,
# 바닥권/턴어라운드 조건을 다시 도입할 때 재사용할 수 있는 보조 함수다.
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

# 6. 최근 1개월 수익률 계산
# 국내는 KRX OHLCV, 미국은 yfinance 히스토리를 사용한다.
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

# 7. 외부 API 숫자값 안전 변환
# yfinance는 None, "N/A", 문자열 숫자를 섞어 반환하므로 필터 전에 숫자로 정규화한다.
def _safe_float(value, default=0):
    try:
        if value in (None, "N/A", ""):
            return default
        return float(str(value).replace(',', '').replace('%', ''))
    except:
        return default

# 8. 국내 성장 저평가주 탐색
# 단순 낙폭과대주가 아니라 성장 테마 안에서 가격, 수급, 이평선 회복이 함께 확인되는 종목을 선별한다.
def find_undervalued_turnaround_stocks(fund_df, cap_df, growth_themes):
    print("\n--- [국내 성장 저평가주 정밀 탐색] ---")
    results = []
    processed_codes = set()
    
    # fund_df나 cap_df가 비어있을 경우에 대한 대비
    has_krx_data = not fund_df.empty and not cap_df.empty
    merged_df = fund_df.join(cap_df) if has_krx_data else pd.DataFrame()

    print("미래 성장 섹터 내 성장 저평가 후보 분석 시작...")
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

                # 성장 저평가 조건: 너무 싼 종목보다 합리적 가격의 성장 후보를 우선한다.
                if 0 < per <= 35 and 0 < pbr <= 4:
                    end_date = datetime.now().strftime("%Y%m%d")
                    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
                    df_ohlcv = stock.get_market_ohlcv(start_date, end_date, code)
                    if df_ohlcv.empty or len(df_ohlcv) < 60: continue
                    
                    max_p = df_ohlcv['종가'].max()
                    curr_p = df_ohlcv['종가'].iloc[-1]
                    volume = int(df_ohlcv['거래량'].iloc[-1])
                    trading_value = curr_p * volume
                    drawdown = 1 - (curr_p / max_p) if max_p > 0 else 0
                    ma20 = df_ohlcv['종가'].rolling(window=20).mean().iloc[-1]
                    ma60 = df_ohlcv['종가'].rolling(window=60).mean().iloc[-1]
                    recent_volume = df_ohlcv['거래량'].iloc[-5:].mean()
                    base_volume = df_ohlcv['거래량'].iloc[-20:].mean()
                    volume_recovering = base_volume > 0 and recent_volume >= (base_volume * 0.8)
                    month_return = (curr_p / df_ohlcv['종가'].iloc[-20] - 1) * 100 if len(df_ohlcv) >= 20 else 0
                    
                    target_p = adv['target_price']
                    upside_val = ((float(target_p) / curr_p) - 1) * 100 if target_p != "N/A" and curr_p > 0 else 0

                    # 성장 저평가 점수:
                    # 밸류에이션, 목표가 상승여력, 이평선 회복, 1개월 모멘텀,
                    # 거래 회복을 가산하고 과도한 소외/목표가 괴리는 감점한다.
                    score = 0
                    if per <= 25: score += 2
                    elif per <= 35: score += 1
                    if pbr <= 2.5: score += 2
                    elif pbr <= 4: score += 1
                    if 15 <= upside_val <= 40: score += 2
                    elif 40 < upside_val <= 70: score += 1
                    if curr_p >= ma20: score += 2
                    if curr_p >= ma60: score += 1
                    if month_return > 0: score += 2
                    elif month_return > -5: score += 1
                    if volume_recovering: score += 1
                    if trading_value >= 3_000_000_000: score += 1
                    if drawdown > 0.50: score -= 3
                    if month_return < -10: score -= 2
                    if upside_val > 80: score -= 1

                    # 최종 통과 조건은 점수만 보지 않고 최소 유동성, 하락폭, 모멘텀을 함께 요구한다.
                    is_growth_value = (
                        score >= 7
                        and 0.03 <= drawdown <= 0.50
                        and upside_val >= 12
                        and trading_value >= 1_000_000_000
                        and (curr_p >= ma20 or curr_p >= ma60)
                        and month_return > -10
                    )

                    if is_growth_value:
                        results.append({
                            'category': 'domestic_value',
                            'theme': theme['name'], 
                            'name': s['name'], 'code': code,
                            'volume': volume, 'change_1m': f"{month_return:+.2f}%",
                            'per': f"{per:.2f}", 'pbr': f"{pbr:.2f}", 'dividend': div,
                            'upside': f"{upside_val:+.2f}%" if upside_val != 0 else "N/A", 'fair_value': target_p,
                            'current_price': curr_p,
                            'opinion': adv['opinion'], 'grades': adv['grades'], 'is_profitable': "Pass (성장 저평가)",
                            'time': datetime.now().strftime('%Y-%m-%d %H:%M')
                        })
                        processed_codes.add(code)
                        print(f"💎 성장 저평가 후보 발견: {s['name']} (점수: {score}, 상승여력: {upside_val:.1f}%)")
                
                if len(results) >= 30: break
            if len(results) >= 30: break
        except: continue
    return results

# 9. 미국 주도 섹터 계산
# 섹터 ETF의 최근 1개월 수익률을 비교해 미국 성장 저평가 점수에 가산점으로 사용한다.
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

# 10. 미국 성장 저평가주 탐색
# S&P500, NASDAQ100, Russell1000 후보를 같은 GARP 기준으로 평가한다.
def scan_us_tickers(tickers, index_name, leading_sectors, limit=30):
    results = []
    print(f"{index_name} 성장 저평가 스캔 중...")
    for t in tickers:
        ticker_str = t.replace('.', '-')
        try:
            ticker = yf.Ticker(ticker_str)
            info = ticker.info
            
            # 섹터 정보를 테마로 활용
            sector = info.get('sector', index_name)
            
            # GARP 필터의 기본 재료: 현재 밸류에이션, 미래 이익 개선, 성장률, 유동성.
            pe = _safe_float(info.get('trailingPE'))
            pb = _safe_float(info.get('priceToBook'))
            forward_pe = _safe_float(info.get('forwardPE'))
            revenue_growth = _safe_float(info.get('revenueGrowth'))
            earnings_growth = _safe_float(info.get('earningsGrowth'))
            peg = _safe_float(info.get('pegRatio'))
            market_cap = _safe_float(info.get('marketCap'))
            avg_volume = _safe_float(info.get('averageVolume'))

            # 너무 비싸거나 유동성이 낮은 종목은 분석 대상에서 제외한다.
            if pe <= 0 or pe > 45: continue
            if pb <= 0 or pb > 12: continue
            if market_cap < 2_000_000_000 or avg_volume < 300_000: continue
            
            # 과열 구간도, 50% 이상 빠진 과도한 소외 구간도 피한다.
            high_52, curr_p = info.get('fiftyTwoWeekHigh', 0), info.get('currentPrice', 0)
            if not curr_p or curr_p <= 0: continue
            drawdown = 1 - (curr_p / high_52) if high_52 else 0
            if drawdown < 0.03 or drawdown > 0.50: continue
            
            # 최근 가격/거래량 회복 여부를 3개월 히스토리에서 확인한다.
            ticker_hist = ticker.history(period="3mo")
            if ticker_hist.empty or len(ticker_hist) < 50: continue
            month_return = (ticker_hist['Close'].iloc[-1] / ticker_hist['Close'].iloc[-20] - 1) * 100
            ma20 = ticker_hist['Close'].rolling(window=20).mean().iloc[-1]
            ma50 = ticker_hist['Close'].rolling(window=50).mean().iloc[-1]
            volume = int(info.get('volume') or ticker_hist['Volume'].iloc[-1] or 0)
            volume_recovering = ticker_hist['Volume'].iloc[-5:].mean() >= (ticker_hist['Volume'].iloc[-20:].mean() * 0.8)

            target_p = info.get('targetMeanPrice', "N/A")
            upside_val = ((target_p / curr_p) - 1) * 100 if target_p != "N/A" and curr_p > 0 else 0
            
            # 성장성이 확인되지 않으면 저평가처럼 보여도 제외한다.
            has_growth = (
                revenue_growth > 0.03
                or earnings_growth > 0.03
                or (forward_pe > 0 and forward_pe < pe)
            )
            if not has_growth: continue

            # 미국 성장 저평가 점수:
            # Forward PE 개선, 매출/EPS 성장, 합리적 PER/PBR, 목표가 상승여력,
            # 이평선/모멘텀 회복, 주도 섹터 여부를 반영한다.
            score = 0
            if forward_pe > 0 and forward_pe < pe: score += 2
            if revenue_growth > 0.05: score += 2
            elif revenue_growth > 0.03: score += 1
            if earnings_growth > 0.05: score += 2
            elif earnings_growth > 0.03: score += 1
            if peg > 0 and peg <= 2: score += 1
            if pe <= 30: score += 2
            elif pe <= 45: score += 1
            if pb <= 6: score += 1
            if 15 <= upside_val <= 45: score += 2
            elif 45 < upside_val <= 80: score += 1
            if curr_p >= ma20: score += 2
            if curr_p >= ma50: score += 1
            if month_return > 0: score += 2
            elif month_return > -5: score += 1
            if volume_recovering: score += 1
            if sector in leading_sectors: score += 1
            if drawdown > 0.50: score -= 3
            if month_return < -10: score -= 2
            if upside_val > 90: score -= 1

            # 점수가 높아도 상승여력, 최근 모멘텀, 이평선 회복 중 핵심 조건이 약하면 제외한다.
            if not (
                score >= 8
                and upside_val >= 12
                and month_return > -10
                and (curr_p >= ma20 or curr_p >= ma50)
            ):
                continue
            
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
                'volume': volume, 'change_1m': f"{month_return:+.2f}%",
                'per': f"{pe:.2f}", 'pbr': f"{pb:.2f}",
                'dividend': f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "N/A",
                'upside': f"{upside_val:+.2f}%", 'fair_value': str(target_p),
                'current_price': curr_p,
                'opinion': info.get('recommendationKey', "N/A").replace('_', ' ').title(),
                'grades': grades, 'is_profitable': "Pass (성장 저평가)",
                'time': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
            if len(results) >= limit: break
        except: continue
    return results

# 11. Russell 1000 구성 종목 수집
# Wikipedia 표 구조가 바뀔 수 있으므로 Symbol 컬럼이 있는 테이블을 찾아 사용한다.
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

# 12. 전체 수집 파이프라인 실행
# 국내 테마, 국내 성장 저평가, 미국 성장 저평가 결과를 합쳐 data.json으로 저장한다.
def main():
    # DART 키가 있으면 기업 목록을 미리 로드한다. 현재 로직에서는 확장 대비 성격이 강하다.
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

    # 미국 지수별 구성 종목을 수집한 뒤 동일한 성장 저평가 스코어로 평가한다.
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
        # pandas/numpy 숫자 타입은 기본 JSON 직렬화가 안 되므로 item()으로 일반 숫자로 바꾼다.
        json.dump(
            results,
            f,
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.item() if hasattr(value, "item") else str(value)
        )
    print(f"\n✅ 분석 완료! {len(results)}개 종목 저장됨.")

if __name__ == "__main__":
    main()
