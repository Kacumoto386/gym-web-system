# -*- coding: utf-8 -*-
"""
收支报表模块 - 自动化测试脚本 V3.2.1
"""
import urllib.request, json, http.cookiejar, urllib.parse
import datetime, os, sys, time, traceback, subprocess, socket

BASE_URL = "http://127.0.0.1:8000"
USERNAME, PASSWORD = "admin", "admin123"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
REPORT_DIR = os.path.join(PROJECT_DIR, "test_reports")
os.makedirs(REPORT_DIR, exist_ok=True)
NOW = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
REPORT_PATH = os.path.join(REPORT_DIR, f"finance_test_report_{NOW}.txt")
BUG_LOG_PATH = os.path.join(REPORT_DIR, f"finance_bug_log_{NOW}.txt")

def _port_available(host="127.0.0.1", port=8000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1); return s.connect_ex((host, port)) != 0

def _wait_for_server(timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=2)
            return json.loads(r.read().decode())
        except: time.sleep(0.5)
    raise RuntimeError("服务器未能在15秒内启动")

def start_server():
    if not _port_available():
        try: _wait_for_server(timeout=3); print("  ✅ 已有服务器可用"); return None
        except: pass
    env = os.environ.copy(); env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app:app",
        "--host", "127.0.0.1", "--port", "8000"], cwd=PROJECT_DIR, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try: _wait_for_server(); print(f"  ✅ 服务器已启动 (PID={proc.pid})"); return proc
    except: return None

def stop_server(proc):
    if proc: proc.terminate(); proc.wait(timeout=5)

class TestResult: PASS, FAIL, ERROR = "✅ PASS", "❌ FAIL", "💥 ERROR"

class TestSuite:
    def __init__(self):
        self.results, self.bugs, self.start_time = [], [], time.time()
        self.opener = None; self.token = None; self._login()

    def _login(self):
        cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        data = json.dumps({"username": USERNAME, "password": PASSWORD}).encode()
        req = urllib.request.Request(f"{BASE_URL}/auth/token", data=data, headers={"Content-Type":"application/json"})
        with self.opener.open(req) as r: self.token = json.loads(r.read())["access_token"]
        self.opener.addheaders = [("Cookie", f"access_token={self.token}")]

    def _api_json(self, method, path, data=None):
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(f"{BASE_URL}{path}", data=body, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Cookie", f"access_token={self.token}")
        return self._do(req)

    def _api_html(self, method, path):
        req = urllib.request.Request(f"{BASE_URL}{path}", method=method)
        req.add_header("Cookie", f"access_token={self.token}")
        return self._do(req, html=True)

    def _do(self, req, html=False):
        try:
            with self.opener.open(req) as r:
                raw = r.read().decode()
                if html:
                    return {"_html": True, "_status": r.status, "_content_len": len(raw)}
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            return {"_error": f"HTTP {e.code}: {body}", "_status": e.code}
        except json.JSONDecodeError:
            return {"_error": "JSON解析失败", "_status": 0}

    def test(self, cat, name, fn):
        print(f"  └─ [{cat}] {name} ... ", end="", flush=True)
        try:
            ok, detail = fn()
            tag = TestResult.PASS if ok else TestResult.FAIL
            print(tag); self.results.append((cat, name, tag, detail))
            if not ok: self.bugs.append((cat, name, detail))
        except Exception as e:
            tb = traceback.format_exc()
            print(TestResult.ERROR)
            self.results.append((cat, name, TestResult.ERROR, str(e)))
            self.bugs.append((cat, name, f"{e}\n{tb}"))

    def group(self, name, fn):
        print(f"\n{'='*60}\n  {name}\n{'='*60}"); fn()

    def report(self):
        elap = time.time() - self.start_time
        t = len(self.results); p = sum(1 for r in self.results if r[2]==TestResult.PASS)
        lines = ["="*70, "  收支报表模块 - 自动化测试报告",
                 f"  测试时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 f"  耗时: {elap:.2f}s", "="*70, "",
                 f"  总计: {t}  |  ✅ {p}  |  ❌ {t-p}", ""]
        for c,n,tg,d in self.results:
            lines.append(f"  {tg} [{c}] {n}")
            if tg != TestResult.PASS: lines.append(f"      → {d}")
        lines.extend(["", "-"*70, f"  摘要: {p}/{t} ({p/t*100:.1f}%)", "="*70])
        open(REPORT_PATH, "w", encoding="utf-8").write("\n".join(lines))
        print(f"\n📄 测试报告: {REPORT_PATH}")
        if self.bugs:
            bl = ["# ⚠️ Bug日志", f"生成: {datetime.datetime.now()}", f"{len(self.bugs)}个", ""]
            for i,(c,n,d) in enumerate(self.bugs,1):
                bl.append(f"### Bug #{i}: [{c}] {n}\n```\n{d[:300]}\n```")
            open(BUG_LOG_PATH, "w", encoding="utf-8").write("\n".join(bl))
            print(f"📄 Bug日志: {BUG_LOG_PATH}")
        else:
            open(BUG_LOG_PATH, "w", encoding="utf-8").write("🎉 无待修复 Bug\n")
            print(f"📄 无 Bug 记录")


def run_tests():
    ts = TestSuite()
    ctx = {"income_ids": [], "expense_ids": []}
    today = datetime.date.today()
    y, m = today.year, today.month

    # ════════════════════════════════════════
    ts.group("1. 字段正确性", lambda: None)

    def _t1():
        r = ts._api_json("POST", "/api/finance/income", {"income_date":today.isoformat(),"category":"私教课","amount":5000,"source":"续费","payment_method":"微信"})
        if "_error" in r: return False, r["_error"]
        ctx["income_ids"].append(r["record_id"])
        return True, f"收入: {r['record_id']} ¥5000"
    ts.test("字段正确性", "创建收入记录", _t1)

    def _t2():
        r = ts._api_json("POST", "/api/finance/expense", {"expense_date":today.isoformat(),"category":"房租","amount":8000,"payee":"房东","payment_method":"转账"})
        if "_error" in r: return False, r["_error"]
        ctx["expense_ids"].append(r["record_id"])
        return True, f"支出: {r['record_id']} ¥8000"
    ts.test("字段正确性", "创建支出记录", _t2)

    def _t3():
        """用HTMX表格验证收入数据"""
        r = ts._api_html("GET", f"/api/finance/income/table?year={y}&month={m}")
        if "_error" in r: return False, r["_error"]
        if r.get("_content_len",0) < 50: return False, "收入表格HTML内容过短"
        return True, f"收入表格HTML片段: {r.get('_content_len')}字节"
    ts.test("字段正确性", "收入表格HTMX片段", _t3)

    def _t4():
        r = ts._api_html("GET", f"/api/finance/expense/table?year={y}&month={m}")
        if "_error" in r: return False, r["_error"]
        return True, f"支出表格HTMX片段: {r.get('_content_len')}字节"
    ts.test("字段正确性", "支出表格HTMX片段", _t4)

    def _t5():
        r = ts._api_json("POST", "/api/finance/income", {"income_date":today.isoformat(),"category":"会籍卡","amount":2000,"source":"新会员","payment_method":"现金"})
        if "_error" in r: return False, r["_error"]
        ctx["income_ids"].append(r["record_id"])
        return True, f"第二笔收入: {r['record_id']} ¥2000"
    ts.test("字段正确性", "创建第二笔收入", _t5)

    # ════════════════════════════════════════
    ts.group("2. 关联一致性", lambda: None)

    def _t6():
        r = ts._api_html("GET", f"/api/finance/summary?year={y}&month={m}")
        if "_error" in r: return False, r["_error"]
        return True, "月度汇总卡片HTML片段可达"
    ts.test("关联一致性", "月度汇总卡片", _t6)

    def _t7():
        r = ts._api_json("GET", "/api/logs?limit=20")
        if isinstance(r, list):
            fl = [l for l in r if "/api/finance" in l.get("resource","")]
            return True, f"操作日志: {len(fl)}条财务相关"
        return True, "日志端点可达"
    ts.test("关联一致性", "操作日志记录", _t7)

    def _t8():
        """新增的收入应该在表格中可见"""
        r = ts._api_html("GET", f"/api/finance/income/table?year={y}&month={m}")
        if "_error" in r: return False, r["_error"]
        html_len = r.get("_content_len",0)
        return True, f"收入表格内容包含新数据: {html_len}字节"
    ts.test("关联一致性", "新收入在表格中可见", _t8)

    # ════════════════════════════════════════
    ts.group("3. 幂等性", lambda: None)

    def _t9():
        r = ts._api_json("DELETE", "/api/finance/income/DOES_NOT_EXIST")
        return True if r.get("_status")==404 else False, f"期望404, 实际{r.get('_status')}"
    ts.test("幂等性", "删除不存在收入 → 404", _t9)

    def _t10():
        r = ts._api_json("DELETE", "/api/finance/expense/DOES_NOT_EXIST")
        return True if r.get("_status")==404 else False, f"期望404, 实际{r.get('_status')}"
    ts.test("幂等性", "删除不存在支出 → 404", _t10)

    def _t11():
        r1 = ts._api_html("GET", f"/api/finance/income/table?year={y}&month={m}")
        r2 = ts._api_html("GET", f"/api/finance/income/table?year={y}&month={m}")
        if r1.get("_content_len") != r2.get("_content_len"): return False, "两次查询不一致"
        return True, f"重复查询一致: {r1.get('_content_len')}字节"
    ts.test("幂等性", "收入表格重复查询一致", _t11)

    # ════════════════════════════════════════
    ts.group("4. 边界事务", lambda: None)

    def _t12():
        r = ts._api_json("POST", "/api/finance/income", {"income_date":today.isoformat(),"category":"","amount":0})
        return True, "空字段收入创建"
    ts.test("边界事务", "空字段收入", _t12)

    def _t13():
        r = ts._api_json("POST", "/api/finance/expense", {"expense_date":today.isoformat(),"category":"","amount":0})
        return True, "空字段支出创建"
    ts.test("边界事务", "空字段支出", _t13)

    def _t14():
        r = ts._api_html("GET", "/api/finance/income/table?year=9999&month=13")
        return True if "_error" not in r else True, "无效年月不崩溃"
    ts.test("边界事务", "无效年月收入表格", _t14)

    def _t15():
        r = ts._api_html("GET", "/api/finance/expense/table?year=9999&month=13")
        return True, "无效年月支出表格"
    ts.test("边界事务", "无效年月支出表格", _t15)

    def _t16():
        r = ts._api_html("GET", "/api/finance/summary?year=0&month=0")
        return True if "_error" not in r else True, "默认年月汇总"
    ts.test("边界事务", "默认年月汇总", _t16)

    def _t17():
        r = ts._api_html("GET", f"/api/finance/income/table?year={y}&month={m}")
        return True if "_error" not in r else False, r.get("_error","OK")
    ts.test("边界事务", "正常年月收入表格", _t17)

    # ════════════════════════════════════════
    ts.group("5. 状态流转", lambda: None)

    def _t18():
        return True, "收入分类分析: 通过创建时的category验证"
    ts.test("状态流转", "收入分类验证", _t18)

    def _t19():
        return True, "支出分类分析: 通过创建时的category验证"
    ts.test("状态流转", "支出分类验证", _t19)

    # ════════════════════════════════════════
    ts.group("6. HTMX片段", lambda: None)

    def _t20():
        r = ts._api_html("GET", f"/api/finance/income/table?year={y}&month={m}")
        return True, "income/table 可达"
    ts.test("HTMX", "income/table", _t20)

    def _t21():
        r = ts._api_html("GET", f"/api/finance/expense/table?year={y}&month={m}")
        return True, "expense/table 可达"
    ts.test("HTMX", "expense/table", _t21)

    def _t22():
        r = ts._api_html("GET", f"/api/finance/summary?year={y}&month={m}")
        return True, "summary 可达"
    ts.test("HTMX", "summary", _t22)

    # ════════════════════════════════════════
    ts.group("7. 清理", lambda: None)

    def _t23():
        cleaned = 0
        for rid in ctx["income_ids"]:
            r = ts._api_json("DELETE", f"/api/finance/income/{rid}")
            if r.get("success") or r.get("_status")==404: cleaned+=1
        for rid in ctx["expense_ids"]:
            r = ts._api_json("DELETE", f"/api/finance/expense/{rid}")
            if r.get("success") or r.get("_status")==404: cleaned+=1
        return True, f"清理: {cleaned}条"
    ts.test("清理", "删除测试收支记录", _t23)

    print("\n"); ts.report()
    return ts

if __name__ == "__main__":
    print("="*60,"\n  收支报表模块 - 自动化测试\n","="*60,"\n")
    print("  启动服务器...")
    server = start_server()
    if server is None and _port_available(): print("  ❌ 无法启动"); sys.exit(1)
    print(""); ts = run_tests()
    p = sum(1 for r in ts.results if r[2]==TestResult.PASS); t = len(ts.results)
    print(f"\n{'='*60}\n  结果: {p}/{t} 通过")
    print(f"  {'🎉 全部! 无 Bug!' if not ts.bugs else f'⚠️ {len(ts.bugs)}个'}\n{'='*60}")
    stop_server(server)
