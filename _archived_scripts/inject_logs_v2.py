"""精确注入操作日志 - 在 db.commit() 后、return 前插入一行日志调用"""
import os, re

DIR = r'C:\Users\12225\.openclaw\workspace\projects\gym-web-system\backend\routers'

# 每个路由文件：[(decorator行, 资源名)]
POSTS = {
    'member.py': [('member.py:167', '会员')],
    'staff.py': [('staff.py:133', '员工')],
    'course.py': [('course.py:138', '课程')],
    'sale.py': [('sale.py:129', '售课记录')],
    'class_record.py': [('class_record.py:133', '上课记录')],
    'checkin.py': [('checkin.py:152', '进场记录')],
    'body_measurement.py': [('body_measurement.py:121', '体测记录')],
    'recharge.py': [('recharge.py:121', '充值记录')],
    'membership_card.py': [('membership_card.py:117', '会籍卡')],
    'product.py': [
        ('product.py:87', '商品'),
        ('product.py:177', '商品零售'),
    ],
    'finance.py': [
        ('finance.py:209', '收入记录'),
        ('finance.py:229', '支出记录'),
    ],
}

PUTS = {
    'member.py': [('member.py:202', '会员')],
    'staff.py': [('staff.py:150', '员工')],
    'course.py': [('course.py:157', '课程')],
    'sale.py': [('sale.py:154', '售课记录')],
    'checkin.py': [
        ('checkin.py:215', '手环'),
        ('checkin.py:232', '手环绑定'),
        ('checkin.py:249', '手环解绑'),
    ],
    'alert.py': [('alert.py:101', '到期提醒')],
}

DELETES = {
    'member.py': [('member.py:218', '会员')],
    'staff.py': [('staff.py:163', '员工')],
    'course.py': [('course.py:173', '课程')],
    'sale.py': [('sale.py:168', '售课记录')],
    'class_record.py': [('class_record.py:149', '上课记录')],
    'checkin.py': [('checkin.py:263', '进场记录')],
    'body_measurement.py': [('body_measurement.py:142', '体测记录')],
    'recharge.py': [('recharge.py:142', '充值记录')],
    'alert.py': [('alert.py:116', '到期提醒')],
    'membership_card.py': [('membership_card.py:145', '会籍卡')],
    'product.py': [
        ('product.py:102', '商品'),
        ('product.py:195', '商品零售'),
    ],
    'finance.py': [
        ('finance.py:255', '收入记录'),
        ('finance.py:267', '支出记录'),
    ],
    'wristband.py': [('wristband.py:150', '手环')],
}


def inject_logs(action, mapping, tag):
    for filename, injections in mapping.items():
        filepath = os.path.join(DIR, filename)
        if not os.path.exists(filepath):
            print(f'  ❌ 未找到 {filepath}')
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')

        # 先加 import（如果没有的话）
        has_import = False
        for line in lines:
            if 'from backend.routers.log_utils import' in line:
                has_import = True
                break

        if not has_import:
            # 在最后一个 from/import 行后插入
            last_import = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(('from ', 'import ')):
                    last_import = i
            import_line = 'from backend.routers.log_utils import log_create, log_update, log_delete'
            if 'from fastapi import Request' not in content:
                import_line += '\nfrom fastapi import Request'
            lines.insert(last_import + 1, import_line)
            content = '\n'.join(lines)
            lines = content.split('\n')

        modified = False
        for loc, resource in injections:
            # 定位装饰器行
            fn, ln = loc.split(':')
            ln = int(ln)
            decorator_line = ln - 1  # 0-indexed

            # 找函数体中的 db.commit() 行
            commit_line = None
            return_line = None
            for i in range(decorator_line, min(decorator_line + 50, len(lines))):
                stripped = lines[i].strip()
                if stripped == 'db.commit()':
                    commit_line = i
                if commit_line is not None and stripped.startswith('return '):
                    return_line = i
                    break

            if return_line is None:
                print(f'  ⚠️  {filename}: {loc} 未找到 return')
                continue

            # 构建日志代码
            indent = ' ' * 8
            if action == 'create':
                code = f"""
{indent}# 操作日志
{indent}try:
{indent}    log_create(request, db, "{resource}", resource_id, detail="{resource}已创建")
{indent}except Exception:
{indent}    pass
"""
            elif action == 'update':
                code = f"""
{indent}# 操作日志
{indent}try:
{indent}    log_update(request, db, "{resource}", resource_id, detail="{resource}已更新")
{indent}except Exception:
{indent}    pass
"""
            else:  # delete
                code = f"""
{indent}# 操作日志
{indent}try:
{indent}    log_delete(request, db, "{resource}", resource_id, detail="{resource}已删除")
{indent}except Exception:
{indent}    pass
"""

            # 插入在 return 前
            lines.insert(return_line, code)

            # 检查函数参数有没有 request
            # 找到 def 行
            def_line = None
            for i in range(decorator_line + 1, decorator_line + 5):
                if lines[i].strip().startswith('def '):
                    def_line = i
                    break

            if def_line is not None and 'request: Request' not in lines[def_line]:
                # 加 request 参数
                sig = lines[def_line]
                # 找第一个 ( 和匹配的 )
                paren = sig.index('(')
                rparen = sig.rindex(')')
                # 检查是否有 request 关键字
                if 'request' not in sig[paren:rparen]:
                    params = sig[paren+1:rparen].strip()
                    if params:
                        lines[def_line] = sig[:paren+1] + 'request: Request, ' + sig[paren+1:]
                    else:
                        lines[def_line] = sig[:paren+1] + 'request: Request' + sig[rparen:]

            modified = True
            print(f'  ✅ {filename}: {tag} → {resource}')

        if modified:
            content = '\n'.join(lines)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
                print(f'     💾 已保存')


# 执行
print('📝 注入 CREATE 日志...')
inject_logs('create', POSTS, 'POST')

print('\n📝 注入 UPDATE 日志...')
inject_logs('update', PUTS, 'PUT')

print('\n📝 注入 DELETE 日志...')
inject_logs('delete', DELETES, 'DELETE')

print('\n🎉 全部日志注入完成！')
