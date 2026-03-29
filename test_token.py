import json
import requests

def test_kis_token():
    try:
        with open("kis_secret.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print("kis_secret.json 파일 읽기 실패:", e)
        return

    app_key = cfg.get("APP_KEY")
    app_secret = cfg.get("APP_SECRET")

    urls = {
        "모의투자": "https://openapivts.koreainvestment.com:29443",
        "실전투자": "https://openapi.koreainvestment.com:9443"
    }

    print("🔑 KIS API 토큰 발급 테스트 시작...")
    
    for name, base_url in urls.items():
        url = f"{base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": app_secret
        }
        print(f"\n[{name}] {url} 로 접근 시도...")
        try:
            res = requests.post(url, headers=headers, json=body, timeout=5)
            if res.status_code == 200:
                print(f"✅ [{name}] 토큰 발급 성공!")
            else:
                print(f"❌ [{name}] 실패 ({res.status_code}):", res.text)
        except Exception as e:
            print(f"❌ [{name}] 요청 에러:", e)

if __name__ == "__main__":
    test_kis_token()
