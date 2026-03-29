import sqlite3
import yfinance as yf
import datetime
import re
import os

db_file = "gap_stock_auto.db"
log_file = "trade_history.log"

if not os.path.exists(db_file):
    print("DB 파일이 없습니다.")
    exit(0)

conn = sqlite3.connect(db_file)
c = conn.cursor()
c.execute("SELECT symbol, buy_date, buy_price, target_price FROM active_positions")
rows = c.fetchall()

# Parse log for buy info
log_info = {}
if os.path.exists(log_file):
    with open(log_file, "r", encoding="utf-8-sig") as f:
        for line in f:
            if "BUY" in line and "종목:" in line:
                m_sym = re.search(r'종목:(\d+)', line)
                m_prc = re.search(r'단가:([\d,]+)원', line)
                m_date = re.search(r'\[(.*?) ', line)
                if m_sym and m_prc and m_date:
                    sym = m_sym.group(1)
                    prc = float(m_prc.group(1).replace(',', ''))
                    dt = m_date.group(1)
                    log_info[sym] = {'price': prc, 'date': dt}

for r in rows:
    sym, b_date, b_price, t_price = r
    print(f"\n[{sym}] DB 상태 - Date:{b_date}, Price:{b_price}, Target:{t_price}")
    
    # 1. 복구할 매수 날짜/가격
    if not b_price or b_price == 0:
        if sym in log_info:
            b_price = log_info[sym]['price']
            b_date = log_info[sym]['date']
            print(f"  -> 로그에서 매수 기록 발견: {b_date} / {b_price}원")
        else:
            print("  -> 로그에 매수 기록 없음. KIS 동기화 대기 필요.")
            
    # 2. 목표가 복구
    if not t_price or t_price == 0:
        print("  -> 목표가(target_price) 복구 시도 (yfinance)")
        for suf in ['.KS', '.KQ']:
            try:
                hist = yf.Ticker(sym+suf).history(period='20d')
                if len(hist) > 0:
                    # 매수일(b_date)의 전일 저가 찾기
                    hist.index = hist.index.tz_localize(None)
                    if b_date:
                        target_dt = datetime.datetime.strptime(b_date, "%Y-%m-%d").date()
                        prev_dates = [d for d in hist.index if d.date() < target_dt]
                        if prev_dates:
                            t_price = float(hist.loc[prev_dates[-1], 'Low'])
                            print(f"  -> 복구된 갭메우기 목표가: {t_price:,}원")
                            break
            except Exception as e:
                pass
                
    if b_price > 0 or t_price > 0:
        c.execute("UPDATE active_positions SET buy_date=?, buy_price=?, target_price=? WHERE symbol=?",
                  (b_date, b_price, t_price, sym))
        print("  => 업데이트 예약 완료.")

conn.commit()
conn.close()
print("\n[DB 복구] 완료되었습니다.")
