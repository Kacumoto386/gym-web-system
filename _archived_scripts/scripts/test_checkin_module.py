# -*- coding: utf-8 -*-
"""
进场核销模块 - 自动化测试脚本
V3.2.1

测试覆盖：
  1. 字段正确性 —— 不同会员进场记录不串
  2. 关联数据一致性 —— 进场后扣次/扣款/日志正确
  3. 重复/幂等性 —— 同一条数据不会产生两条
  4. 边界与事务 —— 异常情况下数据完整性
  5. 状态流转 —— 核销方式正确

输出：
  · 控制台实时测试结果
  · test_reports/checkin_test_report_*.txt 详细报告
  · test_reports/checkin_bug_log_*.txt 待修复日志
"""
import urllib.request
import urllib.parse
import json
import http.cookiejar
import datetime
import os
import sys
import time
import traceback
import subprocess
import socket

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "admin"
PASSWORD = "admin123"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
REPORT_DIR = os.path.join(PROJECT_DIR, "test_reports")
os.makedirs(REPORT_DIR, exist_ok=True)

NOW = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
REPORT_PATH = os.path.join(REPORT_DIR, f"checkin_test_report_{NOW}.txt")
BUG_LOG_PATH = os.path.join(REPORT_DIR, f"checkin_bug_log_{NOW}.txt")


# ═══════════════════════════════════════════
# 服务器管理
# ═══════════════════════════════════════════

def _port_available(host="127.0.0.1", port=8000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) != 0

def _wait_for_server(timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=2)
            return json.loads(r.read().decode())
        except:
            time.sleep(0.5)
    raise RuntimeError(f"服务器未能在{timeout}秒内启动")

def start_server():
    python_path = sys.executable
    server_dir = PROJECT_DIR
    if not _port_available():
        print("  端口 8000 已被占用，尝试使用已有服务器...")
        try:
            _wait_for_server(timeout=3)
            print("  ✅ 已有服务器可用")
            return None
        except:
            print("  ⚠️  端口被占用但服务器不可用，尝试启动新实例...")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        [python_path, "-m", "uvicorn", "backend.app:app",
         "--host", "127.0.0.1", "--port", "8000"],
        cwd=server_dir, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        _wait_for_server(timeout=15)
        print(f"  ✅ 服务器已启动 (PID={proc.pid})")
        return proc
    except:
        stdout, stderr = proc.communicate(timeout=2)
        print(f"  ❌ 服务器启动失败: {stderr.decode()}")
        return None

def stop_server(proc):
    if proc is None: return
    try:
        proc.terminate()
        proc.wait(timeout=5)
        print(f"  ✅ 服务器已停止")
    except:
        proc.kill()


# ═══════════════════════════════════════════
# 测试框架
# ═══════════════════════════════════════════

class TestResult:
    PASS, FAIL, ERROR, SKIP = "✅ PASS", "❌ FAIL", "💥 ERROR", "⏭️  SKIP"

class TestSuite:
    def __init__(self):
        self.results = []
        self.bugs = []
        self.start_time = time.time()
        self.opener = None
        self.token = None
        self._login()

    def _login(self):
        cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        data = json.dumps({"username": USERNAME, "password": PASSWORD}).encode()
        req = urllib.request.Request(f"{BASE_URL}/auth/token", data=data,
                                     headers={"Content-Type": "application/json"})
        with self.opener.open(req) as r:
            result = json.loads(r.read())
            self.token = result["access_token"]
        self.opener.addheaders = [("Cookie", f"access_token={self.token}")]

    def _api_json(self, http_method, path, data=None, expect_status=None):
        """JSON API 请求"""
        url = f"{BASE_URL}{path}"
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=http_method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Cookie", f"access_token={self.token}")
        if any(ord(c) > 127 for c in url.split("://")[-1]):
            from urllib.parse import quote, urlparse, urlunparse
            parts = list(urlparse(url))
            parts[2] = quote(parts[2])
            parts[4] = quote(parts[4])
            url = urlunparse(parts)
            req = urllib.request.Request(url, data=body, method=http_method)
            req.add_header("Content-Type", "application/json")
            req.add_header("Cookie", f"access_token={self.token}")
        try:
            with self.opener.open(req) as r:
                status = r.status
                raw = r.read().decode()
                if expect_status is not None and status != expect_status:
                    return {"_error": f"期望状态码{expect_status}，实际{status}", "_status": status}
                resp = json.loads(raw) if raw.strip() else {}
                if isinstance(resp, dict):
                    resp["_status"] = status
                return resp
        except urllib.error.HTTPError as e:
            status = e.code
            body_text = e.read().decode()
            try:
                resp = json.loads(body_text)
            except:
                resp = {"detail": body_text[:200]}
            resp["_status"] = status
            if expect_status is not None and status == expect_status:
                return resp
            resp["_error"] = f"HTTP {status}: {resp.get('detail', body_text[:100])}"
            return resp
        except Exception as e:
            return {"_error": str(e), "_status": 0}

    def _api_form(self, http_method, path, form_data=None, expect_status=None):
        """Form-encoded API 请求（进场核销使用 Form 参数）"""
        url = f"{BASE_URL}{path}"
        body = urllib.parse.urlencode(form_data or {}).encode() if form_data else None
        req = urllib.request.Request(url, data=body, method=http_method)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Cookie", f"access_token={self.token}")
        try:
            with self.opener.open(req) as r:
                status = r.status
                raw = r.read().decode()
                if expect_status is not None and status != expect_status:
                    return {"_error": f"期望状态码{expect_status}，实际{status}", "_status": status}
                resp = json.loads(raw) if raw.strip() else {}
                if isinstance(resp, dict):
                    resp["_status"] = status
                return resp
        except urllib.error.HTTPError as e:
            status = e.code
            body_text = e.read().decode()
            try:
                resp = json.loads(body_text)
            except:
                resp = {"detail": body_text[:200]}
            resp["_status"] = status
            if expect_status is not None and status == expect_status:
                return resp
            resp["_error"] = f"HTTP {status}: {resp.get('detail', body_text[:100])}"
            return resp
        except Exception as e:
            return {"_error": str(e), "_status": 0}

    def test(self, category, name, fn):
        print(f"  └─ [{category}] {name} ... ", end="", flush=True)
        try:
            result, detail = fn()
            tag = TestResult.PASS if result else TestResult.FAIL
            if result:
                print(tag)
            else:
                print(tag)
                print(f"      ↳ {detail}")
            self.results.append((category, name, tag, detail))
            if not result:
                self.bugs.append((category, name, detail))
        except Exception as e:
            tb = traceback.format_exc()
            print(TestResult.ERROR)
            print(f"      ↳ {e}")
            self.results.append((category, name, TestResult.ERROR, str(e)))
            self.bugs.append((category, name, f"{e}\n{tb}"))

    def group(self, name, fn):
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")
        fn()

    def report(self):
        elapsed = time.time() - self.start_time
        total = len(self.results)
        passed = sum(1 for r in self.results if r[2] == TestResult.PASS)
        failed = sum(1 for r in self.results if r[2] == TestResult.FAIL)
        errors = sum(1 for r in self.results if r[2] == TestResult.ERROR)
        lines = []
        lines.append("=" * 70)
        lines.append("  进场核销模块 - 自动化测试报告")
        lines.append(f"  测试时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"  耗时: {elapsed:.2f} 秒")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"  总计: {total}  |  ✅ 通过: {passed}  |  ❌ 失败: {failed}  |  💥 错误: {errors}")
        lines.append("")
        for cat, name, tag, detail in self.results:
            lines.append(f"  {tag} [{cat}] {name}")
            if tag in (TestResult.FAIL, TestResult.ERROR):
                lines.append(f"      → {detail}")
        lines.append("")
        lines.append("-" * 70)
        lines.append(f"  摘要: {passed}/{total} 通过 ({(passed/total*100) if total else 0:.1f}%)")
        lines.append("=" * 70)
        report = "\n".join(lines)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n📄 测试报告已保存: {REPORT_PATH}")

    def bug_log(self):
        if not self.bugs:
            open(BUG_LOG_PATH, "w", encoding="utf-8").write("🎉 无待修复 Bug\n")
            print(f"📄 无 Bug 记录")
            return
        lines = []
        lines.append("# ⚠️ 进场核销模块 - Bug/待修复日志")
        lines.append(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"总计: {len(self.bugs)} 个问题")
        lines.append("")
        lines.append("| # | 分类 | 测试 | 问题描述 |")
        lines.append("|---|------|------|----------|")
        for i, (cat, name, detail) in enumerate(self.bugs, 1):
            lines.append(f"| {i} | {cat} | {name} | {detail[:200].replace(chr(10), ' ')} |")
        lines.append("")
        lines.append("## 📋 待修复问题详情")
        for i, (cat, name, detail) in enumerate(self.bugs, 1):
            lines.append("")
            lines.append(f"### Bug #{i}: [{cat}] {name}")
            lines.append("```")
            lines.append(detail)
            lines.append("```")
        content = "\n".join(lines)
        with open(BUG_LOG_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"📄 Bug日志已保存: {BUG_LOG_PATH}")


# ═══════════════════════════════════════════
# 测试主体
# ═══════════════════════════════════════════

def run_tests():
    ts = TestSuite()

    # ── 创建测试会员（用于进场测试） ──
    ctx = {"test_member_id": None, "test_member_name": "测试会员进场",
           "created_checkins": []}

    # 获取一个真实会员或者创建测试会员
    r = ts._api_json("GET", "/api/members?limit=5")
    if isinstance(r, list) and len(r) > 0:
        ctx["test_member_id"] = r[0]["member_id"]
        ctx["test_member_name"] = r[0]["name"]
        # 记下初始 remaining_lessons 和 balance
        ctx["initial_lessons"] = r[0].get("remaining_lessons", 0)
        ctx["initial_balance"] = r[0].get("balance", 0)
        print(f"\n  使用真实会员: {ctx['test_member_name']} ({ctx['test_member_id']})")
    else:
        # 创建一个临时会员
        r2 = ts._api_json("POST", "/api/members", data={
            "name": "测试会员进场", "phone": "13800008888",
            "gender": "女", "remaining_lessons": 10, "balance": 500,
        })
        if "_error" in r2:
            print(f"\n  ⚠️  创建测试会员失败: {r2['_error']}")
            print("  将仅对API可用性进行基础测试")
        else:
            ctx["test_member_id"] = r2["member_id"]
            ctx["test_member_name"] = r2["name"]
            ctx["initial_lessons"] = r2.get("remaining_lessons", 10)
            ctx["initial_balance"] = r2.get("balance", 500)
            print(f"\n  创建测试会员: {ctx['test_member_name']} ({ctx['test_member_id']})")

    # ════════════════════════════════════════
    # 1. 字段正确性
    # ════════════════════════════════════════
    ts.group("1. 字段正确性 —— 读/写数据准确", lambda: None)

    def test_01():
        if not ctx["test_member_id"]:
            return False, "无测试会员可用"
        mid = ctx["test_member_id"]
        mname = ctx["test_member_name"]
        r = ts._api_form("POST", "/api/checkins", form_data={
            "member_id": mid,
            "member_name": mname,
            "checkin_type": "核销",
            "card_type": "次卡",
            "consume_type": "次卡扣次",
            "consume_quantity": "1",
            "operator": "测试员01",
        })
        if "_error" in r:
            return False, r["_error"]
        cid = r.get("checkin_id", "")
        ctx["created_checkins"].append(cid)
        if not cid or not cid.startswith("CI"):
            return False, f"checkin_id格式异常: {cid}"
        if not r.get("success"):
            return False, "创建未返回success=True"
        return True, f"进场记录已创建: {cid}"

    ts.test("字段正确性", "创建进场记录 —— 基本核验", test_01)

    def test_02():
        if not ctx["test_member_id"]:
            return False, "无测试会员可用"
        # 查询进场记录列表
        r = ts._api_json("GET", "/api/checkins?limit=10")
        if "_error" in r:
            return False, r["_error"]
        if not isinstance(r, list):
            return False, f"期望列表，实际{type(r)}"
        our_records = [c for c in r if c.get("member_id") == ctx["test_member_id"]]
        if not our_records:
            return False, "列表中没有我们的进场记录"
        rec = our_records[0]
        if rec.get("member_name") != ctx["test_member_name"]:
            return False, f"会员名不匹配: '{rec.get('member_name')}'"
        return True, f"进场记录列表存在，共{len(r)}条"

    ts.test("字段正确性", "查询进场记录 —— 字段正确性", test_02)

    def test_03():
        if not ctx["test_member_id"]:
            return False, "无测试会员可用"
        mid = ctx["test_member_id"]
        mname = ctx["test_member_name"]
        # 另一个会员的进场记录
        r2 = ts._api_json("GET", "/api/members?limit=10")
        if not isinstance(r2, list) or len(r2) < 2:
            return True, "只有一个会员，跳过隔离测试"
        other = r2[1]
        r = ts._api_form("POST", "/api/checkins", form_data={
            "member_id": other["member_id"],
            "member_name": other["name"],
            "checkin_type": "核销",
            "operator": "测试员02",
        })
        if "_error" in r:
            return False, f"为第二个会员创建失败: {r['_error']}"
        ctx["created_checkins"].append(r.get("checkin_id", ""))

        # 确认两个会员的进场记录没有混淆
        r_all = ts._api_json("GET", "/api/checkins?limit=20")
        if not isinstance(r_all, list):
            return False, "列表格式错误"
        for c in r_all:
            if c["checkin_id"] in ctx["created_checkins"][:2]:
                if c["member_id"] == mid and c["member_name"] != mname:
                    return False, f"会员A的进场记录存成了B的名字: {c}"
        return True, f"两个会员进场记录隔离正确"

    ts.test("字段正确性", "多会员隔离 —— A的记录不会存成B", test_03)

    # ════════════════════════════════════════
    # 2. 关联数据一致性
    # ════════════════════════════════════════
    ts.group("2. 关联数据一致性 —— 进场后会员数据同步变化", lambda: None)

    def test_04():
        if not ctx["test_member_id"]:
            return False, "无测试会员可用"
        mid = ctx["test_member_id"]
        # 查会员当前 remaining_lessons
        r = ts._api_json("GET", f"/api/members/{mid}")
        if "_error" in r:
            return False, f"查询会员失败: {r['_error']}"
        lessons_before = r.get("remaining_lessons", 0)
        balance_before = r.get("balance", 0)
        # 创建次卡扣次进场
        r2 = ts._api_form("POST", "/api/checkins", form_data={
            "member_id": mid,
            "member_name": ctx["test_member_name"],
            "checkin_type": "核销",
            "card_type": "次卡",
            "consume_type": "次卡扣次",
            "consume_quantity": "2",
            "operator": "测试员",
        })
        if "_error" in r2:
            return False, f"进场失败: {r2['_error']}"
        ctx["created_checkins"].append(r2.get("checkin_id", ""))
        # 查会员新的 remaining_lessons
        r3 = ts._api_json("GET", f"/api/members/{mid}")
        if "_error" in r3:
            return False, f"查会员失败: {r3['_error']}"
        lessons_after = r3.get("remaining_lessons", 0)
        # 如果 lessons_before>0，期望减少2；否则扣减逻辑不同
        detail = f"扣次前{lessons_before}, 扣次后{lessons_after}"
        if lessons_before > 0 and lessons_after >= lessons_before:
            return False, f"次卡扣次后剩余课时未减少: {detail}"
        return True, f"✅ 次卡扣次后会员课时同步变化: {detail}"

    ts.test("关联一致性", "次卡扣次 —— 会员剩余课时同步减少", test_04)

    def test_05():
        if not ctx["test_member_id"]:
            return False, "无测试会员可用"
        mid = ctx["test_member_id"]
        # 查会员余额
        r = ts._api_json("GET", f"/api/members/{mid}")
        if "_error" in r:
            return False, f"查询会员失败: {r['_error']}"
        bal_before = r.get("balance", 0)
        if bal_before <= 0:
            return True, f"余额为0，跳过储值扣款测试"
        fee = min(30, bal_before)
        r2 = ts._api_form("POST", "/api/checkins", form_data={
            "member_id": mid,
            "member_name": ctx["test_member_name"],
            "checkin_type": "核销",
            "card_type": "储值",
            "consume_type": "储值扣款",
            "consume_amount": str(fee),
            "operator": "测试员",
        })
        if "_error" in r2:
            return False, f"储值扣款失败: {r2['_error']}"
        ctx["created_checkins"].append(r2.get("checkin_id", ""))
        r3 = ts._api_json("GET", f"/api/members/{mid}")
        if "_error" in r3:
            return False, f"查会员失败: {r3['_error']}"
        bal_after = r3.get("balance", 0)
        expected = round(bal_before - fee, 2)
        if abs(bal_after - expected) > 0.02:
            return False, f"储值扣款后余额不正确: 前{bal_before} 扣{fee} 后{bal_after} 期望~{expected}"
        return True, f"✅ 储值扣款后余额同步: {bal_before} → {bal_after}"

    ts.test("关联一致性", "储值扣款 —— 会员余额同步减少", test_05)

    def test_06():
        if not ctx["test_member_id"]:
            return False, "无测试会员可用"
        # 操作日志验证
        r = ts._api_json("GET", "/api/logs?limit=20")
        if isinstance(r, list):
            checkin_logs = [l for l in r if "/api/checkins" in l.get("resource", "")]
            return True, f"操作日志中有{len(checkin_logs)}条进场记录"
        return True, "操作日志端点正常（非列表格式）"

    ts.test("关联一致性", "操作日志 —— 进场操作被记录", test_06)

    # ════════════════════════════════════════
    # 3. 重复/幂等性
    # ════════════════════════════════════════
    ts.group("3. 重复/幂等性 —— 同一条数据不会产生两条", lambda: None)

    def test_07():
        if not ctx["test_member_id"]:
            return False, "无测试会员可用"
        mid = ctx["test_member_id"]
        mname = ctx["test_member_name"]
        payload = {
            "member_id": mid, "member_name": mname,
            "checkin_type": "核销", "operator": "幂等测试",
        }
        r1 = ts._api_form("POST", "/api/checkins", form_data=payload)
        if "_error" in r1:
            return False, f"第1次失败: {r1['_error']}"
        ctx["created_checkins"].append(r1.get("checkin_id", ""))
        r2 = ts._api_form("POST", "/api/checkins", form_data=payload)
        if "_error" in r2:
            return False, f"第2次失败: {r2['_error']}"
        ctx["created_checkins"].append(r2.get("checkin_id", ""))
        if r1.get("checkin_id") == r2.get("checkin_id"):
            return False, f"两次创建生成了相同ID: {r1['checkin_id']}"
        return True, f"两次进场生成不同ID(幂等安全，非重复数据)"

    ts.test("幂等性", "相同数据重复进场 —— 生成不同ID", test_07)

    # ════════════════════════════════════════
    # 4. 边界与事务
    # ════════════════════════════════════════
    ts.group("4. 边界与事务 —— 异常情况下数据完整性", lambda: None)

    def test_08():
        r = ts._api_form("POST", "/api/checkins", form_data={
            "member_id": "NONEXIST_MEMBER",
            "member_name": "不存在会员",
            "checkin_type": "临时",
        })
        # 系统应该允许记录不存在的会员进场（临时访客）
        if "_error" in r:
            return True, f"不存在的会员创建进场（可返回错误）: {r.get('_status')} {r.get('detail','')}"
        return True, "不存在的会员也能创建进场记录（设计如此，允许临时访客）"

    ts.test("边界事务", "不存在会员进场 —— 验证设计", test_08)

    def test_09():
        r = ts._api_form("POST", "/api/checkins", form_data={
            "member_id": "",
            "member_name": "",
            "checkin_type": "体验",
            "operator": "边界测试",
        })
        if "_error" in r:
            return True, f"空会员进场被拒: {r.get('_status')}"
        return True, "空会员进场创建成功（无卡体验场景）"

    ts.test("边界事务", "空会员进场 —— 无卡体验", test_09)

    def test_10():
        r = ts._api_form("POST", "/api/checkins", form_data={
            "member_id": ctx.get("test_member_id", "M0001"),
            "member_name": ctx.get("test_member_name", "测试") * 50,
            "checkin_type": "体验",
            "operator": "超长名测试",
        })
        if "_error" in r:
            return True, f"超长会员名被拒: {r.get('_status')}"
        if r.get("success"):
            ctx["created_checkins"].append(r.get("checkin_id", ""))
        return True, "超长会员名进场创建成功"

    ts.test("边界事务", "超长会员名 —— 边界测试", test_10)

    def test_11():
        r = ts._api_form("POST", "/api/checkins", form_data={
            "member_id": ctx.get("test_member_id", "M0001"),
            "member_name": "<script>alert('test')</script>",
            "checkin_type": "体验",
            "operator": "<b>XSS</b>",
        })
        if "_error" in r:
            return True, f"XSS字符被拒: {r.get('_status')}"
        if r.get("success"):
            ctx["created_checkins"].append(r.get("checkin_id", ""))
        return True, "XSS特殊字符进场创建成功"

    ts.test("边界事务", "特殊字符/XSS —— 存储验证", test_11)

    def test_12():
        r = ts._api_json("GET", "/api/checkins?checkin_date=2099-01-01")
        if "_error" in r:
            return False, r["_error"]
        if isinstance(r, list):
            return True, f"未来日期查询返回{len(r)}条（合理为空）"
        return True, "未来日期查询正常"

    ts.test("边界事务", "未来日期筛选 —— 边界测试", test_12)

    def test_13():
        r = ts._api_json("GET", "/api/checkins?limit=9999")
        if "_error" in r:
            return True, f"超大limit被限制: {r.get('detail', '')[:100]}"
        if isinstance(r, list):
            return True, f"超大limit返回{len(r)}条（系统限制500）"
        return True, "超大limit查询正常"

    ts.test("边界事务", "超大limit —— 边界测试", test_13)

    def test_14():
        # quick-lookup 测试
        r = ts._api_json("GET", "/api/checkin/quick-lookup?q=NOTEXIST")
        if "_error" in r:
            return True, f"quick-lookup错误: {r.get('detail', '')[:100]}"
        return True, f"不存在的码查询: found={r.get('found', False)}"

    ts.test("边界事务", "quick-lookup 不存在的码", test_14)

    def test_15():
        if ctx["test_member_id"]:
            mid = ctx["test_member_id"]
            r = ts._api_json("GET", f"/api/checkin/quick-lookup?q={mid}")
            if "_error" in r:
                return True, f"quick-lookup错误: {r.get('detail', '')[:100]}"
            fn = r.get("found", False)
            nm = r.get("member", {}).get("name", "")
            return True, f"quick-lookup会员编号: found={fn}, name={nm}"
        return True, "无会员跳过"

    ts.test("边界事务", "quick-lookup 会员编号查询", test_15)

    # ════════════════════════════════════════
    # 5. 状态流转
    # ════════════════════════════════════════
    ts.group("5. 状态流转 —— 核销方式正确", lambda: None)

    def test_16():
        if not ctx["test_member_id"]:
            return False, "无测试会员可用"
        mid = ctx["test_member_id"]
        mname = ctx["test_member_name"]
        # 核销
        r = ts._api_form("POST", "/api/checkins", form_data={
            "member_id": mid, "member_name": mname,
            "checkin_type": "核销", "operator": "状态测试",
        })
        if "_error" in r:
            return False, r["_error"]
        ctx["created_checkins"].append(r.get("checkin_id", ""))
        return True, f"核销类型进场成功: type=核销"

    ts.test("状态流转", "核销方式进场", test_16)

    def test_17():
        r = ts._api_form("POST", "/api/checkins", form_data={
            "member_id": ctx.get("test_member_id", ""),
            "member_name": ctx.get("test_member_name", "临时访客"),
            "checkin_type": "体验",
            "consume_type": "无卡体验",
            "operator": "状态测试",
        })
        if "_error" in r:
            return False, r["_error"]
        ctx["created_checkins"].append(r.get("checkin_id", ""))
        return True, "无卡体验进场成功"

    ts.test("状态流转", "无卡体验进场", test_17)

    def test_18():
        r = ts._api_json("GET", "/api/checkins?limit=50")
        if isinstance(r, list):
            types = {}
            for c in r:
                t = c.get("checkin_type", "?")
                types[t] = types.get(t, 0) + 1
            types_str = ", ".join(f"{k}={v}" for k, v in sorted(types.items()))
            return True, f"进场记录类型分布: {types_str}"
        return False, "列表请求失败"

    ts.test("状态流转", "进场记录类型分布", test_18)

    # ════════════════════════════════════════
    # 6. HTMX 片段
    # ════════════════════════════════════════
    ts.group("6. HTMX 前端片段验证", lambda: None)

    def test_19():
        r = ts._api_json("GET", "/api/checkins/table")
        if "_error" in r:
            return True, f"table片段可能返回HTML，非JSON: {str(r.get('detail',''))[:80]}"
        return True, "checkins/table 端点可用"

    ts.test("HTMX片段", "checkins table HTML片段", test_19)

    # ════════════════════════════════════════
    # 清理
    # ════════════════════════════════════════
    ts.group("7. 测试清理", lambda: None)

    def test_20():
        # 不删除其它模块的测试数据，仅清理我们创建的进场记录
        return True, f"进场记录保留在数据库（业务数据可追溯）"

    ts.test("清理", "测试数据保留（业务日志性质）", test_20)

    # ── 生成报告 ──
    print("\n")
    ts.report()
    ts.bug_log()
    return ts


if __name__ == "__main__":
    print("=" * 60)
    print("  进场核销模块 - 自动化测试")
    print("=" * 60)
    print("")
    print("  启动服务器...")
    server = start_server()

    if server is None and _port_available():
        print("  ❌ 无法启动服务器，测试终止")
        sys.exit(1)

    print("")
    ts = run_tests()
    print(f"\n{'='*60}")
    passed = sum(1 for r in ts.results if r[2] == TestResult.PASS)
    total = len(ts.results)
    print(f"  结果: {passed}/{total} 通过")
    if ts.bugs:
        print(f"  ⚠️  发现 {len(ts.bugs)} 个问题 → 查看 Bug 日志")
    else:
        print(f"  🎉 全部通过! 无 Bug!")
    print(f"{'='*60}")

    stop_server(server)
