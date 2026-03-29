import pandas as pd
import numpy as np
import yfinance as yf

from daily_telegram_bot import get_top_tickers_from_naver

def calculate_macd(series, short=12, long=26, signal=9):
    ema_short = series.ewm(span=short, adjust=False).mean()
    ema_long = series.ewm(span=long, adjust=False).mean()
    macd = ema_short - ema_long
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    return macd_hist

def calculate_atr_pct(high, low, close_prev, period=14):
    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr

def run_analysis():
    print("종목 목록 가져오는 중...")
    symbols, _, _ = get_top_tickers_from_naver()
    
    start_date = "2021-01-01"
    end_date = "2025-12-31"
    print(f"데이터 다운로드 중 ({start_date} ~ {end_date})...")
    
    data = yf.download(symbols, start=start_date, end=end_date, group_by="ticker", progress=True)
    
    close_df = pd.DataFrame({sym: data[sym]['Close'] for sym in symbols}).ffill()
    open_df = pd.DataFrame({sym: data[sym]['Open'] for sym in symbols}).ffill()
    high_df = pd.DataFrame({sym: data[sym]['High'] for sym in symbols}).ffill()
    low_df = pd.DataFrame({sym: data[sym]['Low'] for sym in symbols}).ffill()
    
    print("새로운 지표 계산 중 (MACD, ATR, 60일 이격도)...")
    ma5_df = close_df.rolling(5).mean()
    ma60_df = close_df.rolling(60).mean()
    
    # 1. MACD Histogram (추세 지속성 파악)
    macd_hist_df = close_df.apply(calculate_macd)
    
    # 2. 이격도 (Distance from MA60) - 60일선에서 얼마나 높이 떠있는가? (%)
    dist_ma60_df = ((close_df - ma60_df) / ma60_df) * 100
    
    # 전략 조건 동일하게 재적용
    cond_gap_down = low_df.shift(1) > high_df
    cond_drop_4pct = (close_df / close_df.shift(1)) < 0.96
    cond_uptrend = close_df > ma60_df
    
    buy_signals = cond_gap_down & cond_drop_4pct & cond_uptrend
    
    trades = []
    
    print("백테스팅 및 타점 분석 시뮬레이션 중...")
    for sym in symbols:
        in_pos = False
        buy_date = None
        buy_price = 0
        
        entry_macd = 0
        entry_dist = 0
        entry_atr = 0

        # ATR 계산은 개별로 (병렬 처리가 복잡하므로)
        atr_series = calculate_atr_pct(high_df[sym], low_df[sym], close_df[sym].shift(1))
        atr_pct_series = (atr_series / close_df[sym]) * 100 # 종가 대비 ATR 비율(%)
        
        for date, signal in buy_signals[sym].items():
            c_price = close_df.loc[date, sym]
            if pd.isna(c_price): continue
            
            if not in_pos and signal:
                in_pos = True
                buy_date = date
                buy_price = c_price
                target_price = low_df.shift(1).loc[date, sym]
                
                entry_macd = macd_hist_df.loc[date, sym]
                entry_dist = dist_ma60_df.loc[date, sym]
                entry_atr = atr_pct_series.loc[date]
                scaled_out = False
                
            elif in_pos:
                curr_high = high_df.loc[date, sym]
                
                if c_price <= buy_price * 0.9:
                    ret = (c_price - buy_price) / buy_price
                    trades.append({'sym': sym, 'bdate': buy_date, 'sdate': date, 'ret': ret, 
                                   'macd_h': entry_macd, 'dist_ma60': entry_dist, 'atr_pct': entry_atr, 'type': 'Loss'})
                    in_pos = False
                elif not scaled_out and curr_high >= target_price:
                    scaled_out = True
                elif scaled_out and c_price < ma5_df.loc[date, sym]:
                    ret = (c_price - buy_price) / buy_price
                    trades.append({'sym': sym, 'bdate': buy_date, 'sdate': date, 'ret': ret, 
                                   'macd_h': entry_macd, 'dist_ma60': entry_dist, 'atr_pct': entry_atr, 'type': 'Win'})
                    in_pos = False
                
                if in_pos and (date - buy_date).days > 30:
                    ret = (c_price - buy_price) / buy_price
                    ttype = 'Loss' if ret < 0 else 'Win'
                    trades.append({'sym': sym, 'bdate': buy_date, 'sdate': date, 'ret': ret, 
                                   'macd_h': entry_macd, 'dist_ma60': entry_dist, 'atr_pct': entry_atr, 'type': ttype})
                    in_pos = False

    df_trades = pd.DataFrame(trades).dropna()
    
    print("\n" + "="*55)
    print("📊 손실 종목 vs 수익 종목 2차 매수 시점 지표 비교 (평균)")
    print("="*55)
    
    grouped = df_trades.groupby('type')[['macd_h', 'dist_ma60', 'atr_pct']].mean()
    grouped.index = ['손실 거래 (Loss)', '수익 거래 (Win)']
    grouped.columns = ['MACD 히스토그램', '60일선 대비 이격도(%)', '당일 ATR 변동성(%)']
    print(grouped.round(2))
    
    print("\n" + "="*50)
    print("📉 손실 거래 패턴 딥다이브 (구간 배분)")
    print("="*50)
    loss_trades = df_trades[df_trades['type'] == 'Loss']
    
    dist_bins = pd.cut(loss_trades['dist_ma60'], bins=[0, 5, 15, 30, 50, 200])
    print("▶ 60일선 이격도(거리) 분포 (손절 종목 중)")
    print("  0~5% : MA60 지지선 근접 (바람직)")
    print("  30% 이상 : 단기 폭등 후 과열 상태 (거품 붕괴 우려)")
    print(dist_bins.value_counts().sort_index())
    
    atr_bins = pd.cut(loss_trades['atr_pct'], bins=[0, 3, 5, 8, 15, 100])
    print("\n▶ ATR 일일 변동성 분포 (손절 종목 중)")
    print("  종목의 하루 평균 널뛰기 폭이 8% 이상이면 10% 손절을 쉽게 터치할 가능성 높음.")
    print(atr_bins.value_counts().sort_index())

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings('ignore')
    run_analysis()
