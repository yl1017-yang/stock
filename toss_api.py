"""토스증권 Open API의 인증 및 보유종목 조회 기능."""

import os

import requests


BASE_URL = "https://openapi.tossinvest.com"
_SESSION = None


class TossAPIError(RuntimeError):
    """토스증권 API 호출 실패."""


def _request(session, method, path, **kwargs):
    response = session.request(method, f"{BASE_URL}{path}", timeout=15, **kwargs)
    if response.ok:
        return response.json()

    try:
        error = response.json().get("error", {})
        message = error.get("message") or error.get("code")
    except (ValueError, AttributeError):
        message = None
    raise TossAPIError(
        f"토스증권 API 요청 실패 ({response.status_code})"
        + (f": {message}" if message else "")
    )


def _get_session():
    """액세스 토큰을 발급해 프로세스 안에서 재사용하는 세션을 반환한다."""
    global _SESSION
    if _SESSION is not None:
        return _SESSION

    client_id = os.getenv("TOSS_CLIENT_ID")
    client_secret = os.getenv("TOSS_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise TossAPIError("TOSS_CLIENT_ID 또는 TOSS_CLIENT_SECRET이 설정되지 않았습니다.")

    session = requests.Session()
    token_data = _request(
        session,
        "POST",
        "/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    token = token_data.get("access_token")
    if not token:
        raise TossAPIError("토스증권 액세스 토큰이 응답에 없습니다.")

    session.headers["Authorization"] = f"Bearer {token}"
    _SESSION = session
    return session


def get_holdings():
    """환경변수의 API 키로 선택 계좌의 보유종목과 합계를 반환한다."""
    session = _get_session()
    accounts = _request(session, "GET", "/api/v1/accounts").get("result", [])
    if not accounts:
        raise TossAPIError("조회 가능한 토스증권 계좌가 없습니다.")

    preferred_seq = os.getenv("TOSS_ACCOUNT_SEQ")
    account = next(
        (item for item in accounts if str(item.get("accountSeq")) == preferred_seq),
        accounts[0],
    )
    session.headers["X-Tossinvest-Account"] = str(account["accountSeq"])
    result = _request(session, "GET", "/api/v1/holdings").get("result", {})
    return {
        "items": result.get("items", []),
        "summary": {key: value for key, value in result.items() if key != "items"},
    }


def get_daily_candles(symbol, count=200):
    """국내·미국 종목의 수정주가 적용 일봉을 오래된 순서로 반환한다."""
    session = _get_session()
    result = _request(
        session,
        "GET",
        "/api/v1/candles",
        params={"symbol": symbol, "interval": "1d", "count": min(count, 200), "adjusted": "true"},
    ).get("result", {})
    return list(reversed(result.get("candles", [])))
