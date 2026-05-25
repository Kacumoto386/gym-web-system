"""回滚所有操作日志注入 - 改为使用 middleware 方案"""
import os

DIR = r'C:\Users\12225\.openclaw\workspace\projects\gym-web-system\backend\routers'

# 需要清理的文件
files = [
    'member.py', 'staff.py', 'course.py', 'sale.py',
    'class_record.py', 'checkin.py', 'body_measurement.py',
    'recharge.py', 'alert.py', 'membership_card.py',
    'product.py', 'finance.py',
]

for fn in files:
    fp = os.path.join(DIR, fn)
    if not os.path.exists(fp):
        continue
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # 移除注入的操作日志代码块
    import re
    
    # 移除 try/except log_* 块
    content = re.sub(
        r'\n\s+# 操作日志\n\s+try:\n\s+log_\w+\(request, db, "[^"]+", resource_id, detail="[^"]+"\)\n\s+except Exception:\n\s+pass\n',
        '',
        content
    )
    
    # 移除单独的 try/except log_* 块（上面的变体）
    content = re.sub(
        r'\n\s+# 操作日志\n\s+try:\n\s+log_\w+\([^)]+\)\n\s+except Exception:\n\s+pass',
        '',
        content
    )
    
    # 移除 import log_utils
    content = content.replace('from backend.routers.log_utils import log_create, log_update, log_delete\n', '')
    content = content.replace('from backend.routers.log_utils import log_create, log_update, log_delete', '')
    
    # 移除多余的 from fastapi import Request（如果单独在一行）
    content = content.replace('from fastapi import Request\n', '')
    
    if content != original:
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  ✅ {fn} 已清理')
    else:
        print(f'  - {fn} 无需清理')

print('\n🎉 清理完成')
