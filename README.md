# 주식 테마 분석 대시보드

## GitHub Pages 배포와 자동 수집

- `main`에 push하면 저장소의 `data.json`을 그대로 배포합니다.
- 예약 실행(매일 한국시간 15:40) 또는 Actions 수동 실행에서는 새로 수집한 데이터를 배포합니다.
- 국내 일봉 및 KRX 지표 수집을 위해 `KRX_ID`, `KRX_PW`도 등록합니다. 로컬 `.env`는 GitHub Actions에 전달되지 않습니다.
- 지수 구성종목 조회 실패, 기존 탭 전체 누락, 국내 종목의 1개월 수익률 전체 누락 시 데이터 교체와 배포를 중단합니다. Actions 로그에서 실패 원인을 확인하고 인증 설정을 수정한 뒤 다시 실행하세요.
- 자동 수집 결과는 배포 산출물에만 반영되며 Git에 자동 커밋되지 않습니다. 로컬과 동일한 결과를 배포하려면 로컬에서 수집한 `data.json`을 커밋하고 push하세요.
- 배포에는 `index.html`, `style.css`, `script.js`, `data.json`만 포함됩니다.
- 배당·PER 등 개별 지표의 `N/A`는 원천 데이터가 없거나 해당 지표를 수집하지 않는 경우에도 표시됩니다.

이 프로젝트는 네이버 금융의 실시간 테마 데이터를 수집하여 시각화하는 웹 대시보드입니다. Python(Flask)으로 데이터를 수집하고, JavaScript(Vanilla)로 프론트엔드를 구현하여 반응형 대시보드를 제공합니다.

양 종목 메뉴와 토스 계좌 보유종목 조회는 제거했습니다. 국내 일봉은 KRX(pykrx)로 조회합니다. 토스 API 키는 사용하지 않습니다.

## 🚀 주요 기능

- **실시간 테마 분석**: 네이버 금융에서 상승률 상위 테마 및 관련 종목을 자동으로 수집합니다.
- **수익성 검증**: DART API를 활용하여 기업의 재무제표상 영업이익 흑자/적자 여부를 판별합니다.
- **고급 시각화**:
  - **테마별 카드**: 각 테마를 카드로 표시하며, 상승률과 거래량을 한눈에 확인합니다.
  - **필터링**: '전체보기'와 '수익종목만' 필터로 원하는 종목만 볼 수 있습니다.
  - **반응형 디자인**: 모바일과 PC에서 모두 최적화된 화면을 제공합니다.
- **데이터 연동**:
  - **Python Backend**: `main.py`가 데이터를 수집하여 `data.json`을 생성합니다.
  - **JavaScript Frontend**: `script.js`가 `data.json`을 읽어와 실시간으로 화면에 렌더링합니다.


## 🛠️ 설치 및 실행

### 1. 사전 요구 사항

- Python 3.8 이상
- Node.js (선택 사항, 로컬 개발 서버 사용 시)

### 2. 환경 설정

1. **가상 환경 생성 및 활성화**

   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

2. **필수 라이브러리 설치**

   ```bash
   pip install requests beautifulsoup4 pandas pykrx dart-fss python-dotenv
   ```

3. **DART API 키 설정**
   `.env` 파일을 생성하고 DART API 키를 추가합니다.
   ```env
   DART_API_KEY=your_dart_api_key_here
   ```

### 3. 데이터 수집 (Python)

데이터 수집 스크립트를 실행합니다.

```bash
python main.py
```

실행 후 `data.json` 파일이 생성됩니다.

### 4. 웹 대시보드 실행

**옵션 A: Python 내장 서버 사용**

```bash
python -m http.server 8000
```

브라우저에서 `http://localhost:8000`에 접속합니다.

**옵션 B: Node.js 사용 (개발 서버)**

```bash
npm install -g serve
serve .
```

브라우저에서 표시되는 주소로 접속합니다.

## 📂 프로젝트 구조

```
stock/
├── index.html          # 메인 대시보드 UI
├── style.css           # 스타일시트
├── script.js           # 프론트엔드 로직 (데이터 로드 및 렌더링)
├── main.py             # 백엔드 데이터 수집 스크립트
├── data.json           # 수집된 데이터 (자동 생성)
├── .env                # 환경 변수 (DART API 키)
└── README.md           # 프로젝트 설명
```

## 🎨 디자인 가이드

### 색상 팔레트

- **Primary**: `#007bff` (Blue)
- **Success**: `#28a745` (Green)
- **Warning**: `#ffc107` (Yellow)
- **Danger**: `#dc3545` (Red)
- **Background**: `#f8f9fa` (Light Gray)
- **Card Background**: `#ffffff` (White)

### 폰트

- **Font Family**: 'Outfit', sans-serif
- **Weights**: 300, 400, 600, 700

### 레이아웃

- **Dashboard Grid**: 3열 그리드 (PC), 2열 (Tablet), 1열 (Mobile)
- **Card Design**: 둥근 모서리(12px), 그림자 효과, 호버 애니메이션

## 📝 데이터 구조 (data.json)

```json
{
  "update_time": "2026-04-18 10:30:00",
  "themes": [
    {
      "name": "테마명",
      "change": 10.5,
      "stocks": [
        {
          "code": "005930",
          "name": "삼성전자",
          "volume": 1000000,
          "per": "15.0",
          "pbr": "1.5",
          "dvd": "2.0%",
          "is_profitable": "Pass (흑자)"
        }
      ]
    }
  ]
}
```

## 🤝 기여 방법

1. 저장소를 포크합니다.
2. 새 브랜치를 생성합니다 (`git checkout -b feature/AmazingFeature`).
3. 변경 사항을 커밋합니다 (`git commit -m 'Add some AmazingFeature'`).
4. 브랜치를 푸시합니다 (`git push origin feature/AmazingFeature`).
5. 풀 리퀘스트를 생성합니다.

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

