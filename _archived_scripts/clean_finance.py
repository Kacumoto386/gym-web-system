"""清理 finance.py 残留的日志注入代码"""
fp = r'C:\Users\12225\.openclaw\workspace\projects\gym-web-system\backend\routers\finance.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# 替换第一处（收入）
old1 = '''    db.commit()
    db.refresh(r)
    # 操作日志
            ip = request.client.host if hasattr(request, 'client') and request.client else ""
            log_create(request, db, "收入记录", resource_id, detail="收入记录已创建")

    return {"success": True, "record_id": rid}'''

new1 = '''    db.commit()
    db.refresh(r)

    return {"success": True, "record_id": rid}'''

content = content.replace(old1, new1)

# 替换第二处（支出）
old2 = '''    db.commit()
    db.refresh(r)
    # 操作日志
            ip = request.client.host if hasattr(request, 'client') and request.client else ""
            log_create(request, db, "支出记录", resource_id, detail="支出记录已创建")

    return {"success": True, "record_id": rid}'''

content = content.replace(old2, new1)

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
