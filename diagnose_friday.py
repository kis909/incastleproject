"""
001450(현대해상), 139130(DGB금융지주) 매수 탈락 원인 정밀 분석
인코딩 이슈 수정 버전
"""
import yfinance as yf
import datetime
import requests
from bs4 import BeautifulSoup

def get_naver_pbr(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        em = soup.select_one('em#_pbr')
        if em:
            return float(em.text.strip().replace(',',''))
    except Exception as e:
        return None
    return None

TARGET_DATE = datetime.date(2026, 3, 21)
STOCKS = [
    {"kis": "001450", "yf": "001450.KS", "name": "Hyundai Marine & Fire"},
    {"kis": "139130", "yf": "139130.KS", "name": "DGB Financial Group"},
]

for s in STOCKS:
    print()
    print("=" * 60)
    print(f"[{s['kis']}] {s['name']} - Friday buy rejection analysis")
    print("=" * 60)

    try:
        ticker = yf.Ticker(s['yf'])
        hist = ticker.history(period='200d')
        if hist is None or len(hist) == 0:
            print("  ERROR: no history data")
            continue
            
        hist.index = hist.index.tz_convert(None) if hist.index.tz is not None else hist.index

        # 날짜별 분류
        prev_dates = [d for d in hist.index if d.date() < TARGET_DATE]
        cur_dates  = [d for d in hist.index if d.date() == TARGET_DATE]

        if not prev_dates:
            print("  ERROR: no previous day data")
            continue

        prev_idx   = prev_dates[-1]
        prev_close = float(hist.loc[prev_idx, 'Close'])
        prev_low   = float(hist.loc[prev_idx, 'Low'])
        
        all_before = [d for d in hist.index if d <= prev_idx]
        ma60 = float(hist.loc[all_before[-60:],'Close'].mean()) if len(all_before) >= 60 else None

        print(f"  Previous day : {prev_idx.date()}")
        print(f"  prev_close   : {prev_close:,.0f} KRW")
        print(f"  prev_low     : {prev_low:,.0f} KRW  <- target (gap fill)")
        print(f"  MA60         : {ma60:,.0f} KRW" if ma60 else "  MA60: N/A")

        # 금요일 데이터 유무
        if cur_dates:
            cur_idx = cur_dates[0]
            c_price = float(hist.loc[cur_idx, 'Close'])
            c_high  = float(hist.loc[cur_idx, 'High'])
            c_open  = float(hist.loc[cur_idx, 'Open'])

            print(f"\n  Friday data:")
            print(f"  Open  : {c_open:,.0f}")
            print(f"  Close : {c_price:,.0f}")
            print(f"  High  : {c_high:,.0f}")

            is_gap_down  = prev_low > c_high
            is_drop_4pct = c_price <= (prev_close * 0.96)
            is_uptrend   = (c_price > ma60) if ma60 else None

            print(f"\n  ---- Buy Condition Checks ----")
            print(f"  is_gap_down  (prev_low {prev_low:,.0f} > c_high {c_high:,.0f}): {is_gap_down}  {'PASS' if is_gap_down else '>>> FAIL'}")
            print(f"  is_drop_4pct (c_price {c_price:,.0f} <= {prev_close*0.96:,.0f}): {is_drop_4pct}  {'PASS' if is_drop_4pct else '>>> FAIL'}")
            print(f"  is_uptrend   (c_price {c_price:,.0f} > MA60 {ma60:,.0f}): {is_uptrend}  {'PASS' if is_uptrend else '>>> FAIL'}")
        else:
            print(f"\n  [!] NO FRIDAY DATA in yfinance!")
            print(f"  Latest available date: {hist.index[-1].date()}")
            print(f"      => When bot ran at 15:15 on Friday, yfinance may not")
            print(f"         have had intraday data yet for {TARGET_DATE}")

        # 금융주 PBR 체크
        info = ticker.info
        sector = info.get('sector', 'Unknown')
        pbr_yf = info.get('priceToBook', None)
        print(f"\n  ---- Financial Filter ----")
        print(f"  Sector: {sector}")
        print(f"  PBR (yfinance): {pbr_yf}")
        
        pbr_naver = get_naver_pbr(s['kis'])
        print(f"  PBR (Naver):    {pbr_naver}")
        
        if sector == "Financial Services":
            print(f"  => Financial stock: PBR <= 0.5 required for buy")
            if pbr_naver is None:
                print(f"     [!] PBR fetch failed -> bot would print 'PBR 확인 불가. 패스합니다.' -> REJECTED")
            elif pbr_naver > 0.5:
                print(f"     PBR={pbr_naver} > 0.5 -> REJECTED (고평가)")
            else:
                print(f"     PBR={pbr_naver} <= 0.5 -> PASS (저평가 합격)")

    except Exception as e:
        print(f"  ERROR: {e}")
