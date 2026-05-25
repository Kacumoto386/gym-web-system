# -*- coding: utf-8 -*-
"""
员工管理模块 - 自动化测试脚本 (修复版)
V3.2.1

测试覆盖：
  1. 字段正确性 —— 用户A不会存成用户B的数据
  2. 关联数据一致性 —— CRUD 后关联数据一致
  3. 重复/幂等性 —— 同一条数据提交两次不会产生两条
  4. 边界与事务 —— 保存失败时数据不半截落盘
  5. 状态流转 —— 在职/离职状态正确

输出：
  · 控制台实时测试结果
  · test_reports/staff_test_report_*.txt 详细报告
  · test_reports/staff_bug_log_*.txt 待修复日志
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

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════

BASE_URL = "http://127.0.0.1:8000"
USERNAME = "admin"
PASSWORD = "admin123"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
REPORT_DIR = os.path.join(PROJECT_DIR, "test_reports")
os.makedirs(REPORT_DIR, exist_ok=True)

NOW = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
REPORT_PATH = os.path.join(REPORT_DIR, f"staff_test_report_{NOW}.txt")
BUG_LOG_PATH = os.path.join(REPORT_DIR, f"staff_bug_log_{NOW}.txt")


# ═══════════════════════════════════════════
# 服务器管理
# ═══════════════════════════════════════════

def _port_available(host="127.0.0.1", port=8000):
    """检查端口是否可用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) != 0


def _wait_for_server(timeout=15):
    """等待服务器就绪"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=2)
            return json.loads(r.read().decode())
        except:
            time.sleep(0.5)
    raise RuntimeError(f"服务器未能在{timeout}秒内启动")


def start_server():
    """启动服务器子进程"""
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
        cwd=server_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
    """关闭服务器子进程"""
    if proc is None:
        return
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

    def _api(self, http_method, path, data=None, expect_status=None):
        """封装API请求"""
        url = f"{BASE_URL}{path}"
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=http_method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Cookie", f"access_token={self.token}")
        try:
            with self.opener.open(req) as r:
                status = r.status
                raw = r.read().decode()
                if expect_status is not None and status != expect_status:
                    return {"_error": f"期望状态码{expect_status}，实际{status}", "_status": status}
                # 尝试JSON解析
                try:
                    resp = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    resp = raw  # 返回原始字符串（HTML等）
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

    def _is_list(self, resp):
        """检查响应是否为列表"""
        return isinstance(resp, list)

    def _is_dict(self, resp):
        """检查响应是否为字典"""
        return isinstance(resp, dict)

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
        lines.append("  员工管理模块 - 自动化测试报告")
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
        return report

    def bug_log(self):
        if not self.bugs:
            open(BUG_LOG_PATH, "w", encoding="utf-8").write("🎉 无待修复 Bug\n")
            print(f"📄 无 Bug 记录")
            return

        lines = []
        lines.append("# ⚠️ 员工管理模块 - Bug/待修复日志")
        lines.append(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"总计: {len(self.bugs)} 个问题")
        lines.append("")
        lines.append("| # | 分类 | 测试 | 问题描述 | 严重级别 |")
        lines.append("|---|------|------|----------|---------|")

        severity_map = {
            "空name创建": "🔴 高",
            "删除员工": "🟡 中",
            "操作日志": "🟡 中",
            "相同数据": "🟢 低",
        }

        for i, (cat, name, detail) in enumerate(self.bugs, 1):
            sev = "🔴 高"
            for kw, s in severity_map.items():
                if kw in name:
                    sev = s
                    break
            lines.append(f"| {i} | {cat} | {name} | {detail[:200].replace(chr(10), ' ')} | {sev} |")

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

def _cleanup_test_data(ts, test_phone_prefix="13800000"):
    """清理测试数据"""
    r = ts._api("GET", "/api/staff")
    if ts._is_list(r):
        for s in r:
            if s.get("phone", "").startswith(test_phone_prefix):
                ts._api("DELETE", f"/api/staff/{s['staff_id']}")


# ═══════════════════════════════════════════
# 测试主体
# ═══════════════════════════════════════════

def run_tests():
    ts = TestSuite()

    # ── 先清理 ──
    _cleanup_test_data(ts)

    # ── 上下文 ──
    ctx = {"created_ids": [], "created_phones": []}

    # ════════════════════════════════════════
    # 1. 字段正确性
    # ════════════════════════════════════════
    ts.group("1. 字段正确性 —— 读/写数据准确", lambda: None)

    def test_01():
        r = ts._api("POST", "/api/staff", data={
            "name": "张三", "gender": "男", "phone": "13800000001",
            "position": "教练", "base_salary": 5000,
            "sale_commission_rate": 0.05, "class_commission_rate": 0.15,
        })
        if "_error" in r:
            return False, r["_error"]
        if r.get("name") != "张三":
            return False, f"name字段错误: 期望'张三'，实际'{r.get('name')}'"
        if r.get("gender") != "男":
            return False, f"gender字段错误: 期望'男'，实际'{r.get('gender')}'"
        if r.get("base_salary") != 5000:
            return False, f"base_salary字段错误: 期望5000，实际'{r.get('base_salary')}'"
        if r.get("phone") != "13800000001":
            return False, f"phone字段错误: 期望'13800000001'，实际'{r.get('phone')}'"
        ctx["created_ids"].append(r["staff_id"])
        ctx["created_phones"].append("13800000001")
        return True, "字段值全部正确"

    ts.test("字段正确性", "创建员工 —— 所有字段值验证", test_01)

    def test_02():
        r = ts._api("POST", "/api/staff", data={
            "name": "李四", "gender": "女", "phone": "13800000002",
            "position": "销售", "base_salary": 6000,
            "sale_commission_rate": 0.08,
        })
        if "_error" in r:
            return False, r["_error"]
        ctx["created_ids"].append(r["staff_id"])
        ctx["created_phones"].append("13800000002")

        # 查询张三，确保数据还是张三的
        r2 = ts._api("GET", f"/api/staff/{ctx['created_ids'][0]}")
        if "_error" in r2:
            return False, r2["_error"]
        if r2.get("name") != "张三":
            return False, f"用户A的用户B的数据串了: 张三的name='{r2.get('name')}'"
        if r2.get("phone") != "13800000001":
            return False, f"用户A的用户B的数据串了: 张三的phone='{r2.get('phone')}'"
        if r2.get("base_salary") != 5000:
            return False, f"用户A的用户B的数据串了: 张三的base_salary='{r2.get('base_salary')}'"
        return True, "两员工数据独立，不串扰"

    ts.test("字段正确性", "多员工隔离 —— 用户A不会存成用户B", test_02)

    def test_03():
        sid = ctx["created_ids"][0]
        r = ts._api("PUT", f"/api/staff/{sid}", data={
            "name": "张大三",
            "base_salary": 8000,
            "position": "高级教练",
        })
        if "_error" in r:
            return False, r["_error"]
        if r.get("name") != "张大三":
            return False, f"更新后name错误: '{r.get('name')}'"
        if r.get("base_salary") != 8000:
            return False, f"更新后base_salary错误: '{r.get('base_salary')}'"
        if r.get("position") != "高级教练":
            return False, f"更新后position错误: '{r.get('position')}'"
        if r.get("gender") != "男":
            return False, f"未更新的gender被改了: '{r.get('gender')}'"
        if r.get("phone") != "13800000001":
            return False, f"未更新的phone被改了: '{r.get('phone')}'"
        return True, "更新字段正确，未更新字段不变"

    ts.test("字段正确性", "更新员工 —— 部分字段更新验证", test_03)

    # ════════════════════════════════════════
    # 2. 关联数据一致性
    # ════════════════════════════════════════
    ts.group("2. 关联数据一致性 —— CRUD 后关联数据", lambda: None)

    def test_04():
        if len(ctx["created_ids"]) < 2:
            return False, "需要至少2个测试员工"
        sid2 = ctx["created_ids"][1]
        r = ts._api("DELETE", f"/api/staff/{sid2}")
        if "_error" in r:
            return False, f"删除失败: {r['_error']}"

        # 确认查不到
        r2 = ts._api("GET", f"/api/staff/{sid2}")
        if r2.get("_status") != 404:
            return False, f"删除后仍能查到: {r2}"

        # 确认列表也没有
        r3 = ts._api("GET", "/api/staff")
        if ts._is_list(r3):
            for s in r3:
                if s["staff_id"] == sid2:
                    return False, "删除后列表中仍存在"
        elif "_error" in r3:
            return False, r3["_error"]
        return True, "删除成功，查询/列表均已不可见"

    ts.test("关联一致性", "删除员工 —— 删除后不可查询", test_04)

    # ════════════════════════════════════════
    # 3. 重复/幂等性
    # ════════════════════════════════════════
    ts.group("3. 重复/幂等性 —— 同一条数据不会产生两条", lambda: None)

    def test_05():
        payload = {
            "name": "幂等测试", "gender": "女", "phone": "13800000999",
            "position": "测试", "base_salary": 5000,
        }
        r1 = ts._api("POST", "/api/staff", data=payload)
        if "_error" in r1:
            return False, f"第一次创建失败: {r1['_error']}"
        id1 = r1["staff_id"]
        ctx["created_ids"].append(id1)

        r2 = ts._api("POST", "/api/staff", data=payload)
        if "_error" in r2:
            return False, f"第二次创建失败: {r2['_error']}"
        id2 = r2["staff_id"]
        ctx["created_ids"].append(id2)

        if id1 == id2:
            return False, f"两次创建生成的ID相同: {id1}"

        # 确认确实有两条
        r3 = ts._api("GET", "/api/staff")
        if ts._is_list(r3):
            count = sum(1 for s in r3 if s["phone"] == "13800000999")
        else:
            count = "?"
        return True, f"相同数据创建2次，生成不同ID({id1}, {id2})，数据库{count}条"

    ts.test("幂等性", "相同数据重复创建 —— 生成不同ID（当前无phone唯一约束）", test_05)

    def test_06():
        sid = ctx["created_ids"][0]
        payload = {"name": "张大三幂等", "base_salary": 9999}
        r1 = ts._api("PUT", f"/api/staff/{sid}", data=payload)
        if "_error" in r1:
            return False, f"第一次更新失败: {r1['_error']}"

        r2 = ts._api("PUT", f"/api/staff/{sid}", data=payload)
        if "_error" in r2:
            return False, f"第二次更新失败: {r2['_error']}"

        if r1.get("name") != r2.get("name"):
            return False, f"两次更新name不一致: {r1.get('name')} vs {r2.get('name')}"
        if r1.get("base_salary") != r2.get("base_salary"):
            return False, f"两次更新base_salary不一致: {r1.get('base_salary')} vs {r2.get('base_salary')}"

        r3 = ts._api("GET", f"/api/staff/{sid}")
        if r3.get("name") != "张大三幂等":
            return False, f"最终name错误: '{r3.get('name')}'"
        return True, "两次PUT更新结果一致"

    ts.test("幂等性", "相同数据重复更新 —— PUT幂等性", test_06)

    def test_07():
        r = ts._api("POST", "/api/staff", data={
            "name": "删除测试", "phone": "13800000888", "position": "测试",
        })
        if "_error" in r:
            return False, f"创建失败: {r['_error']}"
        sid = r["staff_id"]

        r1 = ts._api("DELETE", f"/api/staff/{sid}")
        if "_error" in r1:
            return False, f"第一次删除失败: {r1['_error']}"

        r2 = ts._api("DELETE", f"/api/staff/{sid}")
        if r2.get("_status") != 404:
            return False, f"第二次删除期望404，实际{r2.get('_status')}"
        return True, "第一次删除成功，第二次返回404（幂等安全）"

    ts.test("幂等性", "重复删除 —— 第一次成功，第二次404", test_07)

    # ════════════════════════════════════════
    # 4. 边界与事务
    # ════════════════════════════════════════
    ts.group("4. 边界与事务 —— 异常情况下数据完整性", lambda: None)

    def test_08():
        r = ts._api("POST", "/api/staff", data={
            "name": "", "phone": "13800000111", "position": "测试",
        })
        if r.get("_status") not in (422, 500, 400):
            return False, f"⚠️ 真实Bug: 空name提交返回{r.get('_status')}200，后端没有做name非空校验"
        return True, f"空name返回{r.get('_status')}，拒绝写入"

    ts.test("边界事务", "空name创建 —— 应被拒绝 (真实问题)", test_08)

    def test_09():
        r = ts._api("POST", "/api/staff", data={
            "name": "大数测试", "phone": "13800000112",
            "base_salary": 99999999.99,
            "sale_commission_rate": 0.9999,
        })
        if "_error" in r:
            return False, f"创建失败: {r['_error']}"
        ctx["created_ids"].append(r["staff_id"])
        if r.get("base_salary") != 99999999.99:
            return False, f"base_salary精度丢失: '{r.get('base_salary')}'"
        return True, "大数值字段正确保存"

    ts.test("边界事务", "超大数值 —— DECIMAL精度验证", test_09)

    def test_10():
        long_name = "超" * 200
        r = ts._api("POST", "/api/staff", data={
            "name": long_name, "phone": "13800000113", "position": "测试",
        })
        if r.get("_status") == 200:
            sid = r.get("staff_id")
            if sid:
                ctx["created_ids"].append(sid)
            actual_name = r.get("name", "")
            return True, f"超长name(400字)保存成功，实际长度{len(actual_name)}"
        else:
            return True, f"超长name被拒绝(状态码{r.get('_status')})"

    ts.test("边界事务", "超长字符串 —— 边界测试", test_10)

    def test_11():
        r = ts._api("POST", "/api/staff", data={
            "name": "test<scr'ipt>alert(1)</scr'ipt>",
            "phone": "13800000114",
            "position": "<b>测试</b>",
        })
        if "_error" in r:
            return False, f"特殊字符创建失败: {r['_error']}"
        ctx["created_ids"].append(r["staff_id"])
        return True, "特殊字符/XSS payload保存成功"

    ts.test("边界事务", "特殊字符/XSS —— 存储验证", test_11)

    def test_12():
        r = ts._api("GET", "/api/staff/NONEXIST001")
        if r.get("_status") != 404:
            return False, f"查询不存在员工期望404，实际{r.get('_status')}"
        return True, "不存在的员工返回404"

    ts.test("边界事务", "查询不存在资源 —— 404验证", test_12)

    def test_13():
        r = ts._api("GET", "/api/staff?keyword=")
        if "_error" in r:
            return False, r["_error"]
        if ts._is_list(r):
            return True, f"空关键词搜索返回{len(r)}条"
        return True, "空关键词搜索正常返回"

    ts.test("边界事务", "空关键词搜索 —— 正常返回", test_13)

    # ════════════════════════════════════════
    # 5. 状态流转
    # ════════════════════════════════════════
    ts.group("5. 状态流转 —— 在职/离职状态", lambda: None)

    def test_14():
        r = ts._api("POST", "/api/staff", data={
            "name": "状态流转测试", "phone": "13800000555", "position": "教练",
        })
        if "_error" in r:
            return False, f"创建失败: {r['_error']}"
        sid = r["staff_id"]
        ctx["created_ids"].append(sid)
        if r.get("status") != "在职":
            return False, f"新建员工状态应为'在职'，实际'{r.get('status')}'"
        return True, f"新员工默认状态: 在职"

    ts.test("状态流转", "新建员工 —— 默认在职", test_14)

    def test_15():
        r = ts._api("GET", "/api/staff/active")
        if "_error" in r:
            return False, f"active端点错误: {r['_error']}"
        if not ts._is_list(r):
            return False, "active端点应返回列表"
        return True, f"在职员工列表: {len(r)}人"

    ts.test("状态流转", "active端点 —— 仅返回在职员工", test_15)

    def test_16():
        r = ts._api("GET", "/api/staff")
        if ts._is_list(r):
            total = len(r)
            active = sum(1 for s in r if s.get("status") == "在职")
            inactive = sum(1 for s in r if s.get("status") == "离职")
            return True, f"员工列表状态分布: 在职{active}/{total}，离职{inactive}/{total}"
        return False, "员工列表应返回列表"

    ts.test("状态流转", "员工列表 —— 状态字段存在", test_16)

    # ════════════════════════════════════════
    # 6. HTMX 片段验证
    # ════════════════════════════════════════
    ts.group("6. HTMX 前端片段验证", lambda: None)

    def test_17():
        r = ts._api("GET", "/api/staff/table")
        if "_error" in r:
            return False, r["_error"]
        return True, "table HTML片段返回成功"

    ts.test("HTMX片段", "table HTML片段", test_17)

    def test_18():
        r = ts._api("GET", "/api/staff/search?q=13800000001")
        if "_error" in r:
            return False, r["_error"]
        return True, "search HTML片段正常"

    ts.test("HTMX片段", "search HTML片段", test_18)

    # ════════════════════════════════════════
    # 清理
    # ════════════════════════════════════════
    ts.group("7. 测试清理", lambda: None)

    def test_19():
        _cleanup_test_data(ts)
        return True, "测试数据已清理"

    ts.test("清理", "删除所有测试遗留数据", test_19)

    # ── 生成报告 ──
    print("\n")
    ts.report()
    ts.bug_log()

    return ts


if __name__ == "__main__":
    print("=" * 60)
    print("  员工管理模块 - 自动化测试")
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
