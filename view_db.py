import sqlite3
import pandas as pd
from gap_stock_auto import load_db

# 최초 1회 실행을 강제하여 기존 json이 있다면 sqlite로 마이그레이션 되도록 트리거
load_db()

def view_database():
    db_file = 'gap_stock_auto.db'
    conn = sqlite3.connect(db_file)
    
    print("\n============ [현재 활성 포지션 (active_positions)] ============")
    try:
        df_active = pd.read_sql_query("SELECT * FROM active_positions", conn)
        if df_active.empty:
            print("현재 보유 중인 매수 포지션이 없습니다.")
        else:
            print(df_active.to_string(index=False))
    except Exception as e:
        print(f"조회 실패: {e}")
        
    print("\n============ [과거 매매 체결 이력 (trade_history)] ============")
    try:
        df_history = pd.read_sql_query("SELECT * FROM trade_history ORDER BY id DESC LIMIT 20", conn)
        if df_history.empty:
            print("아직 기록된 매매 체결 이력이 없습니다.")
        else:
            print(df_history.to_string(index=False))
    except Exception as e:
        print(f"조회 실패: {e}")
        
    conn.close()

if __name__ == "__main__":
    view_database()
