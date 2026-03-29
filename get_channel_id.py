import requests

TOKEN = '8725817969:AAGceTYA4jY3l633ktkQQU0q_7Fry0fTDJs'
url = f'https://api.telegram.org/bot{TOKEN}/getUpdates'

try:
    res = requests.get(url).json()
    if res['ok']:
        updates = res['result']
        found = False
        print('--- 최근 메시지들 분석 ---')
        for update in updates:
            if 'channel_post' in update:
                chat = update['channel_post']['chat']
                print(f"채널 발견! 이름: {chat.get('title')}, ID: {chat.get('id')}")
                found = True
            elif 'message' in update:
                chat = update['message']['chat']
                if chat.get('type') in ['group', 'supergroup']:
                    print(f"그룹 발견! 이름: {chat.get('title')}, ID: {chat.get('id')}")
                    found = True
                elif chat.get('type') == 'private':
                    print(f"개인 카톡(DM) 발견! 이름: {chat.get('first_name')}, ID: {chat.get('id')}")
        if not found:
            print('최근 업데이트 내역에서 채널/그룹 메시지를 찾지 못했습니다. 봇을 채널 관리자로 추가하신 후 채널에 아무 텍스트나 하나 전송하시고 다시 실행해보세요.')
    else:
        print('API 호출 실패:', res)
except Exception as e:
    print('오류 발생:', e)
