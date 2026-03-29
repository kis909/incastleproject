import requests
import json
from kis_auto_trader import get_access_token, load_config

cfg = load_config()
token = get_access_token()

headers = {
    "Content-Type": "application/json",
    "authorization": f"Bearer {token}",
    "appKey": cfg['APP_KEY'],
    "appSecret": cfg['APP_SECRET'],
    "tr_id": "VTTC8434R"
}

params = {
    "CANO": cfg['CANO'],
    "ACNT_PRDT_CD": "01",
    "AFHR_FLPR_YN": "N",
    "OFL_YN": "",
    "INQR_DVSN": "02",
    "UNPR_DVSN": "01",
    "FUND_STTL_ICLD_YN": "N",
    "FNCG_AMT_AUTO_RDPT_YN": "N",
    "PRCS_DVSN": "01",
    "CTX_AREA_FK100": "",
    "CTX_AREA_NK100": ""
}

url = f"{cfg['URL_BASE']}/uapi/domestic-stock/v1/trading/inquire-balance"
res = requests.get(url, headers=headers, params=params)

print(json.dumps(res.json(), indent=2, ensure_ascii=False))
