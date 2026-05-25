"""修复 checkin.py — 删除重复代码 + 后端支持自定义扣次/扣费"""
with open('backend/routers/checkin.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 删除重复的 SINGLE_ENTRY_FEE 定义（保留第一个）
while code.count('SINGLE_ENTRY_FEE = 30.0') > 1:
    first = code.find('SINGLE_ENTRY_FEE = 30.0')
    rest = code[first+23:]  # 跳过第一个
    second = rest.find('SINGLE_ENTRY_FEE = 30.0')
    if second >= 0:
        # 找到第二个定义的位置（在原始代码中的位置）
        pos = first + 23 + second
        # 向后找到换行
        eol = code.find('\n', pos)
        code = code[:pos] + code[eol+1:]

# 删除重复的 _recommend_consume 函数（保留第二个更完整的）
# 查找 `def _recommend_consume` 的第一次出现
first_rc = code.find('\ndef _recommend_consume')
second_rc = code.find('\ndef _recommend_consume', first_rc+50)
if second_rc >= 0:
    # 找到第一个函数结尾（到第二个 def 前）
    # 找到第一个 _recommend_consume 前的空行
    prev_newline = code.rfind('\n', 0, first_rc)
    start_of_duplicate = prev_newline if prev_newline >= 0 else first_rc
    code = code[:start_of_duplicate] + code[second_rc:]

# 删除重复的 _identify_query 函数（保留第一个）
first_iq = code.find('\ndef _identify_query')
second_iq = code.find('\ndef _identify_query', first_iq+50)
if second_iq >= 0:
    # 找到第二个函数前一个换行
    prev_newline = code.rfind('\n', 0, second_iq)
    start_of_duplicate = prev_newline if prev_newline >= 0 else second_iq
    # 找到第二个函数结尾（到下一个 def 前；如果是最后一个函数就到文件尾）
    next_def = code.find('\ndef ', second_iq+50)
    if next_def < 0:
        next_def = len(code)
    code = code[:start_of_duplicate] + code[next_def:]  # 不等号右改 next_def

# 删除重复的 quick_lookup（保留第一个）
first_ql = code.find('\n@router.get("/checkin/quick-lookup"')
second_ql = code.find('\n@router.get("/checkin/quick-lookup"', first_ql+50)
if second_ql >= 0:
    prev_newline = code.rfind('\n', 0, second_ql)
    start_of_duplicate = prev_newline if prev_newline >= 0 else second_ql
    next_route = code.find('\n@router.', second_ql+50)
    if next_route < 0:
        next_route = code.find('\n\nclass ', second_ql+50)
    if next_route < 0:
        next_route = len(code)
    code = code[:start_of_duplicate] + code[next_def:]

# 删除多余的 empty lines (连续3+)
import re
code = re.sub(r'\n{4,}', '\n\n\n', code)

with open('backend/routers/checkin.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("✅ checkin.py 重复代码清理完成")
