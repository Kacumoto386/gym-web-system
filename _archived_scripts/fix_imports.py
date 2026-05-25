"""修复所有路由文件中缺少的 Request import"""
import os, re

DIR = r'C:\Users\12225\.openclaw\workspace\projects\gym-web-system\backend\routers'

for fn in sorted(os.listdir(DIR)):
    if not fn.endswith('.py'):
        continue
    fp = os.path.join(DIR, fn)
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    
    needs_request = 'request: Request' in content
    has_request_import = 'from fastapi import' in content and 'Request' in content.split('from fastapi import')[1].split('\n')[0] if 'from fastapi import' in content else 'fastapi import Request' in content
    
    if needs_request and not has_request_import:
        # 补上 Request
        if 'from fastapi import' in content:
            content = content.replace('from fastapi import', 'from fastapi import Request, ')
            # 去掉重复
            content = content.replace('Request, Request', 'Request')
            content = content.replace('Request, ,', 'Request,')
        elif 'from fastapi.responses import' in content:
            content = content.replace('from fastapi.responses import', 'from fastapi import Request\nfrom fastapi.responses import')
        else:
            # 在 import 块最后加
            import_block = re.search(r'^(from .+ import .+\n)+', content, re.MULTILINE)
            if import_block:
                pos = import_block.end()
                content = content[:pos] + 'from fastapi import Request\n' + content[pos:]
        
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  ✅ {fn} (补了 Request import)')
    else:
        print(f'  - {fn} (ok)')
