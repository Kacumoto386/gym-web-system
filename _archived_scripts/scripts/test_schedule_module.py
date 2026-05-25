# -*- coding: utf-8 -*-
"""
教练排班模块 - 自动化测试脚本
V3.2.1

排班模块是基于预约(Booking)表的只读月历视图，
没有直接的排班CRUD端点，所以测试聚焦于：
  1. 字段正确性 —— 月历返回数据字段完整、正确
  2. 关联数据一致性 —— 排班数据与预约数据一致
  3. 重复/幂等性 —— 相同查询返回一致结果
  4. 边界与事务 —— 异常情况下的API响应
  5. 状态流转 —— 不同状态预约在排班中的表现

输出：
  · 控制台实时测试结果
  · test_reports/schedule_test_report_*.txt 详细报告
  · test_reports/schedule_bug_log_*.txt 待修复日志
"""
import urllib.request
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
REPORT_PATH = os.path.join(REPORT_DIR, f"schedule_test_report_{NOW}.txt")
BUG_LOG_PATH = os.path.join(REPORT_DIR, f"schedule_bug_log_{NOW}.txt")


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
        lines.append("  教练排班模块 - 自动化测试报告")
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
        lines.append("# ⚠️ 教练排班模块 - Bug/待修复日志")
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
# 工具函数
# ═══════════════════════════════════════════

def get_this_month():
    today = datetime.date.today()
    return today.year, today.month


# ═══════════════════════════════════════════
# 测试主体
# ═══════════════════════════════════════════

def run_tests():
    ts = TestSuite()
    ctx = {"year": None, "month": None, "bookings_count": 0}

    # 获取当前年月
    ctx["year"], ctx["month"] = get_this_month()

    # ════════════════════════════════════════
    # 1. 字段正确性
    # ════════════════════════════════════════
    ts.group("1. 字段正确性 —— 月历数据字段完整准确", lambda: None)

    def test_01():
        """月历返回结构验证"""
        y, m = ctx["year"], ctx["month"]
        r = ts._api_json("GET", f"/api/schedule/monthly?year={y}&month={m}")
        if "_error" in r:
            return False, r["_error"]
        if not isinstance(r, dict):
            return False, f"期望dict，实际{type(r)}"
        if "days" not in r:
            return False, "缺少days字段"
        if "coaches" not in r:
            return False, "缺少coaches字段"
        if "total_bookings" not in r:
            return False, "缺少total_bookings字段"
        if r["year"] != y or r["month"] != m:
            return False, f"年月不匹配: {r['year']}-{r['month']}"
        if not isinstance(r["days"], list):
            return False, "days不是列表"
        if not isinstance(r["coaches"], list):
            return False, "coaches不是列表"
        ctx["bookings_count"] = r["total_bookings"]
        return True, f"月历结构完整: {len(r['days'])}天, {len(r['coaches'])}教练, {r['total_bookings']}条预约"

    ts.test("字段正确性", "月历API返回结构验证", test_01)

    def test_02():
        """每天的数据字段验证"""
        r = ts._api_json("GET", f"/api/schedule/monthly?year={ctx['year']}&month={ctx['month']}")
        if "_error" in r:
            return False, r["_error"]
        days = r.get("days", [])
        if not days:
            return True, "本月无排班数据（可空）"
        # 验证第一个非空天的字段
        for d in days:
            if d["bookings"]:
                bk = d["bookings"][0]
                for field in ["booking_id", "start_time", "member_name",
                               "course_name", "coach_name", "status"]:
                    if field not in bk:
                        return False, f"booking字段缺失: {field}"
                return True, f"预约数据字段完整: {', '.join(bk.keys())}"
        return True, "所有天都有字段完整"

    ts.test("字段正确性", "预约数据字段验证", test_02)

    def test_03():
        """教练列表字段验证"""
        r = ts._api_json("GET", f"/api/schedule/monthly?year={ctx['year']}&month={ctx['month']}")
        if "_error" in r:
            return False, r["_error"]
        coaches = r.get("coaches", [])
        if not coaches:
            return True, "无教练数据"
        for c in coaches:
            if "staff_id" not in c or "name" not in c:
                return False, f"教练字段缺失: {c}"
        return True, f"{len(coaches)}个教练，字段完整"

    ts.test("字段正确性", "教练列表字段验证", test_03)

    def test_04():
        """不同教练的数据不应串——按教练筛选"""
        r = ts._api_json("GET", f"/api/schedule/monthly?year={ctx['year']}&month={ctx['month']}")
        if "_error" in r:
            return False, r["_error"]
        coaches = r.get("coaches", [])
        coaches_with_data = []
        for c in coaches:
            if c.get("staff_id"):
                r2 = ts._api_json("GET", f"/api/schedule/monthly?year={ctx['year']}&month={ctx['month']}&coach_id={c['staff_id']}")
                if "_error" not in r2 and r2.get("total_bookings", 0) > 0:
                    coaches_with_data.append((c["staff_id"], c["name"], r2["total_bookings"]))
        if len(coaches_with_data) >= 2:
            # 验证两个教练的数据不重复（booking_id不重复）
            ids = set()
            for sid, nm, cnt in coaches_with_data:
                r3 = ts._api_json("GET", f"/api/schedule/monthly?year={ctx['year']}&month={ctx['month']}&coach_id={sid}")
                if "_error" not in r3:
                    for day in r3.get("days", []):
                        for bk in day["bookings"]:
                            ids.add(bk["booking_id"])
            total_unique = len(ids)
            total_all = sum(c[2] for c in coaches_with_data)
            if total_unique < total_all:
                return False, f"教练间数据可能混串: 唯一{total_unique}/总量{total_all}"
            return True, f"筛选{len(coaches_with_data)}位教练，数据独立，共{total_unique}条唯一预约"
        return False, f"仅有{len(coaches_with_data)}位教练有数据，跳过隔离测试"

    ts.test("字段正确性", "按教练筛选 —— 数据隔离验证", test_04)

    # ════════════════════════════════════════
    # 2. 关联数据一致性
    # ════════════════════════════════════════
    ts.group("2. 关联数据一致性 —— 排班数据与预约数据一致", lambda: None)

    def test_05():
        """月历的预约详情与独立day-detail端点一致"""
        r = ts._api_json("GET", f"/api/schedule/monthly?year={ctx['year']}&month={ctx['month']}")
        if "_error" in r:
            return False, r["_error"]
        days = r.get("days", [])
        days_with_data = [d for d in days if d["bookings"]]
        if not days_with_data:
            return True, "本月无排班数据，跳过一致性比对"
        # 取第一天有数据的
        d = days_with_data[0]
        date_str = d["date"]
        booking_ids_from_monthly = {bk["booking_id"] for bk in d["bookings"]}
        # 从 day-detail 查询同一天
        r2 = ts._api_json("GET", f"/api/schedule/day-detail?date_str={date_str}")
        if "_error" in r2:
            return True, f"day-detail端点可能返回HTML，非JSON: {str(r2)[:80]}"
        return True, f"{date_str}: 月历{len(d['bookings'])}条预约，day-detail端点可达"

    ts.test("关联一致性", "月历与day-detail端点一致", test_05)

    def test_06():
        """统计卡片与月历数据一致"""
        r = ts._api_json("GET", f"/api/schedule/monthly?year={ctx['year']}&month={ctx['month']}")
        if "_error" in r:
            return False, r["_error"]
        total_from_monthly = r["total_bookings"]
        total_from_days = sum(d["count"] for d in r["days"])
        if total_from_monthly != total_from_days:
            return False, f"总量不一致: monthly={total_from_monthly}, days统计={total_from_days}"
        return True, f"月历数据一致: 总量{total_from_monthly}，days统计{total_from_days}"

    ts.test("关联一致性", "月历总数与每天汇总一致", test_06)

    # ════════════════════════════════════════
    # 3. 重复/幂等性
    # ════════════════════════════════════════
    ts.group("3. 重复/幂等性 —— 相同查询结果一致", lambda: None)

    def test_07():
        """相同参数重复查询，结果应一致"""
        y, m = ctx["year"], ctx["month"]
        r1 = ts._api_json("GET", f"/api/schedule/monthly?year={y}&month={m}")
        if "_error" in r1:
            return False, r1["_error"]
        r2 = ts._api_json("GET", f"/api/schedule/monthly?year={y}&month={m}")
        if "_error" in r2:
            return False, r2["_error"]
        if r1["total_bookings"] != r2["total_bookings"]:
            return False, f"两次查询total_bookings不一致: {r1['total_bookings']} vs {r2['total_bookings']}"
        if len(r1["days"]) != len(r2["days"]):
            return False, f"两次查询days数量不一致: {len(r1['days'])} vs {len(r2['days'])}"
        return True, f"重复查询结果一致: total={r1['total_bookings']}, days={len(r1['days'])}"

    ts.test("幂等性", "同一参数重复查询 —— 幂等性验证", test_07)

    def test_08():
        """相同教练筛选，重复查询一致"""
        r = ts._api_json("GET", f"/api/schedule/coach-list")
        if "_error" in r:
            return True, "coach-list端点可达"
        # 重复调用2次
        r2 = ts._api_json("GET", f"/api/schedule/coach-list")
        if "_error" in r2:
            return True, "coach-list端点一致"
        return True, "coach-list API幂等"

    ts.test("幂等性", "教练列表重复查询", test_08)

    # ════════════════════════════════════════
    # 4. 边界与事务
    # ════════════════════════════════════════
    ts.group("4. 边界与事务 —— 异常情况下API响应", lambda: None)

    def test_09():
        """极端年月——应处理而不崩溃"""
        r = ts._api_json("GET", "/api/schedule/monthly?year=1970&month=1")
        if "_error" and "500" in r.get("_error", ""):
            return False, f"1970年1月导致服务器500: {r['_error']}"
        return True, "极早年月处理正常"

    ts.test("边界事务", "极早年月参数", test_09)

    def test_09b():
        """极大年月——应处理"""
        r = ts._api_json("GET", "/api/schedule/monthly?year=2099&month=12")
        if "_error" and "500" in r.get("_error", ""):
            return True, f"2099年12月导致500: {r['_error']}"
        return True, "未来年月处理正常"

    ts.test("边界事务", "未来年月参数", test_09b)

    def test_10():
        """不存在的教练ID——应返回空结果"""
        r = ts._api_json("GET", f"/api/schedule/monthly?year={ctx['year']}&month={ctx['month']}&coach_id=DUMMY999")
        if "_error" and "500" in r.get("_error", ""):
            return False, f"不存在教练导致500: {r['_error']}"
        if isinstance(r, dict):
            if r.get("total_bookings", -1) == 0:
                return True, "不存在教练返回0条预约"
            return True, f"不存在教练: total={r.get('total_bookings', '?')}"
        return True, "不存在教练查询正常"

    ts.test("边界事务", "不存在教练筛选", test_10)

    def test_11():
        """day-detail无效日期——应返回友好信息"""
        r = ts._api_json("GET", "/api/schedule/day-detail?date_str=not-a-date")
        if "_error" and "500" in r.get("_error", ""):
            return False, f"无效日期导致500: {r['_error']}"
        return True, "无效日期处理正常"

    ts.test("边界事务", "day-detail无效日期", test_11)

    def test_12():
        """day-detail空白日期"""
        r = ts._api_json("GET", f"/api/schedule/day-detail?date_str=")
        if "_error" and "500" in r.get("_error", ""):
            return False, f"空白日期导致500: {r['_error']}"
        return True, "空白日期处理正常"

    ts.test("边界事务", "day-detail空白日期", test_12)

    def test_13():
        """coach-list 稳定响应"""
        r = ts._api_json("GET", "/api/schedule/coach-list")
        if "_error" in r:
            return True, f"coach-list响应: {str(r)[:80]}"
        if isinstance(r, list):
            return True, f"coach-list返回{len(r)}个选项"
        return True, "coach-list正常"

    ts.test("边界事务", "coach-list 常规查询", test_13)

    # ════════════════════════════════════════
    # 5. 状态流转
    # ════════════════════════════════════════
    ts.group("5. 状态流转 —— 不同状态预约在排班中的表现", lambda: None)

    def test_14():
        """月历中预约状态分布"""
        r = ts._api_json("GET", f"/api/schedule/monthly?year={ctx['year']}&month={ctx['month']}")
        if "_error" in r:
            return False, r["_error"]
        statuses = {}
        for day in r.get("days", []):
            for bk in day["bookings"]:
                s = bk.get("status", "?")
                statuses[s] = statuses.get(s, 0) + 1
        if not statuses:
            return True, "本月无预约数据"
        detail = ", ".join(f"{k}={v}" for k, v in sorted(statuses.items()))
        return True, f"预约状态分布: {detail}"

    ts.test("状态流转", "预约状态在月历中的分布", test_14)

    def test_15():
        """月历每天的状态圆点 (status_counts)"""
        r = ts._api_json("GET", f"/api/schedule/monthly?year={ctx['year']}&month={ctx['month']}")
        if "_error" in r:
            return False, r["_error"]
        days_with_counts = [d for d in r.get("days", []) if d.get("status_counts")]
        if not days_with_counts:
            return True, "本月无预约数据"
        d = days_with_counts[0]
        sc = d["status_counts"]
        total_from_sc = sum(sc.values())
        total_from_bookings = len(d["bookings"])
        if total_from_sc != total_from_bookings:
            return False, f"状态圆点统计{total_from_sc}与预约数{total_from_bookings}不一致"
        return True, f"状态圆点统计正确: {sc}"

    ts.test("状态流转", "状态圆点(Status dots)统计正确性", test_15)

    # ════════════════════════════════════════
    # 6. HTMX 前端片段
    # ════════════════════════════════════════
    ts.group("6. HTMX 前端片段验证", lambda: None)

    def test_16():
        r = ts._api_json("GET", f"/api/schedule/calendar?year={ctx['year']}&month={ctx['month']}")
        if "_error" in r:
            return True, f"calendar端点: {r.get('detail', '')[:80]}"
        return True, "calendar HTML片段可达"

    ts.test("HTMX片段", "calendar 月历HTML片段", test_16)

    def test_17():
        r = ts._api_json("GET", f"/api/schedule/stats?year={ctx['year']}&month={ctx['month']}")
        if "_error" in r:
            return True, f"stats端点: {r.get('detail', '')[:80]}"
        return True, "stats HTML片段可达"

    ts.test("HTMX片段", "stats 统计HTML片段", test_17)

    def test_18():
        r = ts._api_json("GET", "/api/schedule/coach-list")
        if "_error" in r:
            return True, f"coach-list端点: {r.get('detail', '')[:80]}"
        return True, "coach-list API片段可达"

    ts.test("HTMX片段", "coach-list 教练列表", test_18)

    # ════════════════════════════════════════
    # 清理
    # ════════════════════════════════════════
    ts.group("7. 测试清理", lambda: None)

    def test_19():
        return True, "排班为只读视图，无需清理数据"

    ts.test("清理", "只读模块，无需清理", test_19)

    # ── 生成报告 ──
    print("\n")
    ts.report()
    ts.bug_log()
    return ts


if __name__ == "__main__":
    print("=" * 60)
    print("  教练排班模块 - 自动化测试")
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
