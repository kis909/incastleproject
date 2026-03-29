import os
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# 실전 봇과 동일한 모듈 임포트
from daily_telegram_bot import get_top_tickers_from_naver

START_DATE = "2021-01-01"
END_DATE = "2025-12-31"
INITIAL_CAPITAL = 400_000        # 기본 투자금 40만 원
MONTHLY_CONTRIBUTION = 0    # 매월 추가 투입금 0원
REPORT_FILENAME = "backtest_report_no_contrib.txt"

def get_live_universe():
    print("실전 봇과 동일한 방식으로 네이버 400종목 유니버스를 구성합니다...")
    symbols, symbol_to_name, _ = get_top_tickers_from_naver()
    
    ETF_KEYWORDS = ['KODEX', 'TIGER', 'KBSTAR', 'ARIRANG', 'KOSEF', 'HANARO',
                    'TIMEFOLIO', 'TREX', 'PLUS', 'ACE', '인덱스', 'ETF']

    def is_preferred(sym):
        code = sym.replace('.KS', '').replace('.KQ', '')
        return len(code) == 6 and code[-1] == '5'

    def is_etf(sym):
        name = symbol_to_name.get(sym, '')
        return any(kw in name for kw in ETF_KEYWORDS)

    before = len(symbols)
    symbols = [s for s in symbols if not is_preferred(s) and not is_etf(s)]
    print(f"[필터] 우선주/ETF 제외 완료: {before}종목 → {len(symbols)}종목 추출")
    
    return symbols, symbol_to_name

def download_and_prep_data(symbols):
    print(f"\n{len(symbols)}개 종목의 {START_DATE} ~ {END_DATE} 데이터를 다운로드합니다...")
    data = yf.download(symbols, start=START_DATE, end=END_DATE, group_by="ticker", progress=True)
    
    data_dict = {}
    for sym in symbols:
        try:
            df = data[sym].copy()
            df.dropna(inplace=True)
            if len(df) < 120: continue
                
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA60'] = df['Close'].rolling(window=60).mean()
            df['Prev_Close'] = df['Close'].shift(1)
            df['Prev_Low'] = df['Low'].shift(1)
            
            df['is_gap_down'] = df['High'] < df['Prev_Low']
            df['is_drop_4pct'] = df['Close'] <= (df['Prev_Close'] * 0.96)
            df['is_uptrend'] = df['Close'] > df['MA60']
            
            df['Buy_Signal'] = df['is_gap_down'] & df['is_drop_4pct'] & df['is_uptrend']
            
            df.dropna(inplace=True)
            data_dict[sym] = df
        except Exception:
            continue
            
    print(f"데이터 전처리 완료: 총 {len(data_dict)}개 종목 분석 준비 완료.")
    return data_dict

def run_backtest(data_dict):
    print(f"\n기본금 {INITIAL_CAPITAL:,}원 / 월 적립 {MONTHLY_CONTRIBUTION:,}원 조건으로 백테스트를 시작합니다...")
    
    all_dates = pd.core.indexes.datetimes.DatetimeIndex([])
    for df in data_dict.values():
        all_dates = all_dates.union(df.index)
    all_dates = all_dates.sort_values()

    cash = INITIAL_CAPITAL
    total_invested = INITIAL_CAPITAL
    positions = {} 
    trade_log = []
    daily_equity = []

    if len(all_dates) > 0:
        current_month = all_dates[0].month
    else:
        current_month = 1

    for idx_num, current_date in enumerate(all_dates):
        # 매월 첫 거래일에 추가 투자금 투입
        if current_date.month != current_month:
            cash += MONTHLY_CONTRIBUTION
            total_invested += MONTHLY_CONTRIBUTION
            current_month = current_date.month

        current_equity = cash
        
        # [1] 매도 로직
        for ticker in list(positions.keys()):
            if ticker not in data_dict or current_date not in data_dict[ticker].index:
                continue
                
            pos = positions[ticker]
            today_data = data_dict[ticker].loc[current_date]
            
            t_open, t_high, t_low, t_close = today_data['Open'], today_data['High'], today_data['Low'], today_data['Close']
            ma5 = today_data['MA5']
            days_held = idx_num - pos['buy_date_idx']
            
            sell_qty = 0
            sell_price = 0
            sell_reason = ""
            
            stop_price = pos['buy_price'] * 0.90
            if t_low <= stop_price:
                sell_qty = pos['qty']
                sell_price = min(t_open, stop_price) 
                sell_reason = "손절(-10%)"
            elif days_held >= 20:
                sell_qty = pos['qty']
                sell_price = t_close
                sell_reason = "타임스탑(20일)"
            elif not pos['scaled_out'] and t_high >= pos['target']:
                sell_qty = max(1, pos['qty'] // 2)
                sell_price = max(t_open, pos['target'])
                sell_reason = "1차 익절(갭메움)"
                pos['scaled_out'] = True
                if pos['qty'] == sell_qty:
                    sell_reason = "전량 익절(수량부족)"
            elif pos['scaled_out'] and t_close < ma5:
                sell_qty = pos['qty']
                sell_price = t_close
                sell_reason = "2차 추세청산(MA5)"

            if sell_qty > 0:
                cash += sell_qty * sell_price
                trade_log.append({
                    'Date': current_date, 'Ticker': ticker, 'Action': 'SELL',
                    'Price': sell_price, 'Qty': sell_qty, 'Reason': sell_reason,
                    'Return(%)': (sell_price / pos['buy_price'] - 1) * 100
                })
                pos['qty'] -= sell_qty
                if pos['qty'] <= 0:
                    del positions[ticker]
        
        # [2] 매수 로직
        for ticker, df in data_dict.items():
            if current_date not in df.index: continue
            
            today_data = df.loc[current_date]
            if today_data['Buy_Signal'] and ticker not in positions:
                current_total_asset = cash + sum([p['qty'] * data_dict[t].loc[current_date]['Close'] for t, p in positions.items() if current_date in data_dict[t].index])
                target_budget = current_total_asset * 0.25
                actual_budget = min(target_budget, cash)
                
                t_close = today_data['Close']
                buy_qty = int(actual_budget // t_close)
                
                if buy_qty > 0 and cash >= 10000:
                    cash -= buy_qty * t_close
                    positions[ticker] = {
                        'qty': buy_qty, 'buy_price': t_close,
                        'target': today_data['Prev_Low'], 'scaled_out': False,
                        'buy_date_idx': idx_num
                    }
                    trade_log.append({
                        'Date': current_date, 'Ticker': ticker, 'Action': 'BUY',
                        'Price': t_close, 'Qty': buy_qty, 'Reason': "조건부합 매수",
                        'Return(%)': 0
                    })
        
        # 총 자산 및 투입 원금 기록
        for ticker, pos in positions.items():
            if current_date in data_dict[ticker].index:
                current_equity += pos['qty'] * data_dict[ticker].loc[current_date]['Close']
        daily_equity.append({
            'Date': current_date, 
            'Equity': current_equity, 
            'Invested': total_invested
        })

    return pd.DataFrame(daily_equity), pd.DataFrame(trade_log)

def generate_text_report(equity_df, trades_df, symbol_to_name):
    if trades_df.empty:
        msg = "조건에 맞는 거래가 발생하지 않았습니다."
        print(msg)
        with open(REPORT_FILENAME, "w", encoding="utf-8") as f:
            f.write(msg)
        return

    equity_df.set_index('Date', inplace=True)
    
    # 기본 지표 계산
    final_equity = equity_df['Equity'].iloc[-1]
    final_invested = equity_df['Invested'].iloc[-1]
    
    # 적립식 모델이므로 총 투입 원금 대비 수익률로 계산
    total_return = (final_equity / final_invested - 1) * 100
    
    # MDD 계산
    roll_max = equity_df['Equity'].cummax()
    drawdown = (equity_df['Equity'] / roll_max - 1.0) * 100
    mdd = drawdown.min()
    
    # 매매 통계 계산
    sell_trades = trades_df[trades_df['Action'] == 'SELL'].copy()
    total_sells = len(sell_trades)
    
    winning_trades = sell_trades[sell_trades['Return(%)'] > 0]
    losing_trades = sell_trades[sell_trades['Return(%)'] <= 0]
    
    win_rate = (len(winning_trades) / total_sells * 100) if total_sells > 0 else 0
    avg_return = sell_trades['Return(%)'].mean() if total_sells > 0 else 0
    max_return = sell_trades['Return(%)'].max() if total_sells > 0 else 0
    max_loss = sell_trades['Return(%)'].min() if total_sells > 0 else 0

    # 연도별 자산 변화 계산
    equity_df['Year'] = equity_df.index.year
    yearly_equity = equity_df.groupby('Year').last()

    # 리포트 텍스트 구성
    lines = []
    lines.append("="*55)
    lines.append("📊 갭메우기 퀀트 전략 백테스트 리포트 (적립식)")
    lines.append("="*55)
    
    lines.append("\n[ 💰 자산 및 수익률 요약 ]")
    lines.append(f"🔹 테스트 기간 : {equity_df.index[0].strftime('%Y-%m-%d')} ~ {equity_df.index[-1].strftime('%Y-%m-%d')}")
    lines.append(f"🔹 기본 투자금 : {INITIAL_CAPITAL:,.0f} 원")
    lines.append(f"🔹 월 적립금   : {MONTHLY_CONTRIBUTION:,.0f} 원")
    lines.append(f"🔹 총 투입 원금: {final_invested:,.0f} 원")
    lines.append(f"🔹 최종 총 자산: {final_equity:,.0f} 원")
    lines.append(f"🔹 누적 수익률 : {total_return:,.2f} % (총 투입 원금 대비)")
    lines.append(f"🔹 최대 낙폭   : {mdd:,.2f} % (MDD)")
    
    lines.append("\n[ 📈 연도별 자산 흐름 ]")
    for year, row in yearly_equity.iterrows():
        lines.append(f"🔸 {year}년 말 기준 총 투입 원금: {row['Invested']:,.0f} 원  |  총 자산: {row['Equity']:,.0f} 원")

    lines.append("\n[ 🤝 매매 통계 ]")
    lines.append(f"🔹 총 매도 횟수: {total_sells} 회")
    lines.append(f"🔹 승률        : {win_rate:.2f} % ({len(winning_trades)}승 / {len(losing_trades)}패)")
    lines.append(f"🔹 평균 익/손절: {avg_return:.2f} %")
    lines.append(f"🔹 최고 수익률 : {max_return:.2f} %")
    lines.append(f"🔹 최대 손실률 : {max_loss:.2f} %")
    
    lines.append("\n[ 🔍 매도 사유별 통계 ]")
    reason_counts = sell_trades['Reason'].value_counts()
    for reason, count in reason_counts.items():
        lines.append(f" - {reason:<20}: {count} 회")
        
    lines.append("\n[ 📝 최근 10건의 거래 상세 내역 ]")
    trades_df['Name'] = trades_df['Ticker'].map(symbol_to_name).fillna(trades_df['Ticker'])
    display_df = trades_df.tail(10)[['Date', 'Name', 'Action', 'Price', 'Qty', 'Reason', 'Return(%)']]
    lines.append(display_df.to_string(index=False))
    
    lines.append("="*55)

    # 문자열로 병합
    report_text = "\n".join(lines)
    
    # 터미널 출력
    print(report_text)
    
    # TXT 파일 저장
    try:
        with open(REPORT_FILENAME, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"\n✅ [완료] 위 리포트 내용이 현재 경로의 '{REPORT_FILENAME}' 파일로 안전하게 저장되었습니다.")
    except Exception as e:
        print(f"\n❌ 파일 저장 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    symbols, symbol_to_name = get_live_universe()
    data = download_and_prep_data(symbols)
    equity_df, trades_df = run_backtest(data)
    generate_text_report(equity_df, trades_df, symbol_to_name)