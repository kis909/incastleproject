import re

with open('gap_stock_auto.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 이미 strftime 을 사용해 수동으로 시각을 찍던 패턴도 ts()로 통일
# "[{datetime.datetime.now().strftime('%H:%M:%S')}]" → "{ts()}"
content = re.sub(
    r'\[{datetime\.datetime\.now\(\)\.strftime\(["\']%H:%M:%S["\']\)}\]',
    '{ts()}',
    content
)

# 남아있는 print(f"... 중 ts()가 없는 것을 처리
# 단순 패턴: print(f"...) 의 첫 따옴표 직후에 {ts()} 삽입
def add_ts_to_fstring(m):
    full = m.group(0)
    if 'ts()' in full:
        return full
    # f"TEXT" → f"{ts()} TEXT"
    return full.replace('print(f"', 'print(f"{ts()} ', 1).replace("print(f'", "print(f'{ts()} ", 1)

# print(f"로 시작하는 행
content = re.sub(r'print\(f"[^"]*"', add_ts_to_fstring, content, flags=re.DOTALL)
content = re.sub(r"print\(f'[^']*'", add_ts_to_fstring, content, flags=re.DOTALL)

# 일반 print("TEXT" -> print(f"{ts()} TEXT"
def add_ts_to_plain(m):
    full = m.group(0)
    if 'ts()' in full or 'f"' in full or "f'" in full:
        return full
    if full.startswith('print("'):
        return full.replace('print("', 'print(f"{ts()} ', 1)
    if full.startswith("print('"):
        return full.replace("print('", "print(f'{ts()} ", 1)
    return full

content = re.sub(r'print\("[^"]*"', add_ts_to_plain, content)
content = re.sub(r"print\('[^']*'", add_ts_to_plain, content)

with open('gap_stock_auto.py', 'w', encoding='utf-8') as f:
    f.write(content)

# 몇 개나 적용됐는지 확인
with open('gap_stock_auto.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

missing = [i for i, l in enumerate(lines, 1) 
           if l.strip().startswith('print(') and 'ts()' not in l and 'def ' not in l]
print(f'적용 완료. 여전히 누락된 print문: {len(missing)}개')
for n in missing[:10]:
    print(f'  line {n}: {lines[n-1].strip()[:80]}')
