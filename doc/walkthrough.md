# 🚀 주식 테마 및 수익성 분석기 프로젝트 완료

모든 핵심 기능 개발이 완료되었습니다! 이제 사용자님의 깃허브 저장소에 코드를 올리고 몇 가지 API 키만 설정하면 매일 자동으로 작동하는 나만의 주식 분석 시스템이 완성됩니다.

## ✨ 주요 기능

- **실시간 테마 분석**: 네이버 금융에서 당일 가장 핫한 테마 10개를 자동으로 수집합니다.
- **거래량 필터링**: 각 테마 내에서 거래량이 가장 활발한 종목들을 선별합니다.
- **수익성 검증 (DART)**: 금융감독원 공시 데이터를 직접 조회하여, 실제로 '영업이익'을 내고 있는 우량 기업인지 확인합니다.
- **프리미엄 대시보드**: 수집된 데이터를 유리 질감(Glassmorphism) 스타일의 다크 모드 대시보드로 시각화합니다.
- **자동화 & 알림**: GitHub Actions를 통해 매일 장 마감 후 자동 실행되며, 분석 결과 요약을 **카카오톡**으로 즉시 전송합니다.

## 📁 생성된 프로젝트 구조

- `main.py`: 전체 수집 및 분석 로직의 메인 스크립트
- `template.html`: 대시보드 웹페이지의 디자인 템플릿
- `kakao_api.py`: 카카오톡 메시지 전송을 담당하는 모듈
- `requirements.txt`: 필요한 라이브러리 목록
- `.github/workflows/deploy.yml`: 자동 실행 및 배포 설정 파일

## 🛠️ 필수 설정 (최종 단계)

프로그램이 정상적으로 작동하려면 깃허브 저장소의 **Settings > Secrets and variables > Actions** 메뉴에서 다음 **3가지 비밀 키(Secrets)**를 등록해야 합니다.

| 이름 | 설명 | 발급처 |
| :--- | :--- | :--- |
| `DART_API_KEY` | 수익성 검증을 위한 공시 API 키 | [Open DART](https://opendart.fss.or.kr/) |
| `KAKAO_REST_API_KEY` | 카톡 메시지 전송을 위한 키 | [Kakao Developers](https://developers.kakao.com/) |
| `KAKAO_REFRESH_TOKEN` | 메시지 전송 권한 유지를 위한 토큰 | (별도 가이드 필요) |

> [!IMPORTANT]
> **저장소 배포 설정 확인**: 
> 깃허브 저장소의 **Settings > Pages** 메뉴에서 `Build and deployment` -> `Source`를 반드시 **"GitHub Actions"**로 선택해 주세요. (질문하셨던 그 설정입니다!)

## 🚀 실행 결과 미리보기

![dashboard_preview](https://github.com/yl1017-yang/stock/raw/main/README.md)
*(대시보드는 배포 후 https://yl1017-yang.github.io/stock/ 에서 확인 가능합니다)*

---

**작업 완료 후 가이드**: 로컬 폴더에 생성된 파일들을 깃허브에 `git push` 하신 후, 위 API 키들을 등록하시면 오늘부터 바로 작동합니다. 카카오톡 **Refresh Token**을 발급받는 방법이 궁금하시면 말씀해 주세요! 가이드해 드리겠습니다.
