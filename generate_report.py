import pandas as pd
import yfinance as yf
import time
import os
import sys
import io

# Windows 콘솔 인코딩 대응
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

from daily_telegram_bot import get_top_tickers_from_naver, calc_ta_score

def generate_full_report():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] KOSPI/KOSDAQ 데이터 로딩 중 (시총 상위 400종목)...")
    symbols, symbol_to_name, symbol_to_code = get_top_tickers_from_naver()
    
    if not symbols:
        print("종목 목록 로드 실패")
        return
        
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {len(symbols)}개 종목 다운로드 중...")
    data = yf.download(symbols, period="6mo", group_by="ticker", progress=True)
    
    results = []
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 지표 계산 중...")
    
    for sym in symbols:
        try:
            df = data[sym].dropna() if len(symbols) > 1 else data.dropna()
            if len(df) < 60: continue
            
            score = calc_ta_score(df)
            curr_p = float(df['Close'].iloc[-1])
            prev_p = float(df['Close'].iloc[-2])
            chg = ((curr_p - prev_p) / prev_p) * 100
            
            results.append({
                '종목명': symbol_to_name[sym],
                '종목코드': symbol_to_code[sym],
                'TA점수': score,
                '현재가': f"{curr_p:,.0f}원",
                '변동률': f"{chg:.2f}%"
            })
        except Exception as e:
            pass
            
    # 정렬 (점수 높은 순)
    results.sort(key=lambda x: x['TA점수'], reverse=True)
    
    df_res = pd.DataFrame(results)
    
    # 아티팩트 경로
    report_path = r"C:\Users\kissk\.gemini\antigravity\brain\42abb689-a7bc-4f83-8e66-8726011b438c\400_stocks_ta_report.md"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# 실시간 코스피/코스닥 시총 상위 400종목 기술적 분석 전체 결과\n\n")
        f.write(f"추출 일시: {time.strftime('%Y-%m-%d %H:%M:%S')} (KST)\n")
        f.write("> 본 테이블은 기술적 지표(이평선, RSI(30일), MACD, 볼린저밴드, 거래량) 5가지 항목을 20점씩 총 100점 만점으로 평가한 점수순 정렬입니다.\n\n")
        df_res.to_markdown(f, index=False)
        
    print(f"리포트 생성 완료: {report_path}")

if __name__ == "__main__":
    generate_full_report()
