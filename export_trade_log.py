import sqlite3
import os

db_file = 'gap_stock_auto.db'
log_file = 'trade_history.log'

def export_db_to_log():
    if not os.path.exists(db_file):
        print(f"[오류] 데이터베이스 파일 '{db_file}' 이 없습니다.")
        return

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trade_history'")
    if not cursor.fetchone():
        print("[안내] 매매 내역(trade_history) 테이블이 비어있거나 생성되지 않았습니다.")
        conn.close()
        return

    cursor.execute("SELECT timestamp, action, symbol, price, qty, memo FROM trade_history ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("[안내] 기록된 매매 내역이 없습니다.")
        return

    with open(log_file, "w", encoding="utf-8-sig") as f:
        f.write("==================================================\n")
        f.write("      🚀 KIS 갭메우기 봇 매매(체결) 기록 로그\n")
        f.write("==================================================\n\n")
        
        for r in rows:
            ts, action, symbol, price, qty, memo = r
            total_amt = int(price * qty)
            log_line = f"[{ts}] {action} | 종목:{symbol} | 단가:{int(price):,}원 | 수량:{qty}주 | 총금액:{total_amt:,}원 | 비고:{memo}\n"
            f.write(log_line)
            
    print(f"[성공] 총 {len(rows)}건의 매매 내역이 '{log_file}' 파일로 성공적으로 추출되었습니다!")

if __name__ == "__main__":
    export_db_to_log()
