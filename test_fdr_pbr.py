import FinanceDataReader as fdr
import pandas as pd

# KRX의 Valuation 지표 (PER, PBR, 결산월 등) 가져오기 테스트
try:
    df_krx = fdr.StockListing('KRX-DESC')
    print("KRX-DESC Columns:", df_krx.columns)
    print(df_krx.head())
except Exception as e:
    print("KRX-DESC Fetch error:", e)

# 최신 밸류에이션 지표 가져오기 (종목별)
df_krx_val = fdr.StockListing('KRX')
print("KRX Columns:", df_krx_val.columns)

# 삼성전자(005930), KB금융(105560) 데이터 확인
print(df_krx_val[df_krx_val['Code'].isin(['005930', '105560'])][['Code', 'Name', 'Sector']])

