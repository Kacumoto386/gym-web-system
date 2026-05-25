# -*- coding: utf-8 -*-
"""调试预约状态筛选"""
import urllib.request, json, http.cookiejar

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
body = json.dumps({"username":"admin","password":"admin123"}).encode()
r = opener.open(urllib.request.Request("http://127.0.0.1:8000/auth/token",data=body,headers={"Content-Type":"application/json"}))
token = json.loads(r.read())["access_token"]
opener.addheaders = [("Cookie", f"access_token={token}")]

# 按已完成筛选
r1 = opener.open(urllib.request.Request("http://127.0.0.1:8000/api/booking/list?status=%E5%B7%B2%E5%AE%8C%E6%88%90")).read().decode()
data = json.loads(r1)
print(f"已完成筛选: {len(data)}条")
for d in data:
    print(f"  {d['booking_id']} status={d['status']}")
    if d["status"] != "已完成":
        print(f"  ⚠️ 不符合条件!")

# 按已预约筛选
print()
r2 = opener.open(urllib.request.Request("http://127.0.0.1:8000/api/booking/list?status=%E5%B7%B2%E9%A2%84%E7%BA%A6")).read().decode()
data2 = json.loads(r2)
print(f"已预约筛选: {len(data2)}条")
for d in data2:
    print(f"  {d['booking_id']} status={d['status']}")
    if d["status"] != "已预约":
        print(f"  ⚠️ 不符合条件!")
