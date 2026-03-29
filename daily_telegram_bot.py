import os
import sys
import io
import time
import datetime
import schedule
import requests

import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import FinanceDataReader as fdr
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures

# Windows 환경에서 콘솔 출력 시 이모지 등의 유니코드 에러 방지 (버퍼링 해제)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

# Matplotlib 한글 폰트 설정 (Windows 기준 맑은 고딕)
plt.rc('font', family='Malgun Gothic')
plt.rcParams['axes.unicode_minus'] = False

# 텔레그램 설정 파일 로드 함수
def load_telegram_config(file_path):
    config = {}
    if not os.path.exists(file_path):
        print(f"설정 파일({file_path})이 없습니다.")
        return config
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                config[key.strip()] = value.strip()
    return config

# 텔레그램 메시지 전송 함수 (다중 전송 지원)
def send_telegram_message(token, chat_ids, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chat_id in chat_ids:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 텔레그램 메세지 전송 성공! (ID: {chat_id})")
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 텔레그램 메세지 전송 실패 (ID: {chat_id}): {e}")

# (차트/이미지 발송 기능 제거됨)

# 봇과 대화한 모든 유저(Chat ID) 목록 가져오기 함수
def get_all_chat_ids(token, config_chat_id=None):
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    chat_ids = set()
    
    # 설정 파일에 지정된 기본 ID가 있다면 포함 (쉼표로 여러 개 지원)
    if config_chat_id and config_chat_id != "이곳에_채팅방_아이디를_입력하세요":
        for cid in str(config_chat_id).split(','):
            chat_ids.add(cid.strip())
        
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data.get("ok"):
            for result in data.get("result", []):
                # 메시지를 보낸 사람의 챗 아이디 추출
                if "message" in result and "chat" in result["message"]:
                    chat_id = str(result["message"]["chat"]["id"])
                    chat_ids.add(chat_id)
                elif "my_chat_member" in result:
                    chat_id = str(result["my_chat_member"]["chat"]["id"])
                    chat_ids.add(chat_id)
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 챗 ID 목록 가져오기 실패: {e}")
        
    return list(chat_ids)

# 주식 데이터 가져오기 (지수용)
def get_index_info(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="2d")
        if len(hist) < 2: return 0.0, 0.0
        prev_close = float(hist['Close'].iloc[0])
        current_close = float(hist['Close'].iloc[1])
        change_rate = ((current_close - prev_close) / prev_close) * 100
        return current_close, change_rate
    except:
        return 0.0, 0.0

# 오늘이 코스피 개장일인지 확인 (최근 거래일이 오늘과 같은지 체크)
def is_trading_day():
    try:
        ticker = yf.Ticker('^KS11')
        hist = ticker.history(period="1d")
        if hist.empty:
            return False
            
        latest_date = hist.index[-1].date()
        today_date = datetime.datetime.now().date()
        return latest_date == today_date
    except Exception as e:
        print(f"개장일 확인 실패: {e}")
        # 오류가 나면 일단 전송하도록 True 반환
        return True

# 1. 기술적 분석 스코어링 로직 (MA, RSI, MACD, BB, Vol)
def calc_ta_score(df):
    if len(df) < 60: return 0, []
    score = 0
    details = []
    close = df['Close']
    vol = df['Volume']
    
    # 1. MA (20점)
    ma5, ma20, ma60 = close.rolling(5).mean(), close.rolling(20).mean(), close.rolling(60).mean()
    if ma5.iloc[-1] > ma20.iloc[-1] and ma20.iloc[-1] >= ma20.iloc[-2]:
        score += 20
        details.append("단기이평선 회복(정배열 초입)")
        
    # 2. RSI (20점; 30일 기준)
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=29, adjust=False).mean()
    ema_down = down.ewm(com=29, adjust=False).mean()
    rs = ema_up / ema_down
    rsi = 100 - (100 / (1 + rs))
    if rsi.iloc[-1] > 30 and rsi.iloc[-1] < 70 and rsi.iloc[-1] > rsi.iloc[-2]:
        score += 20
        details.append("RSI(30) 상승모멘텀")
        
    # 3. MACD (20점)
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    if hist.iloc[-1] > 0 and hist.iloc[-1] > hist.iloc[-2]:
        score += 20
        details.append("MACD 강세전환")
        
    # 4. Bollinger Bands (20점)
    std20 = close.rolling(20).std()
    lower_bb = ma20 - 2 * std20
    if df['Low'].iloc[-3:].min() <= lower_bb.iloc[-3:].max():
        if close.iloc[-1] > df['Open'].iloc[-1]: # 양봉 반등
            score += 20
            details.append("볼린저밴드 하단반등")
            
    # 5. Volume (20점)
    vol_ma5 = vol.rolling(5).mean()
    if vol.iloc[-1] >= vol_ma5.iloc[-2] * 1.5: # 2.0에서 1.5로 완화
        score += 20
        details.append("거래량 1.5배 급증")
        
    return score, details

# 2. 최신 뉴스 요약 가져오기 (24시간 이내의 뉴스만 필터링, 모바일 API 활용)
def fetch_news_and_sentiment(code):
    url = f"https://m.stock.naver.com/api/news/stock/{code}?pageSize=10&page=1"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    news_summary = []
    score = 0
    now = datetime.datetime.now()
    pos_keywords = ['상승', '급등', '수주', '돌파', '흑자', '최대', '호실적', '상향', '기대', '호재', '성장', '강세', '수혜', 'MOU', '체결']
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        data = res.json()
        
        if not data:
            return {'score': 0, 'text': "      - 관련 최신 뉴스 없음"}
            
        for group in data:
            if 'items' not in group: continue
            for item in group['items']:
                title = item.get('title', '').replace('\n', ' ')
                dt_str = item.get('datetime', '') # Format: YYYYMMDDHHmm
                try:
                    if dt_str:
                        news_time = datetime.datetime.strptime(dt_str, '%Y%m%d%H%M')
                        if (now - news_time).total_seconds() <= 24 * 3600:
                            for kw in pos_keywords:
                                if kw in title:
                                    score += 1
                            if len(news_summary) < 3:
                                news_summary.append(f"      - {title}")
                except Exception:
                    pass
                if len(news_summary) >= 3:
                    break
            if len(news_summary) >= 3:
                break
                
        if not news_summary:
            return {'score': 0, 'text': "      - 최근 24시간 이내 게재된 이슈 없음"}
            
        return {'score': score, 'text': "\n".join(news_summary)}
    except Exception as e:
        return {'score': 0, 'text': f"      - 뉴스 수집 실패 ({e})"}

# 3. 네이버 금융 시가총액 상위 종목 크롤링 (각 200종목, 총 400종목)
def get_top_tickers_from_naver():
    headers = {"User-Agent": "Mozilla/5.0"}
    symbols = []
    symbol_to_name = {}
    symbol_to_code = {}
    
    # sosok=0 (코스피), sosok=1 (코스닥)
    for sosok, suffix in [(0, '.KS'), (1, '.KQ')]:
        count = 0
        for page in range(1, 5): # 1~4페이지 (50개씩 200개)
            url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
            try:
                res = requests.get(url, headers=headers)
                soup = BeautifulSoup(res.text, 'lxml')
                links = soup.select('a.tltle')
                
                for link in links:
                    if count >= 200:
                        break
                    
                    name = link.text.strip()
                    code = link['href'].split('code=')[-1]
                    yf_sym = f"{code}{suffix}"
                    
                    if yf_sym not in symbols:
                        symbols.append(yf_sym)
                        symbol_to_name[yf_sym] = name
                        symbol_to_code[yf_sym] = code
                        count += 1
            except Exception as e:
                print(f"네이버 금융 크롤링 실패 (sosok={sosok}, page={page}): {e}")
                
            if count >= 200:
                break
            
    return symbols, symbol_to_name, symbol_to_code

def run_real_quant_analysis():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] KOSPI/KOSDAQ 데이터 로딩 중 (시총 상위 400종목)...")
    symbols, symbol_to_name, symbol_to_code = get_top_tickers_from_naver()
    
    if not symbols:
        print("종목 목록을 불러오지 못했습니다.")
        return "종목 목록 로드 실패", ""
        
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {len(symbols)}개 종목 주가 6개월 치 병렬 다운로드...")
    # download multi-ticker data (진행률 표시 활성화)
    data = yf.download(symbols, period="6mo", group_by="ticker", progress=True)
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 400개 종목 뉴스 및 감성점수 병렬 수집 중...")
    news_dict = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_news_and_sentiment, c): s for s, c in symbol_to_code.items()}
        for future in concurrent.futures.as_completed(futures):
            sym = futures[future]
            try:
                news_dict[sym] = future.result()
            except Exception as e:
                news_dict[sym] = {'score': 0, 'text': f"      - 뉴스 수집 실패 ({e})"}
    
    results_ta = []
    results_news = []
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 기술적 지표 계산 및 채점 중...")
    
    for sym in symbols:
        try:
            df = data[sym].dropna() if len(symbols) > 1 else data.dropna()
            if len(df) < 60: continue
            
            curr_p = float(df['Close'].iloc[-1])
            prev_p = float(df['Close'].iloc[-2])
            chg = ((curr_p - prev_p) / prev_p) * 100
            n_info = news_dict.get(sym, {'score': 0, 'text': "      - 뉴스 정보 없음"})

            score, details = calc_ta_score(df)
            # 기술적 지표 허들 대폭 완화: 지표 중 1개(20점)만 만족해도 후보군 진입
            if score >= 20: 
                results_ta.append({
                    'symbol': sym,
                    'name': symbol_to_name[sym],
                    'code': symbol_to_code[sym],
                    'ta_score': score,
                    'ta_details': details,
                    'price': curr_p,
                    'change': chg,
                    'news_text': n_info['text']
                })
                
            if n_info['score'] > 0:
                results_news.append({
                    'symbol': sym,
                    'name': symbol_to_name[sym],
                    'code': symbol_to_code[sym],
                    'news_score': n_info['score'],
                    'price': curr_p,
                    'change': chg,
                    'news_text': n_info['text']
                })
        except:
            pass
            
    # 기술적 점수순 정렬 후 상위 10개 추출
    results_ta.sort(key=lambda x: x['ta_score'], reverse=True)
    final_buy_ta = results_ta[:10]
    
    # 긍정 뉴스 점수 기준 Top 10 추출 (동점 시 상승률 높은 순)
    results_news.sort(key=lambda x: (x['news_score'], x['change']), reverse=True)
    final_buy_news = results_news[:10]
            
    # 지수 가져오기
    kospi_c, kospi_chg = get_index_info('^KS11')
    kosdaq_c, kosdaq_chg = get_index_info('^KQ11')
    
    kospi_str = f"{kospi_c:,.2f} ({'+' if kospi_chg > 0 else ''}{kospi_chg:.2f}%)"
    kosdaq_str = f"{kosdaq_c:,.2f} ({'+' if kosdaq_chg > 0 else ''}{kosdaq_chg:.2f}%)"
    
    # 텔레그램 마크다운 구성
    report_ta = f"🚀 *INCASTLE 시장분석 (Top 10)*\n\n"
    report_ta += f"*Date*: {time.strftime('%Y-%m-%d')} (KST)\n\n"
    report_ta += f"📊 *Market Daily Close*\n* KOSPI: {kospi_str}\n* KOSDAQ: {kosdaq_str}\n\n"
    
    report_ta += f"🎯 *투자 적합 기술적 반등 Top 10 종목*\n"
    if not final_buy_ta:
        report_ta += "조건을 완벽히 만족하는 종목이 오늘은 없습니다.\n\n"
    else:
        for idx, c in enumerate(final_buy_ta, 1):
            report_ta += f"{idx}. *{c['name']}* ({c['code']}) - TA: {c['ta_score']}점\n"
            detail_lines = ", ".join(c['ta_details']) if c['ta_details'] else "없음"
            report_ta += f"   ✅ [만족조건]: {detail_lines}\n"
            report_ta += f"   💰 종가: {c['price']:,.0f}원 ({'+' if c['change'] > 0 else ''}{c['change']:.2f}%)\n"
            report_ta += f"   📰 최근 24H 헤드라인:\n{c['news_text']}\n\n"
            
    report_news = f"🔥 *금일 긍정 뉴스 모멘텀 Top 10 종목*\n\n"
    if not final_buy_news:
        report_news += "긍정적인 뉴스가 포착된 종목이 없습니다.\n\n"
    else:
        for idx, c in enumerate(final_buy_news, 1):
            report_news += f"{idx}. *{c['name']}* ({c['code']}) - 긍정 키워드: {c['news_score']}회\n"
            report_news += f"   💰 종가: {c['price']:,.0f}원 ({'+' if c['change'] > 0 else ''}{c['change']:.2f}%)\n"
            report_news += f"   📰 주요 호재성 뉴스:\n{c['news_text']}\n\n"
        
    return report_ta, report_news

def daily_job():
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 정규 분석 스케줄러 실행 시작.")
    
    if not is_trading_day():
        print("오늘은 휴장일이므로 종목 분석 및 메시지 전송을 건너뜁니다.")
        return
        
    config = load_telegram_config('telegram_config.txt')
    token = config.get('TELEGRAM_BOT_TOKEN')
    config_chat_id = config.get('TELEGRAM_CHAT_ID')
    
    if not token or token.startswith('이곳에'):
        print("오류: 텔레그램 봇 토큰이 올바르지 않습니다.")
        return

    # 봇에게 메세지를 보낸 적이 있는 모든 챗 ID 수집
    chat_ids = get_all_chat_ids(token, config_chat_id)
    if not chat_ids:
        print("오류: 메시지를 보낼 대상(Chat ID)이 없습니다. 봇에게 먼저 메시지를 보내주세요.")
        return
        
    print(f"총 {len(chat_ids)}명의 유저/채널에게 리포트를 발송할 예정입니다.")

    # 실제 분석 실행
    report_ta, report_news = run_real_quant_analysis()
    
    # 텔레그램 전송 (모두에게)
    # 메시지 길이 제한을 위해 2번으로 나눠서 발송
    send_telegram_message(token, chat_ids, report_ta)
    send_telegram_message(token, chat_ids, report_news)

if __name__ == "__main__":
    print("===================================================")
    print("📈 Antigravity 텔레그램 자동 분석 봇 (Real-time Ver.) 📈")
    print("===================================================")
    
    # 지금 바로 테스트 실행
    #daily_job()

    # С케줄 등록 (매일 18:00)
    schedule.every().day.at("18:00").do(daily_job)

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n스케줄러가 종료되었습니다.")
