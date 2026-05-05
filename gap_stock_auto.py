import os
import json
import time
import datetime
import requests
import pandas as pd
import yfinance as yf
import sqlite3
from daily_telegram_bot import get_top_tickers_from_naver


def ts():
    """현재 시각 문자열 반환 (로그 타임스탬프용)"""
    return datetime.datetime.now().strftime('[%Y-%m-%d %H:%M:%S]')

# ----------------- KIS API 설정 및 토큰 관리 -----------------
CONFIG_FILE = "kis_secret.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"{CONFIG_FILE} 파일이 없습니다. 발급받은 키를 템플릿에 입력해주세요.")
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

cfg = load_config()
APP_KEY = cfg["APP_KEY"]
APP_SECRET = cfg["APP_SECRET"]
CANO = cfg["CANO"]
ACNT_PRDT_CD = cfg["ACNT_PRDT_CD"]
URL_BASE = cfg["URL_BASE"]

def get_access_token():
    TOKEN_FILE = "kis_token.json"
    
    # 1. 파일에 토큰이 저장되어 있는지, 유효한지 1차 확인 (토큰 유효기간: 24시간)
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                t_data = json.load(f)
            # 유효 기간이 1시간 이상 남았으면 기존 토큰 재사용 (발급 빈도 제한 우회)
            if datetime.datetime.strptime(t_data['expired'], "%Y-%m-%d %H:%M:%S") > datetime.datetime.now() + datetime.timedelta(hours=1):
                return t_data['access_token']
        except Exception:
            pass

    # 2. 신규 발급 진행
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }
    url = f"{URL_BASE}/oauth2/tokenP"
    res = requests.post(url, headers=headers, data=json.dumps(body))
    
    # 403, 400 등의 오류 코드가 반환되면 명확하게 예외 처리
    if res.status_code != 200:
        raise Exception(f"토큰 발급 실패 (상태코드: {res.status_code}), {res.text}")
        
    data = res.json()
    token = data["access_token"]
    expired = data.get("access_token_token_expired")
    
    with open(TOKEN_FILE, 'w') as f:
        json.dump({'access_token': token, 'expired': expired}, f)
        
    return token

def hashkey(datas):
    """ POST 요청 시 필요한 해시키 발급 """
    headers = {
        'content-Type': 'application/json',
        'appKey': APP_KEY,
        'appSecret': APP_SECRET,
    }
    url = f"{URL_BASE}/uapi/hashkey"
    res = requests.post(url, headers=headers, data=json.dumps(datas))
    res.raise_for_status()
    return res.json()["HASH"]

# ----------------- KIS API 주요 기능 -----------------
def kis_api_request(method, url, **kwargs):
    """ KIS API 요청 공통 핸들러 (재시도 및 타임아웃 처리) """
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 15
    
    for i in range(3):
        try:
            if method.upper() == 'GET':
                res = requests.get(url, **kwargs)
            else:
                res = requests.post(url, **kwargs)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            if i < 2:
                print(f"{ts()} API 통신 에러... {i+1}차 재시도 중: {e}")
                time.sleep(2)
            else:
                print(f"{ts()} API 통신 최종 실패: {e}")
    return None

def get_current_price(token, symbol):
    """ 특정 종목의 현재 실시간 현재가, 고가 조회 """
    symbol_code = symbol.replace(".KS", "").replace(".KQ", "")
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appKey": APP_KEY,
        "appSecret": APP_SECRET,
        "tr_id": "FHKST01010100"
    }
    url = f"{URL_BASE}/uapi/domestic-stock/v1/quotations/inquire-price"
    params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": symbol_code}
    
    data = kis_api_request('GET', url, headers=headers, params=params)
    if data and data.get('rt_cd') == '0':
        return {
            'close': int(data['output']['stck_prpr']),
            'high': int(data['output']['stck_hgpr'])
        }
    return None

def get_account_balance(token):
    """ 계좌 증거금 및 현금 잔고 조회 """
    is_mock = "openapivts" in URL_BASE
    tr_id = "VTTC8434R" if is_mock else "TTTC8434R"
    
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appKey": APP_KEY,
        "appSecret": APP_SECRET,
        "tr_id": tr_id
    }
    url = f"{URL_BASE}/uapi/domestic-stock/v1/trading/inquire-balance"
    params = {
        "CANO": CANO, "ACNT_PRDT_CD": ACNT_PRDT_CD, "AFHR_FLPR_YN": "N", "OFL_YN": "",
        "INQR_DVSN": "02", "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01", "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""
    }
    
    data = kis_api_request('GET', url, headers=headers, params=params)
    if data and data.get('rt_cd') == '0' and data.get('output2'):
        row = data['output2'][0]
        cash = 0
        if 'ord_psbl_cash' in row:
            cash = int(row['ord_psbl_cash'])
        elif 'prvs_rcdl_excc_amt' in row:
            cash = int(row['prvs_rcdl_excc_amt'])
        elif 'dnca_tot_amt' in row:
            cash = int(row['dnca_tot_amt'])
            
        total_asset = int(row.get('tot_evlu_amt', cash))
        return cash, total_asset
    return 0, 0

def get_my_positions(token):
    """ 현재 보유 종목 목록 조회 """
    is_mock = "openapivts" in URL_BASE
    tr_id = "VTTC8434R" if is_mock else "TTTC8434R"
    
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appKey": APP_KEY,
        "appSecret": APP_SECRET,
        "tr_id": tr_id 
    }
    url = f"{URL_BASE}/uapi/domestic-stock/v1/trading/inquire-balance"
    params = {
        "CANO": CANO, "ACNT_PRDT_CD": ACNT_PRDT_CD, "AFHR_FLPR_YN": "N", "OFL_YN": "",
        "INQR_DVSN": "01", "UNPR_DVSN": "01", "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "01", "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""
    }
    
    data = kis_api_request('GET', url, headers=headers, params=params)
    positions = []
    if data and data.get('rt_cd') == '0' and data.get('output1'):
        for item in data['output1']:
            if int(item['hldg_qty']) > 0:
                positions.append({
                    'symbol': item['pdno'],
                    'qty': int(item['hldg_qty']),
                    'buy_price': float(item['pchs_avg_pric'])
                })
    return positions

def send_order(token, buy_sell, symbol_code, qty, price=0):
    """ 지정가/시장가 매매 주문 (price=0 이면 시장가) """
    is_mock = "openapivts" in URL_BASE
    if buy_sell == "BUY":
        tr_id = "VTTC0802U" if is_mock else "TTTC0802U"
    else:
        tr_id = "VTTC0801U" if is_mock else "TTTC0801U"
        
    ord_dvsn = "01" if price == 0 else "00" # 01: 시장가, 00: 지정가
    
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appKey": APP_KEY,
        "appSecret": APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P"
    }
    body = {
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "PDNO": symbol_code,
        "ORD_DVSN": ord_dvsn,
        "ORD_QTY": str(qty),
        "ORD_UNPR": str(price)
    }
    headers["hashkey"] = hashkey(body)
    
    url = f"{URL_BASE}/uapi/domestic-stock/v1/trading/order-cash"
    data = kis_api_request('POST', url, headers=headers, data=json.dumps(body))
    
    if data and data.get('rt_cd') == '0':
        print(f"{ts()} [{buy_sell}] 체결 성공! 종목:{symbol_code}, 수량:{qty}, 결과:{data['msg1']}")
        return True
    else:
        msg = data.get('msg1', '통신 실패') if data else '응답 없음'
        print(f"{ts()} [{buy_sell}] 체결 실패! 사유: {msg}")
        return False

# ----------------- 투자 전략 및 메인 루프 -----------------
def analyze_targets():
    """ yfinance로 히스토리컬 데이터를 불러와 갭하락+MA120 조건에 부합하는 후보군 추출 """
    print(f"{ts()} [분석] 네이버/yfinance 기반 400종목 최신 기술적 분석 중...")
    symbols, symbol_to_name, _ = get_top_tickers_from_naver()
    
    # ── 우선주 / ETF 필터링 ──────────────────────────────────────────
    ETF_KEYWORDS = ['KODEX', 'TIGER', 'KBSTAR', 'ARIRANG', 'KOSEF', 'HANARO',
                    'TIMEFOLIO', 'TREX', 'PLUS', 'ACE', '인덱스', 'ETF']

    def is_preferred(sym):
        """우선주 판별: KIS 코드 6자리의 마지막 숫자가 5이면 우선주"""
        code = sym.replace('.KS', '').replace('.KQ', '')
        return len(code) == 6 and code[-1] == '5'

    def is_etf(sym):
        """ETF 판별: 종목명에 ETF 브랜드 키워드 포함 여부"""
        name = symbol_to_name.get(sym, '')
        return any(kw in name for kw in ETF_KEYWORDS)

    before = len(symbols)
    symbols = [s for s in symbols if not is_preferred(s) and not is_etf(s)]
    print(f"{ts()} [필터] 우선주/ETF 제외: {before}종목 → {len(symbols)}종목 (개별 보통주만 매매)")
    # ────────────────────────────────────────────────────────────────
    
    end_date = datetime.date.today() + datetime.timedelta(days=1)
    start_date = end_date - datetime.timedelta(days=200) # 120일선 계산을 위해 200일 치
    
    data = yf.download(symbols, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), group_by="ticker", progress=False)
    
    # yfinance 당일/전일 데이터 누락 버그 필터링을 위한 기준 날짜 (코스피 1위 삼성전자)
    try:
        benchmark_dates = data['005930.KS'].dropna().index[-2:]
    except:
        benchmark_dates = None
        
    candidates = []
    
    for sym in symbols:
        try:
            df = data[sym].dropna()
            if len(df) < 120: continue
            
            # 삼성전자의 최신 2일 날짜와 일치하지 않으면 데이터 누락 지연 버그로 간주하고 패스
            if benchmark_dates is not None and len(benchmark_dates) == 2:
                if len(df.index) < 2 or len(df.index[-2:]) != 2: continue
                if not (df.index[-2:] == benchmark_dates).all():
                    continue
            
            prev_close = df['Close'].iloc[-2]
            prev_low = df['Low'].iloc[-2]
            
            ma60 = df['Close'].rolling(60).mean().iloc[-1]
            ma5 = df['Close'].rolling(5).mean().iloc[-1]
            
            candidates.append({
                'symbol_yf': sym,
                'symbol_kis': sym.replace(".KS", "").replace(".KQ", ""),
                'name': symbol_to_name.get(sym, ''),
                'prev_close': prev_close,
                'prev_low': prev_low,
                'ma60': ma60,
                'ma5_yesterday': ma5
            })
        except:
            pass
            
    return candidates


db_file = 'gap_stock_auto.db'

def init_db():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_positions (
        symbol TEXT PRIMARY KEY, buy_date TEXT, buy_price REAL,
        target_price REAL, ma5_yesterday REAL, scaled_out INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS trade_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, symbol TEXT,
        action TEXT, price REAL, qty INTEGER, memo TEXT)''')
    conn.commit()
    conn.close()

def log_trade(symbol, action, price, qty, memo=""):
    init_db()
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO trade_history (timestamp, symbol, action, price, qty, memo) VALUES (?, ?, ?, ?, ?, ?)",
                   (ts, symbol, action, price, qty, memo))
    conn.commit()
    conn.close()
    
    # 텍스트 로그 파일 기록 추가
    log_file = "trade_history.log"
    with open(log_file, "a", encoding="utf-8-sig") as f:
        log_line = f"[{ts}] {action} | 종목:{symbol} | 단가:{int(price):,}원 | 수량:{qty}주 | 총금액:{int(price*qty):,}원 | 비고:{memo}\n"
        f.write(log_line)

def load_db():
    init_db()
    
    # JSON 마이그레이션 (1회성)
    json_file = 'trading_db.json'
    if os.path.exists(json_file):
        try:
            with open(json_file, 'r') as f:
                old_db = json.load(f)
            save_db(old_db) # DB에 인서트
            os.rename(json_file, json_file + '.bak') # 백업 후 숨김 처리
            print(f"{ts()} [시스템] 기존 JSON DB를 SQLite DB로 마이그레이션 완료했습니다.")
        except Exception as e:
            print(f"{ts()} [시스템] DB 마이그레이션 실패: {e}")
            
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_positions")
    rows = cursor.fetchall()
    conn.close()
    
    result = {}
    for r in rows:
        result[r[0]] = {
            'buy_date': r[1], 'buy_price': r[2], 'target_price': r[3],
            'ma5_yesterday': r[4], 'scaled_out': bool(r[5])
        }
    return result

FINANCIAL_DB_FILE = "financial_db.json"

def load_financial_db():
    if os.path.exists(FINANCIAL_DB_FILE):
        try:
            with open(FINANCIAL_DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_financial_db(data):
    try:
        with open(FINANCIAL_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"재무 DB 저장 오류: {e}")

def save_db(db_dict):
    """DB 전체를 덮어쓰지 않고, 로우별 UPSERT로 안전하게 저장 (Race Condition 방지)"""
    init_db()
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    # 기존 DB에 없는 종목만 삭제 (SELL 완료된 항목 정리)
    existing = {r[0] for r in cursor.execute("SELECT symbol FROM active_positions").fetchall()}
    to_delete = existing - set(db_dict.keys())
    for sym in to_delete:
        cursor.execute("DELETE FROM active_positions WHERE symbol=?", (sym,))
    # 나머지는 UPSERT (업데이트 또는 삽입)
    for sym, d in db_dict.items():
        cursor.execute("""INSERT OR REPLACE INTO active_positions
            (symbol, buy_date, buy_price, target_price, ma5_yesterday, scaled_out)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (sym, d.get('buy_date', ''), d.get('buy_price', 0),
             d.get('target_price', 0), d.get('ma5_yesterday', 0),
             int(d.get('scaled_out', False))))
    conn.commit()
    conn.close()

def save_position(sym, data):
    """단일 종목만 즉시 DB에 저장 (매수 직후 원자적 기록)"""
    init_db()
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""INSERT OR REPLACE INTO active_positions
        (symbol, buy_date, buy_price, target_price, ma5_yesterday, scaled_out)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (sym, data.get('buy_date', ''), data.get('buy_price', 0),
         data.get('target_price', 0), data.get('ma5_yesterday', 0),
         int(data.get('scaled_out', False))))
    conn.commit()
    conn.close()

def get_realtime_ma5(sym_code, current_price=None):
    """
    실시간 5일 이동평균(MA5) 계산.
    - 과거 4일 종가(yfinance) + 오늘 현재가(KIS API) = 5개 값 평균
    - current_price 를 넘기면 오늘 실시간 가격이 MA5에 즉시 반영됨
    """
    for suffix in ['.KS', '.KQ']:
        try:
            ticker = yf.Ticker(sym_code + suffix)
            hist = ticker.history(period='20d')
            if hist is not None and len(hist) >= 4:
                past_4_closes = list(hist['Close'].iloc[-4:])  # 과거 4일 종가
                if current_price and current_price > 0:
                    five_values = past_4_closes + [current_price]  # 오늘 현재가 포함
                else:
                    five_values = list(hist['Close'].iloc[-5:])  # 현재가 없으면 5일 전체 과거
                ma5 = round(sum(five_values) / len(five_values), 0)
                return float(ma5)
        except Exception:
            continue
    return None


def count_trading_days_since(buy_date_str):
    """매수일로부터 오늘까지 거래일(영업일) 수를 반환한다.
    토·일요일을 제외한 평일 기준으로 계산 (공휴일은 단순화를 위해 평일로 처리).
    """
    try:
        buy_date = datetime.datetime.strptime(buy_date_str, "%Y-%m-%d").date()
    except Exception:
        return 0
    today = datetime.date.today()
    trading_days = 0
    current = buy_date
    while current < today:
        current += datetime.timedelta(days=1)
        if current.weekday() < 5:  # 0=월 ~ 4=금
            trading_days += 1
    return trading_days

def check_sells(token):
    print(f"{ts()} 실시간 매도/수익실현 모니터링 (KIS API 실시간 잔고 기준)...")
    trading_db = load_db()
    my_pos = get_my_positions(token)  # KIS API = 보유 종목의 진실(Source of Truth)
    
    if not my_pos:
        print(f"{ts()} 현재 보유 종목 없음. 모니터링 스킵.")
        # DB에도 없는 종목 정리
        if trading_db:
            save_db({})
        return
    
    current_symbols = {p['symbol'] for p in my_pos}
    
    # --- DB에는 있지만 KIS에 없는 종목 → 매도 완료, DB 정리 ---
    for k in list(trading_db.keys()):
        if k not in current_symbols:
            print(f"{ts()} [동기화] '{k}' KIS 잔고에 없음. DB에서 제거.")
            del trading_db[k]
    
    # --- KIS API 보유 종목 기준으로 루프 (DB 여부와 무관하게 모든 보유 종목 처리) ---
    for pos in my_pos:
        sym_code = pos['symbol']
        qty       = pos['qty']
        buy_price = pos['buy_price']  # KIS API 평균매수가 사용 (가장 정확)
        
        # DB에 없는 종목 자동 감지 및 등록 (수동매수 or 이전 DB 유실 종목)
        if sym_code not in trading_db:
            print(f"{ts()} [신규 감지] {sym_code} KIS에 있지만 DB에 없음. yfinance로 목표가 추정 후 자동 등록.")
            # yfinance로 전일 저가를 1차 익절 목표가로 추정
            target_est = buy_price * 1.03  # 기본값: 매수가 +3% (알 수 없을 때)
            for suffix in ['.KS', '.KQ']:
                try:
                    hist = yf.Ticker(sym_code + suffix).history(period='10d')
                    if hist is not None and len(hist) >= 2:
                        target_est = float(hist['Low'].iloc[-2])  # 전일 저가
                        break
                except Exception:
                    continue
            trading_db[sym_code] = {
                'buy_date': datetime.datetime.now().strftime("%Y-%m-%d"),
                'buy_price': buy_price,
                'target_price': target_est,
                'ma5_yesterday': 0.0,
                'scaled_out': False
            }
            save_position(sym_code, trading_db[sym_code])
            print(f"{ts()} [자동 등록] {sym_code} | 추정 목표가(전일저가): {target_est:,.0f}원")
        
        db_info      = trading_db[sym_code]
        target_price = db_info.get('target_price', buy_price * 1.03)
        scaled_out   = db_info.get('scaled_out', False)
        
        # KIS 실제 매입단가와 DB 저장 단가 자동 동기화
        db_buy_price = db_info.get('buy_price', 0)
        if db_buy_price == 0 or abs(db_buy_price - buy_price) > 1:  # 1원 이상 차이 시 동기화
            print(f"{ts()} [단가 동기화] {sym_code} DB:{db_buy_price:,.0f}원 → KIS 실제:{buy_price:,.0f}원 으로 업데이트")
            trading_db[sym_code]['buy_price'] = buy_price
            save_position(sym_code, trading_db[sym_code])
            db_info = trading_db[sym_code]  # 갱신된 db_info 반영
        
        rt_data = get_current_price(token, sym_code)
        time.sleep(0.2)
        if not rt_data:
            continue
        
        curr_price = rt_data['close']
        curr_high  = rt_data['high']
        
        # [신규] 모든 보유 종목에 대해 실시간 MA5 계산 후 DB 갱신 (GUI 연동 목적)
        ma5_live = get_realtime_ma5(sym_code, curr_price)
        if ma5_live is not None:
            # DB의 값과 다르면 업데이트 후 저장
            if db_info.get('ma5_yesterday', 0) != ma5_live:
                trading_db[sym_code]['ma5_yesterday'] = ma5_live
                save_position(sym_code, trading_db[sym_code])
        else:
            # 실시간 MA5 조회 실패 시 DB에 있는 가장 최근 값 사용
            ma5_live = db_info.get('ma5_yesterday', 0)
            print(f"{ts()} [{sym_code}] 실시간 MA5 조회 실패, DB 저장값({ma5_live:.0f}원) 사용")
        
        # ⏰ 20 거래일 타임스탑 (장기 횡보 종목 자본 효율성 개선)
        buy_date_str = db_info.get('buy_date', '')
        trading_days_held = count_trading_days_since(buy_date_str) if buy_date_str else 0
        if trading_days_held >= 20:
            print(f"{ts()} [타임스탑] {sym_code} 매수 후 {trading_days_held} 거래일 경과 ({buy_date_str}). 타겟 미도달로 전량 강제 시장가 청산!")
            success = send_order(token, "SELL", sym_code, qty, 0)
            if success:
                log_trade(sym_code, "SELL_TIMEOUT", curr_price, qty, f"20거래일 타임스탑 (보유 {trading_days_held}일)")
            if sym_code in trading_db:
                del trading_db[sym_code]
            continue
        
        # 하드 손절 (-10%, KIS 평균매수가 기준)
        if curr_price <= buy_price * 0.9:
            print(f"{ts()} [손절] {sym_code} -10% 터치 (매수가:{buy_price:,.0f} / 현재가:{curr_price:,.0f}). 전량 매도")
            success = send_order(token, "SELL", sym_code, qty, 0)
            if success:
                log_trade(sym_code, "SELL_STOPLOSS", curr_price, qty, "-10% 손절")
            if sym_code in trading_db:
                del trading_db[sym_code]
            continue

            
        # 1차 익절 (갭 메움: 당일 고가 >= 전일 저가)
        if not scaled_out and curr_high >= target_price:
            half_qty = max(1, qty - (qty // 2)) # 수량이 1개일 때 1개 전량 매도
            if half_qty > 0:
                print(f"{ts()} [1차 익절] {sym_code} 목표가({target_price:,.0f}원) 도달! {half_qty}주 시장가 매도")
                success = send_order(token, "SELL", sym_code, half_qty, 0)
                if success:
                    log_trade(sym_code, "SELL_SCALE_OUT", curr_price, half_qty, "1차 익절(목표가 도달)")
                if sym_code in trading_db:
                    if half_qty == qty:
                        del trading_db[sym_code]
                        print(f"{ts()} [{sym_code}] 전량 1차 익절 매도 완료로 관리 대상에서 제외")
                    else:
                        trading_db[sym_code]['scaled_out'] = True
                        save_position(sym_code, trading_db[sym_code])  # 즉시 저장
                
        # 2차 추세청산 (1차 익절 후, 현재가 < 실시간 MA5)
        elif scaled_out:
            print(f"{ts()} [{sym_code}] 실시간 MA5: {ma5_live:.0f}원 | 현재가: {curr_price:,}원")
            if curr_price < ma5_live:
                print(f"{ts()} [2차 추세청산] {sym_code} 5일선({ma5_live:.0f}원) 이탈. 남은 {qty}주 전량 매도")
                success = send_order(token, "SELL", sym_code, qty, 0)
                if success:
                    log_trade(sym_code, "SELL_TREND_EXIT", curr_price, qty, "2차 추세청산(MA5 이탈)")
                if sym_code in trading_db:
                    del trading_db[sym_code]
    
    save_db(trading_db)

def check_naver_net_income(code):
    import requests
    from bs4 import BeautifulSoup
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        tbody = soup.select_one('div.cop_analysis tbody')
        if not tbody:
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
            annual_incomes = []
            for td in tds[0:4]:
                text = td.text.strip().replace(',', '')
                if text and text != '-':
                    annual_incomes.append(int(float(text)))
            
            if len(annual_incomes) >= 3:
                last_3 = annual_incomes[-3:]
                # 최근 3년 중 한 번이라도 적자(<0)면 필터링 (True 반환)
                return any(v < 0 for v in last_3)
        return False
    except Exception:
        return False

def get_naver_pbr(code):
    import requests
    from bs4 import BeautifulSoup
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        pbr_tag = soup.select_one('#_pbr')
        if pbr_tag:
            return float(pbr_tag.text.replace(',', ''))
        return None
    except:
        return None

def check_naver_bad_news(stock_name):
    import requests
    from bs4 import BeautifulSoup
    import urllib.parse
    import datetime
    
    now = datetime.datetime.now()
    date_str = now.strftime('%Y.%m.%d')
    date_str_prev = (now - datetime.timedelta(days=1)).strftime('%Y.%m.%d')
    
    encoded_query = urllib.parse.quote(stock_name)
    url = f"https://search.naver.com/search.naver?where=news&query={encoded_query}&sm=tab_opt&sort=0&photo=0&field=0&pd=3&ds={date_str_prev}&de={date_str}&docid=&related=0&mynews=0&office_type=0&office_section_code=0&news_office_checked=&nso=so%3Ar%2Cp%3Afrom{date_str_prev.replace('.','')}to{date_str.replace('.','')}&is_sug_officeid=0"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            titles = soup.select('.news_tit')
            
            bad_keywords = ['유상증자', '횡령', '배임', '감자', '거래정지', '불성실공시', '하한가', '관리종목', '상장폐지', '어닝쇼크']
            for title in titles:
                text = title.get_text()
                for keyword in bad_keywords:
                    if keyword in text:
                        return True, text # 악재 발견
    except Exception:
        pass
    return False, ""

def execute_buys(token):
    print(f"{ts()} 15:10 종가 라스트 찬스! 갭메우기 후보 매수 타점 탐색...")
    trading_db = load_db()
    my_pos = get_my_positions(token)
    
    raw_cash, total_asset = get_account_balance(token)
    cash = max(0, raw_cash)
    
    # 미수/신용거래 방지: 주문 가능 현금이 최소 권장금액(약 1만원) 이하면 즉각 매수 포기
    if cash < 10000:
        print(f"{ts()} [매수 패스] 현재 남은 현금이 충분치 않아({cash:,}원), 미수/신용 방지를 위해 신규 매수를 건너뜁니다.")
        return
        
    # 각 종목별 예산: 총 자산의 25% 고정 (한도 내 종목 수 무제한)
    target_budget = total_asset * 0.25
        
    print(f"{ts()} 💰 [자산 확인] 총 자산: {total_asset:,}원 | 주문 가능 현금: {cash:,}원")
    print(f"{ts()} 🎯 [매수 준비] 종목당 투입 예산: {int(target_budget):,}원 (현금 한도 내 무한 매수)")
    
    candidates = analyze_targets()
    buy_count = 0
    
    financial_db = load_financial_db()
    financial_db_updated = False
    
    for item in candidates:
        if cash < 10000:
            print(f"{ts()} [매수 패스] 현금이 거의 소진되어 추가 매수를 종료합니다.")
            break
        if item['symbol_kis'] in [p['symbol'] for p in my_pos]: continue
        if item['symbol_kis'] in trading_db: continue  # 이미 처리중
        
        # [신규 추가] 실시간 악재 뉴스/공시 필터 (가짜 갭하락 회피)
        stock_name = item.get('name', '')
        if stock_name:
            print(f"{ts()} 🔍 [{stock_name}] 실시간 악재 뉴스 스캔 중...")
            has_bad_news, hl = check_naver_bad_news(stock_name)
            if has_bad_news:
                print(f"{ts()} 🚫 [매수 기각] {stock_name} 악재 발견 / 관련 뉴스: {hl}")
                continue # 악재 있으면 패스
        
        # 재무정보 캐싱 활용 (유효기간 14일)
        fin_info = financial_db.get(item['symbol_kis'])
        today_str = datetime.datetime.now().strftime('%Y-%m-%d')
        need_fetch = True
        
        if fin_info:
            last_date_str = fin_info.get('last_updated', '2000-01-01')
            try:
                last_date = datetime.datetime.strptime(last_date_str, '%Y-%m-%d')
                if (datetime.datetime.now() - last_date).days < 14:
                    need_fetch = False
            except Exception:
                pass
                
        if need_fetch:
            print(f"{ts()} 🌐 [{item['symbol_kis']}] 재무 데이터 API/크롤링 수집 중...")
            fin_info = {
                'sector': None,
                'pbr': None,
                'debt_ratio': None,
                'is_deficit': False,
                'last_updated': today_str
            }
            try:
                import yfinance as yf
                info = yf.Ticker(item['symbol_yf']).info
                fin_info['sector'] = info.get('sector')
                fin_info['debt_ratio'] = info.get('debtToEquity')
                if fin_info['sector'] == "Financial Services":
                    fin_info['pbr'] = get_naver_pbr(item['symbol_kis'])
                fin_info['is_deficit'] = check_naver_net_income(item['symbol_kis'])
                
                financial_db[item['symbol_kis']] = fin_info
                financial_db_updated = True
                time.sleep(0.5) # API Rate Limit 방어
            except Exception as e:
                print(f"{ts()} ⚠️ [{item['symbol_kis']}] 재무 데이터 수집 예외: {e}")
                
        if fin_info:
            sector = fin_info.get('sector')
            if sector == "Financial Services":
                pbr = fin_info.get('pbr')
                if pbr is None:
                    print(f"{ts()} 🚫 [필터링] {item['symbol_kis']} 금융주 본질가치(PBR) 확인 불가. 패스합니다.")
                    continue
                elif pbr > 0.5:
                    print(f"{ts()} 🚫 [필터링] {item['symbol_kis']} 금융주 PBR({pbr}배) 고평가로 가치주 필터 탈락. 패스합니다.")
                    continue
                else:
                    print(f"{ts()} ✅ [필터링] {item['symbol_kis']} 금융주 PBR({pbr}배) 저평가 합격!")
            else:
                dr = fin_info.get('debt_ratio')
                if dr is not None and float(dr) >= 200:
                    print(f"{ts()} 🚫 [필터링] {item['symbol_kis']} 부채비율 과다({dr:.1f}%)로 안정성 필터 탈락. 패스합니다.")
                    continue
            
            if fin_info.get('is_deficit'):
                print(f"{ts()} 🚫 [필터링] {item['symbol_kis']} 최근 3년 내 당기순이익 적자 기록 발견. 재무 안정성 미달로 패스합니다.")
                continue
        
        rt = get_current_price(token, item['symbol_kis'])
        time.sleep(0.2) # API 초당 요청 제한 방어
        if not rt: continue
        
        c_price = rt['close']
        c_high = rt['high']
        
        # 실제 매수 가능한 예산은 1종목당 공평 비중(타겟 예산)과 현재 남은 현금 중 작은 값
        actual_budget = min(target_budget, cash)
        
        # 현재가가 예산보다 높을 경우 매수 패스
        if c_price > actual_budget:
            print(f"{ts()} [{item['symbol_kis']}] 현재가({c_price:,})가 실 사용가능 예산({int(actual_budget):,}) 초과로 매수 패스")
            continue
            
        # Expert 퀀트 조건 적용 (갭하락 + 4% 하락 + MA60 위)
        is_gap_down = c_high < item['prev_low']
        is_drop_4pct = c_price <= (item['prev_close'] * 0.96)
        is_uptrend = c_price > item['ma60']
        
        if is_gap_down and is_drop_4pct and is_uptrend:
            buy_qty = int(actual_budget // c_price)
            if buy_qty > 0:
                print(f"{ts()} 💎 [매수 포착] {item['symbol_kis']} | 현재가:{c_price:,} | 타겟가:{item['prev_low']:,}")
                success = send_order(token, "BUY", item['symbol_kis'], buy_qty, 0)
                time.sleep(0.2) # 주문 직후 딜레이
                if success:
                    log_trade(item['symbol_kis'], "BUY", c_price, buy_qty, "갭하락 추세추종 매수")
                    pos_data = {
                        'buy_date': datetime.datetime.now().strftime("%Y-%m-%d"),
                        'buy_price': c_price,
                        'target_price': item['prev_low'],
                        'ma5_yesterday': item['ma5_yesterday'],
                        'scaled_out': False
                    }
                    trading_db[item['symbol_kis']] = pos_data
                    # 매수 즉시 DB에 원자적 저장 (Race Condition 방지 - check_sells 덮어쓰기 차단)
                    save_position(item['symbol_kis'], pos_data)
                    cash -= buy_qty * c_price
                    buy_count += 1

    if financial_db_updated:
        save_financial_db(financial_db)
                    
    save_db(trading_db)
    print(f"{ts()} [매수] 오늘의 갭메우기 매수 루틴 종료.")

def job_check_sells():
    """ 10분 단위 단기 매도 모니터링 """
    now = datetime.datetime.now()
    
    # 주말이면 봇 가동 중지
    if now.weekday() >= 5:
        return
        
    try:
        token = get_access_token()
    except Exception as e:
        print(f"{ts()} [오류] 매도 확인 중 토큰 발급 실패: {e}")
        return

    # 장중(09:00 ~ 15:20) 매 10분마다 매도 처리 진행
    if 9 <= now.hour <= 15:
        if now.hour == 15 and now.minute > 20:
            pass # 15:20 이후 동시호가 시간대 배제
        else:
            check_sells(token)

def job_execute_buys():
    """ 매일 15:10에 일괄 매수 탐색 루틴 """
    now = datetime.datetime.now()
    
    if now.weekday() >= 5:
        return
        
    try:
        token = get_access_token()
        execute_buys(token)
    except Exception as e:
        print(f"{ts()} [오류] 종가 배팅 중 토큰 발급 실패: {e}")

import schedule
def run_scheduler():
    print(f"{ts()} ==================================================")
    print(f"{ts()} 🚀 한국투자증권(KIS) 갭메우기 스케줄러 봇 시작 (모의/실전)")
    print(f"{ts()} ==================================================")
    
    # 1. API 접속 및 토큰 발급 테스트 수행
    try:
        print(f"{ts()} \n[시스템] KIS API 접속 상태 및 접근 권한 검사 중...")
        token = get_access_token()
        print(f"{ts()} ✅ [성공] 한국투자증권 API 통신 및 토큰 발급 완료.")
        
        # 계좌 조회 테스트
        cash, total_asset = get_account_balance(token)
        print(f"{ts()} 💰 [계좌 연동] 현재 주문 가능 현금: {cash:,}원\n")
    except Exception as e:
        print(f"{ts()} ❌ [실패] KIS API 접속에 실패했습니다. kis_secret.json 파일의 키 값이나 URL_BASE를 확인하세요.")
        print(f"{ts()}    오류 사유: {e}\n")
        return  # 연결 안 되면 봇 시작 안 함

    # 10분 단위로 매도 조건 등 모니터링
    schedule.every(10).minutes.do(job_check_sells)
    
    # 15:10 종가 매수를 위해 정해진 시각에 정확히 매수 스케쥴 체크
    schedule.every().day.at("15:10").do(job_execute_buys)
    
    print(f"{ts()} [알림] 장중 매 10분마다 매도 타점 점검, 오후 15시 10분에 일괄 당일 매수 탐색을 수행합니다.")
    print(f"{ts()} [알림] (주의) 시장 외의 시간에 구동하면 KIS 모의투자 정책상 주문 에러가 날 수 있습니다.")
    print(f"{ts()} [알림] 프로그램을 종료하시려면 Ctrl + C 를 누르세요.\n")
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    import importlib.util
    if importlib.util.find_spec("schedule") is None:
        print(f"{ts()} ❗ 'schedule' 모듈이 설치되어 있지 않습니다. pip install schedule 키워드로 먼저 설치해주세요.")
    else:
        run_scheduler()
