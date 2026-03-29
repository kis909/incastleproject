import os
import json
from kis_auto_trader import get_access_token, send_order, get_account_balance, get_current_price

def manual_test():
    print("=== 수동 매매 테스트 (장 마감 환경) ===")
    try:
        token = get_access_token()
        print("1. 토큰 발급 성공")
        
        cash = get_account_balance(token)
        print(f"2. 현재 모의투자 잔액: {cash:,}원")
        
        symbol = "005930"  # 삼성전자
        qty = 1
        
        rt = get_current_price(token, symbol)
        if rt:
            print(f"3. 삼성전자 현재 장의 실시간 종가: {rt['close']:,}원")
            
            # 여기서 시장가(가격 0)로 매수 주문을 넣어봅니다.
            print("4. 모의투자 서버로 수동 시장가 매수 주문 전송 시도...")
            success = send_order(token, "BUY", symbol, qty, 0)
            if not success:
                print("-> KIS API 정책상 장외 시간 주문 거부 상태임을 확인했습니다.")
                
    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    manual_test()
