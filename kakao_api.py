import requests
import json
import os

def refresh_access_token(rest_api_key, refresh_token):
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token
    }
    response = requests.post(url, data=data)
    result = response.json()
    
    if 'access_token' in result:
        return result['access_token']
    else:
        print(f"토큰 갱신 실패: {result}")
        return None

def send_kakao_message(text):
    rest_api_key = os.getenv('KAKAO_REST_API_KEY')
    refresh_token = os.getenv('KAKAO_REFRESH_TOKEN')
    
    if not rest_api_key or not refresh_token:
        print("카카오 API 설정(KEY/TOKEN)이 세팅되지 않았습니다.")
        return False
        
    access_token = refresh_access_token(rest_api_key, refresh_token)
    if not access_token:
        return False
        
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    payload = {
        "template_object": json.dumps({
            "object_type": "text",
            "text": text,
            "link": {
                "web_url": "https://yl1017-yang.github.io/stock/",
                "mobile_web_url": "https://yl1017-yang.github.io/stock/"
            },
            "button_title": "대시보드 보기"
        })
    }
    
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        print("카카오톡 메시지 전송 성공!")
        return True
    else:
        print(f"메시지 전송 실패: {response.json()}")
        return False
