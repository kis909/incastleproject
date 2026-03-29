import yfinance as yf
import json

syms = ['105560.KS', '085620.KS', '006800.KS'] # KB, 미래에셋, 미래에셋증권 등

for s in syms:
    print(f"--- {s} ---")
    ticker = yf.Ticker(s)
    info = ticker.info
    # Extract financial-related metrics
    keys = ['sector', 'industry', 'priceToBook', 'trailingPE', 'forwardPE', 'debtToEquity', 'returnOnEquity']
    out = {k: info.get(k) for k in keys}
    print(json.dumps(out, indent=2, ensure_ascii=False))
