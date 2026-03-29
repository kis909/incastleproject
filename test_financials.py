import yfinance as yf
import pandas as pd

def check_net_income(sym):
    print(f"--- {sym} ---")
    ticker = yf.Ticker(sym)
    try:
        inc = ticker.income_stmt
        if 'Net Income' in inc.index:
            net_incomes = inc.loc['Net Income'].dropna()
            print("Net Incomes:")
            print(net_incomes)
            
            # Check last 3 years
            if len(net_incomes) >= 3:
                last_3 = net_incomes.iloc[:3]
                print(f"Last 3 years: {last_3.values}")
                is_all_negative = (last_3 < 0).all()
                print(f"Is negative for last 3 years? {is_all_negative}")
            else:
                print("Not enough data for 3 years")
        else:
            print("No 'Net Income' in income_stmt")
    except Exception as e:
        print(f"Error: {e}")

check_net_income('005930.KS')
check_net_income('085620.KS')
check_net_income('456160.KQ')
