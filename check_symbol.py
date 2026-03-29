import yfinance as yf
import datetime
import pandas as pd

sym = '456160.KQ'
end_date = datetime.date.today() + datetime.timedelta(days=1)
start_date = end_date - datetime.timedelta(days=200)

df = yf.download(sym, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), progress=False)

if not df.empty:
    print(df.tail(5))
    
    prev_close = df['Close'].iloc[-2]
    prev_low = df['Low'].iloc[-2]
    ma120 = df['Close'].rolling(120).mean().iloc[-1]
    last_close = df['Close'].iloc[-1]
    last_high = df['High'].iloc[-1]
    
    print("\n--- 봇 조건(analyze_targets) 시뮬레이션 ---")
    print(f"전일 저가 (prev_low): {prev_low}")
    print(f"당일 고가 (c_high): {last_high}")
    print(f"전일 종가 (prev_close): {prev_close}")
    print(f"당일 종가 (c_price): {last_close}")
    print(f"MA120: {ma120}")
    
    is_gap_down = prev_low > last_high
    is_drop_5pct = last_close <= (prev_close * 0.95)
    is_uptrend = last_close > ma120
    print(f"\nCondition 1 (Gap Down: prev_low > c_high): {is_gap_down}")
    print(f"Condition 2 (Drop > 5%: c_price <= prev_close * 0.95): {is_drop_5pct}")
    print(f"Condition 3 (Uptrend: c_price > ma120): {is_uptrend}")
else:
    print("Data empty.")
