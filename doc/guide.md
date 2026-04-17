# 💹 Stock Theme Analyzer - 프로젝트 개발 가이드 (AI & Human)

이 문서는 프로젝트의 구조, 개발 원칙 및 협업을 위한 가이드라인을 담고 있습니다. AI 어시스턴트나 새로운 개발자가 프로젝트에 참여할 때 이 문서를 가장 먼저 참고하십시오.

---

## 1. 프로젝트 개요 (Core Concept)
본 프로젝트는 **"오늘의 핫 테마 종목 분석 및 수익성 검증 자동화"**를 목표로 합니다.
- **Data First**: 모든 데이터는 파이썬이 객관적으로 수집 및 분석합니다.
- **Premium UI**: 분석된 결과는 사용자에게 '프리미엄' 감성의 현대적인 대시보드로 제공됩니다.
- **Separation of Concerns**: 데이터 분석 엔진(Python)과 UI 렌더링 엔진(JS)은 완전히 독립되어 동작합니다.

---

## 2. 시스템 아키텍처 및 역할
프로젝트는 **데이터 엔진**과 **UI 엔진**으로 이원화되어 있습니다.

### 2.1 🐍 데이터 엔진 (Python / `main.py`)
- **수집**: 네이버 금융 테마 및 종목 수집 + `pykrx`를 통한 실시간 투자 지표(PER, PBR, 배당) 수집.
- **분석**: Open DART API를 사용하여 해당 종목의 최근 영업이익(흑자 여부) 검증.
- **출력**: 분석 결과를 `data.json` 파일로 생성.
- **알림**: 분석 완료 시 카카오톡 알림 메시지 전송 (`kakao_api.py`).

### 2.2 🌐 UI 엔진 (JavaScript / `index.html`)
- **역할**: `data.json` 데이터 로드, 테마별 그룹화, 프리미엄 UI 렌더링.
- **기능**:
  - 각 테마 내 종목 **순위(#1, #2...)** 자동 부여 및 표시.
  - 종목별 **투자 지표(PER, PBR, DIV)** 하단 바 렌더링.
- **핵심 파일**: 
  - [index.html](file:///e:/%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8%EB%AA%A8%EC%9D%8C/00_git/stock/index.html): 메인 구조
  - [style.css](file:///e:/%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8%EB%AA%A8%EC%9D%8C/00_git/stock/style.css): 프리미엄 디자인 스타일
  - [script.js](file:///e:/%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8%EB%AA%A8%EC%9D%8C/00_git/stock/script.js): 동적 렌더링 로직

---

## 3. 데이터 스키마 (data.json)
`main.py`가 생성하고 `index.html`이 소비하는 데이터 표준 형식입니다.

```json
[
  {
    "theme": "테마명 (예: 전고체 배터리)",
    "name": "종목명 (예: 에코프로)",
    "code": "종목코드 (예: 086520)",
    "volume": 1234567,
    "per": "현재 PER (예: 15.4 또는 N/A)",
    "pbr": "현재 PBR (예: 1.2 또는 N/A)",
    "dividend": "현재 배당수익률 (예: 2.5% 또는 N/A)",
    "is_profitable": "Pass (흑자) | Fail (적자) | Skipped (API 키 없음)",
    "time": "2026-04-17 15:40"
  }
]
```

---

## 4. 환경 설정 (Configuration)
프로젝트 작동을 위해 아래의 환경 변수(Secrets)가 필요합니다.

| 변수명 | 설명 | 비고 |
| :--- | :--- | :--- |
| `DART_API_KEY` | Open DART 공시 데이터 조회용 | 없을 시 수익성 체크 생략 |
| `KAKAO_REST_API_KEY` | 카카오 알림톡 전송용 | |
| `KAKAO_REFRESH_TOKEN` | 카카오 API 권한 유지용 | |

---

## 5. 개발 및 수정 가이드 (AI 지침)

### ⚠️ 변경 금지 원칙
1.  **하드코딩 금지**: `index.html`에 종목 데이터를 직접 입력하지 마십시오. 모든 데이터는 `data.json`을 통해야 합니다.
2.  **구조 유지**: `main.py`는 데이터 생성 및 저장에만 집중해야 하며, HTML 태그를 생성하지 마십시오.

### ✅ 확장 및 고도화 가이드
- **데이터 엔진 확장 시**: `main.py`의 `results` 리스트에 새로운 필드를 추가하면 `data.json`에 자동 포함됩니다.
- **UI 개선 시**: `index.html`의 CSS 변수를 활용하십시오. 시각적으로 'Premium'하고 'Alive'한 느낌을 주기 위해 미세 애니메이션 적용을 권장합니다.
- **로컬 테스트**: `python main.py` 실행 후 `python -m http.server`를 통해 데이터를 확인하십시오.

---

## 6. 로컬 실행 및 배포
- **로컬 실행**:
  1. `pip install -r requirements.txt`
  2. `python main.py` (data.json 생성됨)
  3. `python -m http.server` 실행 후 `localhost:8000` 접속
- **배포**: GitHub Actions가 `main.py` 실행 후 최신 데이터를 포함한 정적 파일들을 GitHub Pages로 자동 배포합니다.
