import requests
from bs4 import BeautifulSoup

def get_pbr(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # PBR is usually in an id called _pbr
        pbr_tag = soup.select_one('#_pbr')
        if pbr_tag:
            return float(pbr_tag.text.replace(',', ''))
        return None
    except Exception as e:
        print(e)
        return None

for c in ['105560', '085620']: # KB금융, 미래에셋생명
    print(f"{c} PBR: {get_pbr(c)}")
