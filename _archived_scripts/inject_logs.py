"""批量给所有路由文件注入操作日志调用"""
import os
import re

CWD = r'C:\Users\12225\.openclaw\workspace\projects\gym-web-system'
ROUTERS_DIR = os.path.join(CWD, 'backend', 'routers')

IMPORT = """from backend.routers.log_utils import log_create, log_update, log_delete
from fastapi import Request"""

# 需要注入日志的文件和对应的操作映射
# {filename: [(HTTP方法, 路径片段, 资源名)]}
INJECTIONS = {
    'member.py': [
        ('@router.post("")', '/api/members', '会员'),
        ('@router.put("/{member_id}")', '/api/members/{member_id}', '会员'),
        ('@router.delete("/{member_id}")', '/api/members/{member_id}', '会员'),
    ],
    'staff.py': [
        ('@router.post("")', '/api/staff', '员工'),
        ('@router.put("/{staff_id}")', '/api/staff/{staff_id}', '员工'),
        ('@router.delete("/{staff_id}")', '/api/staff/{staff_id}', '员工'),
    ],
    'course.py': [
        ('@router.post("")', '/api/courses', '课程'),
        ('@router.put("/{course_id}")', '/api/courses/{course_id}', '课程'),
        ('@router.delete("/{course_id}")', '/api/courses/{course_id}', '课程'),
    ],
    'sale.py': [
        ('@router.post("")', '/api/sales', '售课记录'),
        ('@router.delete("/{sale_id}")', '/api/sales/{sale_id}', '售课记录'),
    ],
    'class_record.py': [
        ('@router.post("")', '/api/class-records', '上课记录'),
        ('@router.delete("/{class_id}")', '/api/class-records/{class_id}', '上课记录'),
    ],
    'checkin.py': [
        ('@router.post("/checkin")', '/api/checkin', '进场签到'),
        ('@router.post("")', '/api/checkins', '进场记录'),
        ('@router.delete("/{checkin_id}")', '/api/checkins/{checkin_id}', '进场记录'),
    ],
    'body_measurement.py': [
        ('@router.post("")', '/api/body-measurements', '体测记录'),
        ('@router.delete("/{measure_id}")', '/api/body-measurements/{measure_id}', '体测记录'),
    ],
    'recharge.py': [
        ('@router.post("")', '/api/recharges', '充值记录'),
        ('@router.delete("/{recharge_id}")', '/api/recharges/{recharge_id}', '充值记录'),
    ],
    'alert.py': [
        ('@router.put("/{alert_id}")', '/api/alerts/{alert_id}', '到期提醒'),
        ('@router.delete("/{alert_id}")', '/api/alerts/{alert_id}', '到期提醒'),
    ],
    'membership_card.py': [
        ('@router.post("")', '/api/membership-cards', '会籍卡'),
        ('@router.delete("/{card_id}")', '/api/membership-cards/{card_id}', '会籍卡'),
    ],
    'product.py': [
        ('@router.post("/products")', '/api/products', '商品'),
        ('@router.delete("/products/{product_id}")', '/api/products/{product_id}', '商品'),
        ('@router.post("/product-sales")', '/api/product-sales', '商品零售'),
        ('@router.delete("/product-sales/{sale_id}")', '/api/product-sales/{sale_id}', '商品零售'),
    ],
    'finance.py': [
        ('@router.post("/income")', '/api/finance/income', '收入记录'),
        ('@router.post("/expense")', '/api/finance/expense', '支出记录'),
        ('@router.delete("/income/{record_id}")', '/api/finance/income/{record_id}', '收入记录'),
        ('@router.delete("/expense/{record_id}")', '/api/finance/expense/{record_id}', '支出记录'),
    ],
}

# 每个函数注入的代码模板
INJECT_CODE_TEMPLATE = """    # 操作日志
    ip = request.client.host if hasattr(request, 'client') and request.client else ""
    log_create(request, db, "{resource}", resource_id, detail="{resource}已创建")
"""

UPDATE_CODE = """    # 操作日志
    log_update(request, db, "{resource}", resource_id, detail="{resource}已更新")
"""

DELETE_CODE = """    # 操作日志
    log_delete(request, db, "{resource}", resource_id, detail="{resource}已删除")
"""

# 解析函数体，找到 return 之前的位置
def find_return_end(content, func_start):
    """从函数定义开始，找到 return 行的结束"""
    lines = content.split('\n')
    depth = 0
    in_func = False
    in_return = False
    for i in range(func_start, len(lines)):
        line = lines[i]
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        # 跳过装饰器
        if stripped.startswith('@'):
            continue

        # 找到 def
        if stripped.startswith('def '):
            in_func = True
            continue

        if not in_func:
            continue

        # 找到 return 行
        if stripped.startswith('return'):
            return i  # 返回 return 行号

    return None


def inject_file(filepath, injections):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 先加 import
    if 'from backend.routers.log_utils import' not in content:
        # 找到最后一个 import 行
        lines = content.split('\n')
        last_import = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')):
                last_import = i
        content = content.replace(lines[last_import], lines[last_import] + '\n' + IMPORT)
        lines = content.split('\n')

    # 对每个注入点，找到对应函数
    for decorator, endpoint, resource in injections:
        lines = content.split('\n')
        decorator_line = None
        for i, line in enumerate(lines):
            if line.strip() == decorator:
                decorator_line = i
                break

        if decorator_line is None:
            print(f'  ⚠️  {os.path.basename(filepath)}: 未找到 {decorator}')
            continue

        # 找到 decorator 后的 def
        def_line = None
        for i in range(decorator_line + 1, min(decorator_line + 5, len(lines))):
            if lines[i].strip().startswith('def '):
                def_line = i
                break

        if def_line is None:
            print(f'  ⚠️  {os.path.basename(filepath)}: {decorator} 后未找到 def')
            continue

        # 找到函数体内有 commit + return 的部分
        # 简单策略：找 db.commit() 之后的 return 行前插入
        commit_line = None
        for i in range(def_line + 1, len(lines)):
            stripped = lines[i].strip()
            if stripped == 'db.commit()':
                commit_line = i
            elif commit_line and stripped.startswith('return '):
                # 在 commit_line 后面、return 前面插入
                indent = ' ' * 8
                code = ''
                if 'create' in decorator or 'post' in decorator:
                    code = f"""
        # 操作日志
        ip = request.client.host if hasattr(request, 'client') and request.client else ""
        log_create(request, db, "{resource}", resource_id, detail="{resource}已创建")
"""
                elif 'put' in decorator:
                    code = f"""
        # 操作日志
        log_update(request, db, "{resource}", resource_id, detail="{resource}已更新")
"""
                elif 'delete' in decorator:
                    code = f"""
        # 操作日志
        log_delete(request, db, "{resource}", resource_id, detail="{resource}已删除")
"""

                # 插入代码
                # 确保函数签名有 request 参数
                func_sig = lines[def_line]
                if 'request:' not in func_sig and 'Request' not in func_sig:
                    # 加 request 参数
                    if 'request: Request' not in func_sig:
                        # 在第一个参数后加 request
                        # 找括号位置
                        paren = func_sig.index('(')
                        # 简单处理：检查是否有 Depends
                        if 'db: Session' in func_sig:
                            func_sig_new = func_sig.replace('db: Session', 'request: Request, db: Session')
                            lines[def_line] = func_sig_new

                # 在 return 前插入
                indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
                code_indented = ''
                for cl in code.strip().split('\n'):
                    code_indented += indent + cl + '\n'
                lines.insert(i, code_indented)
                print(f'  ✅ {os.path.basename(filepath)}: {decorator} → {resource}')
                commit_line = None
                break

        content = '\n'.join(lines)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


# 执行
for filename, injs in INJECTIONS.items():
    filepath = os.path.join(ROUTERS_DIR, filename)
    if os.path.exists(filepath):
        print(f'\n📝 {filename}')
        inject_file(filepath, injs)
    else:
        print(f'\n❌ 未找到 {filepath}')

print('\n🎉 全部注入完成！')
