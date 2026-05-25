"""修复 _full_test.py 中的 http 函数名冲突"""
fp = r'C:\Users\12225\.openclaw\workspace\projects\gym-web-system\_full_test.py'

with open(fp, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    stripped = line.strip()
    # 不要改 def 和 import 行
    if stripped.startswith('def http_req') or stripped.startswith('import http'):
        new_lines.append(line)
    else:
        # 替换 http( 调用为 http_req(
        new_lines.append(line.replace('http(', 'http_req('))

with open(fp, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Done')
