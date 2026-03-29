import sqlite3
import yfinance as yf
import datetime

# ============================================================
# 수동 매수 종목을 DB에 등록하는 스크립트
# 아래 MANUAL_ENTRIES에 매수하신 내용을 직접 입력해주세요.
# ============================================================

MANUAL_ENTRIES = [
    {
        "symbol": "329180",         # 덕산네오룩스 종목코드 (KIS 6자리)
        "symbol_yf": "329180.KS",   # yfinance 형식
        "buy_price": 0,             # ← 실제 매수 단가 입력 (0이면 yfinance 종가로 추정)
        "buy_date": "2026-03-19",   # 매수일
        "scaled_out": 0,            # 0=1차익절전, 1=1차익절완료
    },
    {
        "symbol": "036830",         # 솔브레인홀딩스 종목코드 (KIS 6자리)
        "symbol_yf": "036830.KQ",   # yfinance 형식 (코스닥이면 .KQ)
        "buy_price": 0,
        "buy_date": "2026-03-19",
        "scaled_out": 0,
    },
]

db_path = "gap_stock_auto.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

for entry in MANUAL_ENTRIES:
    sym = entry["symbol"]
    sym_yf = entry["symbol_yf"]
    buy_date = entry["buy_date"]
    scaled_out = entry["scaled_out"]
    
    # 이미 존재하면 스킵
    c.execute("SELECT symbol FROM active_positions WHERE symbol=?", (sym,))
    if c.fetchone():
        print(f"[SKIP] {sym} 이미 DB에 존재합니다.")
        continue
    
    # yfinance에서 최근 데이터 가져오기
    print(f"\n[{sym}] yfinance({sym_yf}) 데이터 조회 중...")
    ticker = yf.Ticker(sym_yf)
    hist = ticker.history(period="10d")
    
    if hist is None or len(hist) < 2:
        print(f"  !! yfinance 데이터 없음. .KS/.KQ 반대로 시도합니다.")
        alt = sym_yf.replace(".KS", ".KQ") if ".KS" in sym_yf else sym_yf.replace(".KQ", ".KS")
        ticker = yf.Ticker(alt)
        hist = ticker.history(period="10d")
        if hist is None or len(hist) < 2:
            print(f"  !! 데이터를 가져올 수 없습니다. 수동으로 입력하세요.")
            continue
    
    # 가장 최근 종가 = 매수가 (0이면 추정)
    buy_price = entry["buy_price"]
    if buy_price == 0:
        buy_price = float(hist['Close'].iloc[-1])
        print(f"  매수가 자동 추정: {buy_price:,.0f}원 (최근 종가 기준)")
    
    # 전전일 저가 = 1차 익절 목표가  
    # 매수일 기준 전일 저가를 사용
    target_price = float(hist['Low'].iloc[-2])
    print(f"  목표가(전일저가): {target_price:,.0f}원")
    
    # 5일선 (실시간 MA5)
    ma5 = float(hist['Close'].iloc[-5:].mean())
    print(f"  현재 MA5: {ma5:,.0f}원")
    
    c.execute("""
        INSERT INTO active_positions (symbol, buy_date, buy_price, target_price, ma5_yesterday, scaled_out)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (sym, buy_date, buy_price, target_price, ma5, scaled_out))
    
    print(f"  ✅ [{sym}] DB 등록 완료!")
    print(f"     매수가: {buy_price:,.0f}원 | 목표가(1차익절): {target_price:,.0f}원 | MA5: {ma5:,.0f}원")

conn.commit()
conn.close()

print("\n=== 최종 DB 상태 ===")
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT * FROM active_positions")
rows = c.fetchall()
conn.close()
for r in rows:
    print(f"  {r[0]} | 매수일:{r[1]} | 매수가:{r[2]:,.0f} | 목표가:{r[3]:,.0f} | MA5:{r[4]:,.0f} | 1차익절:{bool(r[5])}")
