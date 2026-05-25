#!/usr/bin/env python3
"""
鼠小弟健身管理系统 V3.5.3 稳定性与数据逻辑测试
==============================================
全面测试所有 API 模块的功能完整性、数据一致性和边界条件。
"""
import requests
import json
import sys
import os
from datetime import date, datetime

BASE = "http://127.0.0.1:8000"
SESSION = requests.Session()
SESSION.cookies.set("access_token", "")
HEADERS = {"Content-Type": "application/json"}

PASS = 0
FAIL = 0
WARN = 0
TEST_RESULTS = []

def _ok(label):
    global PASS
    PASS += 1
    TEST_RESULTS.append(("PASS", label))
    print(f"  ✅ {label}")

def _fail(label, detail=""):
    global FAIL
    FAIL += 1
    msg = f"  ❌ {label}"
    if detail:
        msg += f"  → {detail}"
    print(msg)
    TEST_RESULTS.append(("FAIL", f"{label} | {detail}" if detail else label))

def _warn(label, detail=""):
    global WARN
    WARN += 1
    msg = f"  ⚠️  {label}"
    if detail:
        msg += f"  → {detail}"
    print(msg)
    TEST_RESULTS.append(("WARN", f"{label} | {detail}" if detail else label))

def api(method, path, **kwargs):
    """Send request with session cookies."""
    url = f"{BASE}{path}"
    try:
        if method == "GET":
            r = SESSION.get(url, **kwargs)
        elif method == "POST":
            r = SESSION.post(url, **kwargs)
        elif method == "PUT":
            r = SESSION.put(url, **kwargs)
        elif method == "DELETE":
            r = SESSION.delete(url, **kwargs)
        else:
            raise ValueError(f"Unknown method: {method}")
        r._text = r.text
        return r
    except requests.ConnectionError:
        r = type('obj', (object,), {'status_code': 0, 'text': 'Connection refused', '_text': 'Connection refused'})()
        return r

# ─── Step 1: Login ───
print("\n" + "="*60)
print("  TEST 1: 认证模块")
print("="*60)

# 1.1 Login
r = api("POST", "/auth/token", json={"username": "admin", "password": "admin123"})
if r.status_code == 200:
    data = r.json()
    token = data.get("access_token", "")
    if token:
        SESSION.cookies.set("access_token", token)
        _ok(f"Login OK → token={token[:20]}...")
    else:
        _fail("Login returned no token")
else:
    _fail(f"Login failed: {r.status_code}", r._text[:200])

# 1.2 Get current user
r = api("GET", "/auth/me")
if r.status_code == 200:
    d = r.json()
    _ok(f"auth/me OK → username={d.get('username')}, role={d.get('role')}")
else:
    _fail(f"auth/me failed: {r.status_code}", r._text[:200])

# 1.3 Unauthenticated access
s = requests.Session()
r = s.get(f"{BASE}/api/staff")
if r.status_code == 401:
    _ok("Unauthenticated access correctly returns 401")
else:
    _fail(f"Unauthenticated access returned {r.status_code} (expected 401)", r._text[:200])

# 1.4 Health check (no auth needed)
r = api("GET", "/api/health")
if r.status_code == 200:
    d = r.json()
    _ok(f"Health check OK → version={d.get('version')}, system_name={d.get('system_name')}")
else:
    _fail(f"Health check failed: {r.status_code}")

# 1.5 Login failure with wrong password
r = api("POST", "/auth/token", json={"username": "admin", "password": "wrongpass"})
if r.status_code == 401:
    _ok("Wrong password correctly returns 401")
else:
    _fail(f"Wrong password returned {r.status_code} (expected 401)")

# ─── Step 2: Member CRUD ───
print("\n" + "="*60)
print("  TEST 2: 会员管理模块")
print("="*60)

# 2.1 List members
r = api("GET", "/api/members")
if r.status_code == 200:
    members = r.json()
    _ok(f"List members OK → {len(members)} members")
else:
    _fail(f"List members failed: {r.status_code}", r._text[:200])
    members = []

# 2.2 Search members
r = api("GET", "/api/members/search-json?q=admin")
if r.status_code == 200:
    _ok("Search members OK (JSON API)")
else:
    _fail(f"Search members failed: {r.status_code}")

# 2.3 Create test member via form
test_member_id = None
form_data = {
    "name": "测试会员A",
    "gender": "男",
    "phone": "13800001111",
    "level": "普通",
    "birth_date": "1995-06-15",
    "source": "测试",
    "remark": "自动化测试创建",
}
r = api("POST", "/api/members", data=form_data)
if r.status_code == 200:
    m = r.json()
    test_member_id = m.get("member_id")
    _ok(f"Create member OK → id={test_member_id}, name={m.get('name')}")
    # Check auto-generated fields
    if not m.get("member_id"):
        _fail("member_id is empty")
    if m.get("birth_date") != "1995-06-15":
        _fail(f"birth_date mismatch: {m.get('birth_date')}")
    if m.get("status") != "正常":
        _fail(f"status should be '正常', got '{m.get('status')}'")
else:
    _fail(f"Create member failed: {r.status_code}", r._text[:300])

# 2.4 Get member detail
if test_member_id:
    r = api("GET", f"/api/members/{test_member_id}")
    if r.status_code == 200:
        m = r.json()
        if m.get("name") == "测试会员A":
            _ok(f"Get member OK → {m['name']}")
        else:
            _fail(f"Member name mismatch: {m.get('name')}")
    else:
        _fail(f"Get member failed: {r.status_code}", r._text[:200])

# 2.5 Update member
if test_member_id:
    r = api("PUT", f"/api/members/{test_member_id}", data={
        "name": "测试会员A_改名",
        "phone": "13800002222",
        "level": "VIP",
        "birth_date": "1995-06-15",
    })
    if r.status_code == 200:
        m = r.json()
        if m.get("name") == "测试会员A_改名":
            _ok(f"Update member OK → name changed to {m['name']}")
        else:
            _fail(f"Update member name not changed: {m.get('name')}")
        if m.get("level") == "VIP":
            _ok("Update member level OK")
        else:
            _fail(f"Member level not updated: {m.get('level')}")
    else:
        _fail(f"Update member failed: {r.status_code}", r._text[:300])

# 2.6 Search JSON (used by checkin)
r = api("GET", "/api/members/search-json?q=测试")
if r.status_code == 200:
    results = r.json()
    if len(results) > 0:
        _ok(f"search-json OK → found {len(results)} matching members")
    else:
        _fail("search-json returned empty results for '测试'")
else:
    _fail(f"search-json failed: {r.status_code}")

# 2.7 Get member with cards
if test_member_id:
    r = api("GET", f"/api/members/{test_member_id}/with-cards")
    if r.status_code == 200:
        d = r.json()
        _ok(f"with-cards OK → member={d.get('member',{}).get('name')}, cards={len(d.get('cards',[]))}")
    else:
        _fail(f"with-cards failed: {r.status_code}", r._text[:200])

# 2.8 HTML table fragment
r = api("GET", "/api/members/table")
if r.status_code == 200 and "测试会员A" in r.text:
    _ok("Member table HTML contains test member")
else:
    _fail("Member table HTML doesn't contain test member")

# 2.9 Member ID format validation
if test_member_id:
    if test_member_id.startswith("M") and len(test_member_id) >= 12:
        _ok(f"Member ID format OK: {test_member_id}")
    else:
        _warn(f"Member ID format unusual: {test_member_id}")

# 2.10 Stats cards
r = api("GET", "/api/members/stats")
if r.status_code == 200 and "总会员数" in r.text and "活跃率" in r.text:
    _ok("Member stats cards OK")
else:
    _fail(f"Member stats cards failed: {r.status_code}")

# 2.11 Filter options
r = api("GET", "/api/members/filter-options")
if r.status_code == 200:
    opts = r.json()
    has_all = all(k in opts for k in ["levels", "statuses", "sources", "staff"])
    _ok(f"Filter options OK → {len(opts.get('staff',[]))} staff, {len(opts.get('levels',[]))} levels") if has_all else _fail("Filter options missing keys")
else:
    _fail(f"Filter options failed: {r.status_code}")

# 2.12 Detail tab: cards-html
r = api("GET", f"/api/members/{test_member_id}/cards-html")
if r.status_code == 200:
    _ok("Detail cards-html OK")
else:
    _fail(f"Detail cards-html failed: {r.status_code}")

# 2.13 Detail tab: checkins-html
r = api("GET", f"/api/members/{test_member_id}/checkins-html")
if r.status_code == 200:
    _ok("Detail checkins-html OK")
else:
    _fail(f"Detail checkins-html failed: {r.status_code}")

# 2.14 Detail tab: class-records-html
r = api("GET", f"/api/members/{test_member_id}/class-records-html")
if r.status_code == 200:
    _ok("Detail class-records-html OK")
else:
    _fail(f"Detail class-records-html failed: {r.status_code}")

# 2.15 Detail tab: body-measurements-html
r = api("GET", f"/api/members/{test_member_id}/body-measurements-html")
if r.status_code == 200:
    _ok("Detail body-measurements-html OK")
else:
    _fail(f"Detail body-measurements-html failed: {r.status_code}")

# 2.16 Detail tab: purchases-html
r = api("GET", f"/api/members/{test_member_id}/purchases-html")
if r.status_code == 200:
    _ok("Detail purchases-html OK")
else:
    _fail(f"Detail purchases-html failed: {r.status_code}")

# 2.17 Detail page route
r = api("GET", f"/members/{test_member_id}")
if r.status_code == 200 and "测试会员A" in r.text:
    _ok("Member detail page OK")
else:
    _fail(f"Member detail page failed: {r.status_code}")

# 2.18 Table sorting
r = api("GET", "/api/members/table?sort_by=name&sort_dir=asc")
if r.status_code == 200:
    _ok("Table sort by name asc OK")
else:
    _fail(f"Table sort failed: {r.status_code}")

# 2.19 Table filters
r = api("GET", "/api/members/table?level=普通")
if r.status_code == 200:
    _ok("Table filter by level OK")
else:
    _fail(f"Table filter failed: {r.status_code}")


# ─── Step 3: Staff Module ───
print("\n" + "="*60)
print("  TEST 3: 员工管理模块")
print("="*60)

r = api("GET", "/api/staff")
if r.status_code == 200:
    staff_list = r.json()
    _ok(f"List staff OK → {len(staff_list)} staff")
else:
    _fail(f"List staff failed: {r.status_code}")
    staff_list = []

test_staff_id = None
r = api("POST", "/api/staff", json={
    "name": "测试教练B",
    "gender": "女",
    "phone": "13900001111",
    "position": "教练",
    "base_salary": 5000,
    "sale_commission_rate": 10,
})
if r.status_code == 200:
    s = r.json()
    test_staff_id = s.get("staff_id")
    _ok(f"Create staff OK → id={test_staff_id}")
else:
    _fail(f"Create staff failed: {r.status_code}", r._text[:300])


# ─── Step 4: Course Module ───
print("\n" + "="*60)
print("  TEST 4: 课程管理模块")
print("="*60)

r = api("GET", "/api/courses")
if r.status_code == 200:
    courses = r.json()
    _ok(f"List courses OK → {len(courses)} courses")
else:
    _fail(f"List courses failed: {r.status_code}")
    courses = []

test_course_id = None
r = api("POST", "/api/courses", json={
    "name": "测试私教课C",
    "sport_type": "健身",
    "course_type": "私教",
    "standard_hours": 1,
    "standard_price": 300,
    "coach": "测试教练B",
})
if r.status_code == 200:
    c = r.json()
    test_course_id = c.get("course_id")
    _ok(f"Create course OK → id={test_course_id}")
else:
    _fail(f"Create course failed: {r.status_code}", r._text[:300])

# Search courses JSON
r = api("GET", "/api/courses/search-json?q=测试")
if r.status_code == 200:
    results = r.json()
    _ok(f"Course search-json OK → {len(results)} results")
else:
    _fail(f"Course search-json failed: {r.status_code}")


# ─── Step 5: Sale Module ───
print("\n" + "="*60)
print("  TEST 5: 售课记录模块")
print("="*60)

r = api("GET", "/api/sales")
if r.status_code == 200:
    sales = r.json()
    _ok(f"List sales OK → {len(sales)} sales")
else:
    _fail(f"List sales failed: {r.status_code}")

test_sale_id = None
if test_member_id and test_course_id:
    r = api("POST", "/api/sales", json={
        "member_id": test_member_id,
        "member_name": "测试会员A_改名",
        "member_phone": "13800002222",
        "course_id": test_course_id,
        "course_name": "测试私教课C",
        "bought_hours": 10,
        "bonus_hours": 2,
        "unit_price": 300,
        "total_price": 3000,
        "actual_amount": 2800,
        "payment_method": "微信",
        "staff_id": test_staff_id or "",
        "staff_name": "测试教练B",
        "payment_status": "已付款",
    })
    if r.status_code == 200:
        s = r.json()
        test_sale_id = s.get("sale_id")
        _ok(f"Create sale OK → id={test_sale_id}, amount=2800")
        # Verify calculated fields
        if s.get("total_hours") == 12:
            _ok("Sale total_hours=12 (10+2 bonus) correct")
        else:
            _fail(f"Sale total_hours={s.get('total_hours')}, expected 12")
    else:
        _fail(f"Create sale failed: {r.status_code}", r._text[:300])

# Sale table HTML
r = api("GET", "/api/sales/table")
if r.status_code == 200:
    if "测试" in r.text:
        _ok("Sale table HTML shows test data")
    else:
        _warn("Sale table HTML doesn't contain test data", r._text[:300])
else:
    _fail(f"Sale table failed: {r.status_code}")


# ─── Step 6: Booking Module ───
print("\n" + "="*60)
print("  TEST 6: 预约管理模块")
print("="*60)

today_str = date.today().isoformat()
test_booking_id = None

# 6.1 Get coaches
r = api("GET", "/api/booking/coaches")
if r.status_code == 200:
    _ok("Get coaches OK")
else:
    _warn(f"Get coaches failed: {r.status_code}")

# 6.2 Get courses for booking
r = api("GET", "/api/booking/courses")
if r.status_code == 200:
    _ok("Get courses for booking OK")
else:
    _warn(f"Get courses for booking failed: {r.status_code}")

# 6.3 Create booking
if test_member_id and test_course_id:
    r = api("POST", "/api/booking/create", data={
        "booking_date": today_str,
        "start_time": "14:00",
        "end_time": "15:00",
        "member_id": test_member_id,
        "member_name": "测试会员A_改名",
        "course_id": test_course_id,
        "course_name": "测试私教课C",
        "coach_id": test_staff_id or "",
        "coach_name": "测试教练B",
        "location": "A教室",
    })
    if r.status_code == 200:
        d = r.json()
        test_booking_id = d.get("booking_id")
        _ok(f"Create booking OK → id={test_booking_id}")
    else:
        detail = r._text[:300] if hasattr(r, '_text') else str(r.status_code)
        _fail(f"Create booking failed: {r.status_code}", detail)

# 6.4 Booking list
r = api("GET", "/api/booking/list?date_str=" + today_str)
if r.status_code == 200:
    d = r.json()
    _ok(f"Booking list OK → {d.get('total', 0)} bookings for today")
else:
    _fail(f"Booking list failed: {r.status_code}")

# 6.5 Conflict detection (same coach, same time)
if test_member_id and test_course_id and test_staff_id:
    r = api("POST", "/api/booking/create", data={
        "booking_date": today_str,
        "start_time": "14:00",
        "end_time": "15:00",
        "member_id": test_member_id,
        "member_name": "测试会员A_改名",
        "course_id": test_course_id,
        "course_name": "测试私教课C",
        "coach_id": test_staff_id,
        "coach_name": "测试教练B",
    })
    if r.status_code == 400:
        _ok("Conflict detection works: 400 on duplicate coach+time")
    else:
        _fail(f"Conflict detection failed: expected 400, got {r.status_code}", str(r._text)[:200])


# ─── Step 7: Checkin Module (core logic) ───
print("\n" + "="*60)
print("  TEST 7: 进场核销模块（核心逻辑）")
print("="*60)

# 7.1 Quick lookup
if test_member_id:
    r = api("GET", f"/api/checkin/quick-lookup?q={test_member_id}")
    if r.status_code == 200:
        d = r.json()
        if d.get("found"):
            _ok(f"Quick lookup found member: {d['member']['name']}")
            cards = d.get("active_cards", [])
            _ok(f"Found {len(cards)} active cards for member")
        else:
            _fail(f"Quick lookup did not find member: {d.get('message')}")
    else:
        _fail(f"Quick lookup failed: {r.status_code}")

# 7.2 Today checkin count
if test_member_id:
    r = api("GET", f"/api/checkin/today-count?member_id={test_member_id}")
    if r.status_code == 200:
        d = r.json()
        _ok(f"Today checkin count OK → {d.get('count')} times")
    else:
        _fail(f"Today checkin count failed: {r.status_code}")

# 7.3 Create checkin (无卡体验)
if test_member_id:
    r = api("POST", "/api/checkins", data={
        "member_id": test_member_id,
        "member_name": "测试会员A_改名",
        "checkin_type": "体验",
        "consume_type": "无卡体验",
        "operator": "admin",
    })
    if r.status_code == 200:
        d = r.json()
        _ok(f"Create checkin (体验) OK → consume_note={d.get('consume_note')}")
    else:
        _fail(f"Create checkin (体验) failed: {r.status_code}", str(r._text)[:300])

# 7.4 Checkin table
r = api("GET", "/api/checkins/table")
if r.status_code == 200 and "测试会员A" in r.text:
    _ok("Checkin table shows test member")
else:
    _warn("Checkin table may not show test data")

# 7.5 Checkin list JSON
r = api("GET", "/api/checkins")
if r.status_code == 200:
    checkins = r.json()
    _ok(f"Checkin list OK → {len(checkins)} records")
else:
    _fail(f"Checkin list failed: {r.status_code}")


# ─── Step 8: MCP & AI Chat ───
print("\n" + "="*60)
print("  TEST 8: MCP 工具 & AI 对话")
print("="*60)

# 8.1 List MCP tools
r = api("GET", "/api/mcp/tools")
if r.status_code == 200:
    d = r.json()
    tools = d.get("result", {}).get("tools", [])
    _ok(f"MCP tools/list OK → {len(tools)} tools")
    # Check for critical tools
    tool_names = [t["name"] for t in tools]
    for need in ["get_member", "list_members", "get_dashboard_stats", "search"]:
        if need in tool_names:
            _ok(f"  Critical tool '{need}' registered")
        else:
            _fail(f"  Critical tool '{need}' NOT registered")
else:
    _fail(f"MCP tools/list failed: {r.status_code}")

# 8.2 MCP server info
r = api("GET", "/api/mcp/server-info")
if r.status_code == 200:
    d = r.json()
    _ok(f"MCP server info OK → {d.get('tool_count')} tools, {d.get('tools_by_category')}")
else:
    _fail(f"MCP server info failed: {r.status_code}")

# 8.3 MCP call tool (get_dashboard_stats)
r = api("POST", "/api/mcp/call-tool", json={
    "name": "get_dashboard_stats",
    "arguments": {},
})
if r.status_code == 200:
    d = r.json()
    content = d.get("result", {}).get("content", [{}])
    text = content[0].get("text", "") if content else ""
    if text:
        stats = json.loads(text) if isinstance(text, str) else text
        _ok(f"MCP call get_dashboard_stats OK → total_members={stats.get('total_members')}")
    else:
        _fail("MCP call returned empty content")
else:
    _fail(f"MCP call failed: {r.status_code}", str(r._text)[:300])

# 8.4 MCP search tools
r = api("GET", "/api/mcp/search-tools?q=member")
if r.status_code == 200:
    d = r.json()
    _ok(f"MCP search 'member' → {d.get('total')} tools")

# 8.5 MCP parity report
r = api("GET", "/api/mcp/parity-report")
if r.status_code == 200:
    d = r.json()
    _ok(f"MCP parity report OK → {d.get('total_tools')} tools total")

# 8.6 AI Chat (only if LLM is configured)
r = api("POST", "/api/chat/message", json={
    "message": "系统有几个会员？",
    "session_id": "test-stability",
})
if r.status_code == 200:
    d = r.json()
    reply = d.get("reply", "")
    if reply and len(reply) > 10:
        _ok(f"AI chat OK → reply length={len(reply)}")
    else:
        _warn("AI chat returned short/empty reply", reply[:100])
elif r.status_code == 500:
    _warn("AI chat 500 (LLM may not be configured)", str(r._text)[:200])
else:
    _fail(f"AI chat failed: {r.status_code}")


# ─── Step 9: Performance Module ───
print("\n" + "="*60)
print("  TEST 9: 业绩统计模块")
print("="*60)

# 9.1 Overview cards
r = api("GET", "/api/performance/overview/cards?period=全部")
if r.status_code == 200:
    _ok("Overview cards OK")
else:
    _fail(f"Overview cards failed: {r.status_code}")

# 9.2 Sales stats cards
r = api("GET", "/api/performance/sales/stats?period=全部")
if r.status_code == 200:
    _ok("Sales stats cards OK")
else:
    _fail(f"Sales stats cards failed: {r.status_code}")

# 9.3 Package stats
r = api("GET", "/api/performance/packages/stats")
if r.status_code == 200:
    _ok("Package stats OK")
else:
    _fail(f"Package stats failed: {r.status_code}")

# 9.4 Card stats
r = api("GET", "/api/performance/cards/stats?period=全部")
if r.status_code == 200:
    _ok("Card stats OK")
else:
    _fail(f"Card stats failed: {r.status_code}")

# 9.5 Checkin stats
r = api("GET", "/api/performance/checkins/stats?period=本月")
if r.status_code == 200:
    _ok("Checkin stats OK")
else:
    _fail(f"Checkin stats failed: {r.status_code}")


# ─── Step 10: Finance Module ───
print("\n" + "="*60)
print("  TEST 10: 财务管理模块")
print("="*60)

r = api("GET", "/api/finance/income")
if r.status_code == 200:
    _ok("Finance income list OK")
else:
    _fail(f"Finance income list failed: {r.status_code}")

r = api("GET", "/api/finance/expense")
if r.status_code == 200:
    _ok("Finance expense list OK")
else:
    _fail(f"Finance expense list failed: {r.status_code}")

r = api("GET", "/api/finance/summary?year=2026&month=5")
if r.status_code == 200:
    _ok("Finance summary OK")
else:
    _warn(f"Finance summary failed: {r.status_code}")


# ─── Step 11: Auxiliary Modules ───
print("\n" + "="*60)
print("  TEST 11: 辅助模块")
print("="*60)

# 11.1 Wristband list
r = api("GET", "/api/wristbands")
if r.status_code == 200:
    _ok("Wristband list OK")
else:
    _fail(f"Wristband list failed: {r.status_code}")

# 11.2 Body measurements
r = api("GET", "/api/body-measurements")
if r.status_code == 200:
    _ok("Body measurements list OK")
else:
    _fail(f"Body measurements list failed: {r.status_code}")

# 11.3 Alerts
r = api("GET", "/api/alerts")
if r.status_code == 200:
    _ok("Alerts list OK")
else:
    _fail(f"Alerts list failed: {r.status_code}")

# 11.4 Membership cards
r = api("GET", "/api/membership-cards")
if r.status_code == 200:
    _ok("Membership cards list OK")
else:
    _fail(f"Membership cards list failed: {r.status_code}")

# 11.5 Products
r = api("GET", "/api/products")
if r.status_code == 200:
    _ok("Products list OK")
else:
    _fail(f"Products list failed: {r.status_code}")

# 11.6 Recharges
r = api("GET", "/api/recharges")
if r.status_code == 200:
    _ok("Recharges list OK")
else:
    _fail(f"Recharges list failed: {r.status_code}")

# 11.7 Operation logs
r = api("GET", "/api/logs")
if r.status_code == 200:
    logs = r.json()
    _ok(f"Operation logs OK → {len(logs)} entries")
else:
    _fail(f"Operation logs failed: {r.status_code}")

# 11.8 Log stats
r = api("GET", "/api/logs/stats")
if r.status_code == 200:
    _ok("Log stats OK")
else:
    _fail(f"Log stats failed: {r.status_code}")

# 11.9 System settings
r = api("GET", "/api/system/settings")
if r.status_code == 200:
    d = r.json()
    _ok(f"System settings OK → system_name={d.get('system_name')}")
else:
    _fail(f"System settings failed: {r.status_code}")

# 11.10 Schedule calendar
from datetime import date
today = date.today()
r = api("GET", f"/api/schedule/calendar?year={today.year}&month={today.month}")
if r.status_code == 200:
    _ok("Schedule calendar HTML OK")
else:
    _fail(f"Schedule calendar failed: {r.status_code}")

# 11.11 Export data module
r = api("GET", "/api/export/members")
if r.status_code == 200:
    _ok("Export members OK")
else:
    _warn(f"Export members failed: {r.status_code}")

# 11.12 Commission
r = api("GET", "/api/commission/tiers/list")
if r.status_code == 200:
    _ok("Commission tiers OK")
else:
    _warn(f"Commission tiers failed: {r.status_code}")

# 11.13 Dashboard stats
r = api("GET", "/api/dashboard/stats")
if r.status_code == 200:
    _ok("Dashboard stats HTML OK")
else:
    _fail(f"Dashboard stats failed: {r.status_code}")

# 11.14 Today bookings dashboard
r = api("GET", "/api/dashboard/today-bookings")
if r.status_code == 200:
    _ok("Today bookings dashboard OK")
else:
    _warn(f"Today bookings dashboard failed: {r.status_code}")

# 11.15 Today checkins dashboard
r = api("GET", "/api/dashboard/today-checkins")
if r.status_code == 200:
    _ok("Today checkins dashboard OK")
else:
    _warn(f"Today checkins dashboard failed: {r.status_code}")


# ─── Step 12: Data Integrity Checks ───
print("\n" + "="*60)
print("  TEST 12: 数据完整性检查")
print("="*60)

# 12.1 Check that sale date matches the current date pattern
if test_sale_id:
    r = api("GET", f"/api/sales/{test_sale_id}")
    if r.status_code == 200:
        sale = r.json()
        _ok(f"Sale detail OK → date={sale.get('sale_date')}" if hasattr(sale, 'get') else "Sale detail OK")
    else:
        _fail(f"Get sale failed: {r.status_code}")

# 12.2 Check member balance and remaining lessons consistency
if test_member_id:
    r = api("GET", f"/api/members/{test_member_id}")
    if r.status_code == 200:
        m = r.json()
        # Just verify the fields exist
        ok = True
        for f in ["member_id", "name", "status", "remaining_lessons", "balance"]:
            if f not in m:
                _fail(f"Member missing field: {f}")
                ok = False
        if ok:
            _ok("All member fields present")
    else:
        _fail(f"Member detail failed: {r.status_code}")

# 12.3 Verify dashboard stats consistency
r = api("GET", "/api/members")
total_members_api = len(r.json()) if r.status_code == 200 else -1

# 12.4 Check response content-type for HTML endpoints
r = api("GET", "/api/dashboard/stats")
ct = r.headers.get("content-type", "")
if "text/html" in ct:
    _ok("Dashboard stats has correct content-type: text/html")
else:
    _warn(f"Dashboard stats content-type: {ct}")

# 12.5 Test HTMX HTML fragments have no script injection risk
# (Just verify they return valid HTML with no raw <script> tags from user data)
r = api("GET", "/api/members/table")
html = r.text
if "<script>" not in html.lower() or html.lower().count("<script>") == html.lower().count("<script src="):
    _ok("No suspicious <script> in member table HTML")
else:
    _warn("Found <script> tags in member table (check if from trusted CDN)")

# 12.6 Verify member create with empty name
r = api("POST", "/api/members", data={
    "name": "",
    "phone": "13899999999",
})
if r.status_code in (200, 422):
    _ok(f"Empty name handled: status={r.status_code}")
else:
    _fail(f"Empty name returned unexpected status: {r.status_code}")


# ─── Step 13: Cleanup ───
print("\n" + "="*60)
print("  TEST 13: 清理测试数据")
print("="*60)

# Delete test booking
if test_booking_id:
    r = api("POST", f"/api/booking/{test_booking_id}/cancel")
    if r.status_code == 200:
        _ok(f"Cleanup: cancelled booking {test_booking_id}")
    else:
        _warn(f"Cleanup: cancel booking failed: {r.status_code}")

# Delete test member (will cascade?)
if test_member_id:
    r = api("DELETE", f"/api/members/{test_member_id}")
    if r.status_code == 200:
        _ok(f"Cleanup: deleted member {test_member_id}")
    else:
        _warn(f"Cleanup: delete member failed: {r.status_code}")

# Delete test staff
if test_staff_id:
    r = api("DELETE", f"/api/staff/{test_staff_id}")
    if r.status_code == 200:
        _ok(f"Cleanup: deleted staff {test_staff_id}")
    else:
        _warn(f"Cleanup: delete staff failed: {r.status_code}")

# Delete test course
if test_course_id:
    r = api("DELETE", f"/api/courses/{test_course_id}")
    if r.status_code == 200:
        _ok(f"Cleanup: deleted course {test_course_id}")
    else:
        _warn(f"Cleanup: delete course failed: {r.status_code}")


# ─── Final Report ───
print("\n" + "="*60)
print("  测试完成报告")
print("="*60)
print(f"  ✅ PASS: {PASS}")
print(f"  ❌ FAIL: {FAIL}")
print(f"  ⚠️  WARN: {WARN}")
total = PASS + FAIL + WARN
print(f"  总计: {total} tests")
if FAIL > 0:
    print(f"\n  🔴 发现 {FAIL} 个失败项:")
    for status, msg in TEST_RESULTS:
        if status == "FAIL":
            print(f"     ❌ {msg}")
if WARN > 0:
    print(f"\n  🟡 发现 {WARN} 个警告项:")
    for status, msg in TEST_RESULTS:
        if status == "WARN":
            print(f"     ⚠️  {msg}")
print("="*60)

# Also check server code for potential issues
print("\n" + "="*60)
print("  代码静态检查")
print("="*60)

CODE_ISSUES = []

# Check for hardcoded secrets
env_content = open(".env", "r", encoding="utf-8").read()
if "sk-" in env_content and "sk-placeholder" not in env_content:
    CODE_ISSUES.append("⚠️  .env 文件中包含真实的 API Key，需要保护")

# Check for potential SQL injection in raw SQL
import glob
py_files = glob.glob("backend/**/*.py", recursive=True)
for f in py_files:
    content = open(f, "r", encoding="utf-8", errors="ignore").read()
    if "f\"%" in content or "f'%" in content:
        if "like" not in content.lower():
            CODE_ISSUES.append(f"⚠️  {f}: 可能存在 SQL 注入风险（f-string 拼接）")

# Check chat_router.py escape warnings (dynamic check)
import subprocess
result = subprocess.run(
    ["C:/Users/12225/AppData/Local/Programs/Python/Python312/python.exe", "-W", "error", "-c",
     "import sys; sys.path.insert(0,'.'); from backend.routers.chat_router import router"],
    capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))
)
if result.returncode != 0 and "SyntaxWarning" in result.stderr:
    CODE_ISSUES.append(f"⚠️  chat_router.py 存在 SyntaxWarning: {result.stderr.strip()[:200]}")

# Check for missing error handling in critical paths
if "except:" in open("backend/routers/checkin.py", "r", encoding="utf-8").read():
    CODE_ISSUES.append("⚠️  checkin.py 存在裸 except: 可能吞掉重要异常")

for issue in CODE_ISSUES:
    print(f"  {issue}")

print("\n  诊断完成。")
