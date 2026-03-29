import sqlite3, json

try:
    with open('gap_stock_auto_db.json', 'r', encoding='utf-8') as f:
        db = json.load(f)
    print('=== 현재 보유 포지션 (JSON DB) ===')
    for sym, info in db.items():
        print(f'종목: {sym}')
        print(f'  매수가: {info.get("buy_price", "?")}')
        print(f'  목표가: {info.get("target_price", "?")}')
        print(f'  MA5(저장): {info.get("ma5_yesterday", "?")}')
        print(f'  1차익절완료(scaled_out): {info.get("scaled_out", False)}')
        print()
except Exception as e:
    print(f'JSON DB 오류: {e}')

try:
    conn = sqlite3.connect('gap_stock_auto.db')
    c = conn.cursor()
    c.execute('PRAGMA table_info(active_positions)')
    cols = [col[1] for col in c.fetchall()]
    c.execute('SELECT * FROM active_positions')
    rows = c.fetchall()
    conn.close()
    print('=== SQLite DB (active_positions) ===')
    print('컬럼:', cols)
    for r in rows:
        d = dict(zip(cols, r))
        for k, v in d.items():
            print(f'  {k}: {v}')
        print()
except Exception as e:
    print(f'SQLite 오류: {e}')
