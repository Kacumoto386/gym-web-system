import subprocess, json, sys

# Send message - capture bytes
result = subprocess.run([
    'C:\\Windows\\System32\\curl.exe', '-s',
    'http://localhost:8000/api/chat/message',
    '-H', 'Content-Type: application/json',
    '-H', 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc3OTM1NTgxOH0._5wZ3fCGO8ut-k9SsybU4KRoumRtHm0fMn8Ffwcvf58',
    '-d', '{"message":"查一下鼠小弟的会员信息和最近进场记录","session_id":"verify"}'
], capture_output=True, text=False)  # binary mode

stdout = result.stdout.decode('utf-8', errors='replace')
data = json.loads(stdout)
reply = data.get('reply', '')
dirty = '[object Object]' in reply
print(f"Reply len={len(reply)}, dirty={dirty}")
if not dirty:
    print("CLEAN - first 200:", reply[:200])
else:
    print("DIRTY - first 500:", reply[:500])
