"""清除所有路由文件中残留的手动日志注入代码"""
import os, glob, re

DIR = r'C:\Users\12225\.openclaw\workspace\projects\gym-web-system\backend\routers'

for fp in glob.glob(os.path.join(DIR, '*.py')):
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # 移除 # 操作日志 + 带缩进的 log_* 调用块
    # 模式: 注释行 + log_* 行（可能有缩进错误）
    content = re.sub(
        r'\n[ \t]*# 操作日志\n[ \t]+log_\w+\([^)]+\)\n',
        '\n',
        content
    )
    
    # 移除孤立 import
    content = content.replace('from backend.routers.log_utils import log_create, log_update, log_delete\n', '')
    
    if content != original:
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  ✅ {os.path.basename(fp)} 已清理')
    # else: print(f'  - {os.path.basename(fp)} ok')

print('完成')
