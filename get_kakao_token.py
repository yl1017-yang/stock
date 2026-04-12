import requests

def get_refresh_token():
    print("=== 카카오톡 Refresh Token 발급 도구 ===")
    rest_api_key = input("1. 카카오 REST API 키를 입력하세요: ").strip()
    redirect_uri = "https://localhost:3000" # 카카오 설정에서 등록한 것과 같아야 함
    auth_code = input("2. 브라우저 주소창에서 복사한 code 값을 입력하세요: ").strip()

    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": rest_api_key,
        "redirect_uri": redirect_uri,
        "code": auth_code
    }
    
    response = requests.post(url, data=data)
    result = response.json()
    
    if 'refresh_token' in result:
        print("\n" + "="*50)
        print("Success! 발급 성공!")
        print(f"KAKAO_REFRESH_TOKEN: {result['refresh_token']}")
        print("="*50)
        print("Copy the above value and register it as 'KAKAO_REFRESH_TOKEN' in GitHub Secrets.")
    else:
        print("\nFail! 발급 실패!")
        print(f"Error details: {result}")
        print("Check if the Redirect URI is registered as 'https://localhost:3000' in Kakao Developers.")

if __name__ == "__main__":
    get_refresh_token()
