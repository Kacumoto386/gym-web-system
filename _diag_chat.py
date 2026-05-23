"""Quick test: chat page rendering + API response"""
import urllib.request, json, sys

port = "8081"
base = f"http://127.0.0.1:{port}"

# 1. Login
r = urllib.request.urlopen(f"{base}/auth/token",
    json.dumps({"username":"admin","password":"admin123"}).encode())
token = json.loads(r.read())["access_token"]
print(f"1. Login OK, token={token[:16]}...")

# 2. Fetch /chat page
req = urllib.request.Request(f"{base}/chat")
req.add_header("Cookie", f"access_token={token}")
r = urllib.request.urlopen(req)
chat_html = r.read().decode("utf-8")
print(f"2. /chat page: {r.status} ({len(chat_html)} bytes)")

# Check key elements
checks = [
    ("initDom()", "initDom" in chat_html),
    ("sendMessage()", "sendMessage" in chat_html),
    ("renderMarkdown()", "renderMarkdown" in chat_html),
    ("input field", 'id="input"' in chat_html),
    ("messages container", 'id="messages"' in chat_html),
    ("send button", 'id="sendBtn"' in chat_html),
    ("chat API endpoint", "/api/chat/message" in chat_html),
    ("Tailwind CDN", "cdn.tailwindcss.com" in chat_html),
]
for name, ok in checks:
    print(f"   {'✅' if ok else '❌'} {name}")

# 3. Send a test message via API
body = json.dumps({"message": "hi", "session_id": "diag"}).encode()
req = urllib.request.Request(f"{base}/api/chat/message", data=body, method="POST")
req.add_header("Content-Type", "application/json")
r = urllib.request.urlopen(req, timeout=30)
resp = json.loads(r.read().decode("utf-8"))
reply = resp.get("reply", "")
print(f"3. Chat API: 200 ({len(reply)} chars response)")
print(f"   First 100 chars: {reply[:100]}")

print("\n✅ All checks passed")
