import requests
from bs4 import BeautifulSoup

def check_naver_net_income(code):
    print(f"--- {code} ---")
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        tbody = soup.select_one('div.cop_analysis tbody')
        if not tbody:
            print("재무제표 표를 찾을 수 없습니다.")
            return False
            
        rows = tbody.select('tr')
        net_income_row = None
        for r in rows:
            th = r.select_one('th')
            if th and '당기순이익' in th.text:
                net_income_row = r
                break
                
        if net_income_row:
            tds = net_income_row.select('td')
            # 0~3 인덱스가 연간 실적 4개년 (ex: 2021, 2022, 2023, 2024(E))
            # 4~9 인덱스가 최근 6개 분기 실적
            annual_incomes = []
            for td in tds[0:4]:
                text = td.text.strip().replace(',', '')
                if text and text != '-':
                    annual_incomes.append(int(text))
            
            print(f"연간 당기순이익: {annual_incomes}")
            
            # 최근 3년 실적만 가져오기 (가장 뒷쪽 3개)
            if len(annual_incomes) >= 3:
                last_3 = annual_incomes[-3:]
                print(f"최근 3년: {last_3}")
                is_all_negative = all(v < 0 for v in last_3)
                print(f"결과: 최근 3년 연속 적자? {is_all_negative}")
                return is_all_negative
            else:
                print("최근 3년치 데이터가 부족합니다.")
                return False
                
    except Exception as e:
        print(f"Error: {e}")
        return False

check_naver_net_income('005930') # 삼성전자
check_naver_net_income('456160') # 지투지바이오 (적자기업)
check_naver_net_income('105560') # KB금융
