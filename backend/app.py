"""
FastAPI 应用入口
V3.8.2 — 数据导入模块（模板下载 / Excel 上传 / 进度跟踪 / 历史记录）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from backend.database import init_db, get_db
from backend.models.models import Member, Checkin, ClassRecord
from backend.routers.auth import get_current_user, User
from backend.routers.operation_log import record_log
from backend.routers.mcp_router import router as mcp_router
from backend.routers.chat_router import router as chat_router
from backend.feature_registry import registry

app = FastAPI(
    title="鼠小弟健身管理系统",
    description="Web 版健身管理系统 V3.8.8 — 功能配置清单 + Bug 修复",
    version="3.8.8",
)

# 模板
templates_dir = Path(__file__).parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))


# 模板全局上下文：系统名称（每次渲染时动态读取）
def _get_system_name():
    """读取系统名称，供模板全局使用"""
    try:
        db = next(get_db())
        from backend.routers.operation_log import get_system_name
        name = get_system_name(db)
        db.close()
        return name
    except Exception:
        return "健身房管理系统"


templates.env.globals["_get_system_name"] = _get_system_name
templates.env.globals["_nav_tree"] = registry.get_nav_tree
templates.env.globals["_group_names"] = registry.get_group_names

# 静态文件
from fastapi.staticfiles import StaticFiles
static_dir = Path(__file__).parent.parent / "frontend" / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
@app.on_event("startup")
def on_startup():
    init_db()


# ── 认证中间件 ──

# 不需要登录的路径
PUBLIC_PATHS = {
    "/auth/login", "/auth/token", "/auth/setup", "/api/health",
    "/favicon.ico",
}

# 公开 API 前缀（不需要登录）
PUBLIC_API_PREFIXES = {"/api/dashboard/", "/api/members/search-json", "/api/mcp/", "/api/chat/"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # 公共路径跳过
    if path in PUBLIC_PATHS:
        return await call_next(request)

    # 公开 API 前缀跳过
    for prefix in PUBLIC_API_PREFIXES:
        if path.startswith(prefix):
            return await call_next(request)

    # API 路径也需要验证 cookie（JSON API 请求）
    if path.startswith("/api/") and path != "/api/health":
        # 从 cookie 拿 token
        token = request.cookies.get("access_token")
        if not token:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=401, content={"detail": "未登录"})

    # 页面路由验证登录
    if not path.startswith("/auth/") and not path.startswith("/api/health"):
        token = request.cookies.get("access_token")
        if not token:
            return RedirectResponse(url="/auth/login", status_code=302)
        # 验证 token 是否有效
        db = next(get_db())
        user = get_current_user(request, db)
        db.close()
        if not user:
            return RedirectResponse(url="/auth/login", status_code=302)

    return await call_next(request)


# ── 全局 no-cache 中间件 ──
@app.middleware("http")
async def no_cache_middleware(request: Request, call_next):
    response = await call_next(request)
    # 给所有 HTML 页面加上 Cache-Control: no-cache
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ── 操作日志中间件 ──

# 已知的非 ID 路径段（子资源/动作名，不应作为 resource_id）
_KNOWN_ACTION_SEGMENTS = frozenset({
    # product
    "inbounds", "form-options", "low-stock", "profit-summary",
    "adjust-stock", "sales", "batch",
    # package
    "products", "monthly-passes", "courses", "toggle-status",
    # booking
    "create", "update", "checkin", "cancel", "complete",
    # commission
    "tiers", "calculate", "staff-list", "list", "table",
    # class_record
    "evaluation", "coaches", "status-options",
    # member
    "photo", "search-json", "search",
    # membership_card
    "sell", "sold",
    # course, mcp, chat, export, operation_log
    "call-tool", "read-resource", "batch-execute", "set-permission",
    "message", "stream", "clear",
    "tables", "fields",
    "settings", "assets", "summary",
})

# 资源名 → 中文名映射（由 feature_registry 根据配置过滤）
_RESOURCE_CN_MAP = registry.get_active_resource_map()


@app.middleware("http")
async def operation_log_middleware(request: Request, call_next):
    """自动记录所有写操作的日志"""
    method = request.method
    path = request.url.path

    # 只记录写操作，排除登录/日志自身/健康检查
    if method not in ("POST", "PUT", "DELETE"):
        return await call_next(request)
    if path.startswith("/auth/") or path == "/api/health" or path.startswith("/api/logs") or path == "/favicon.ico":
        return await call_next(request)

    # 提取资源名（⚠️ 必须用切片而非 lstrip，lstrip 会误删字符）
    path_part = path[len("/api/"):].split("/")[0] if path.startswith("/api/") else ""
    resource = _RESOURCE_CN_MAP.get(path_part, path_part or "未知")

    # 先处理请求
    response = await call_next(request)

    # 只记录成功的写操作
    if 200 <= response.status_code < 300:
        try:
            db = next(get_db())
            # 获取操作人
            token = request.cookies.get("access_token", "")
            operator = "系统"
            if token:
                from jose import jwt
                from backend.routers.auth import SECRET_KEY, ALGORITHM
                try:
                    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                    operator = payload.get("sub", "系统")
                except Exception:
                    pass
            # IP
            ip = request.client.host if request.client else ""
            # 资源ID：找到 path_part 后第一个非关键字段
            parts = path.rstrip("/").split("/")
            resource_id = ""
            found_resource = False
            for seg in parts:
                if seg == path_part:
                    found_resource = True
                    continue
                if found_resource and seg not in _KNOWN_ACTION_SEGMENTS:
                    resource_id = seg
                    break

            action = {"POST": "create", "PUT": "update", "DELETE": "delete"}.get(method, "unknown")
            record_log(db, operator, action, resource, resource_id, f"{method} {path}")
        except Exception:
            pass

    return response


# ── 全局异常处理器 ──

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """统一 HTTPException 响应格式"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "data": None, "message": exc.detail},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """未捕获异常 → 500 统一格式"""
    # 记录到服务器日志
    import traceback
    print(f"[500] {request.method} {request.url.path}: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"success": False, "data": None, "message": "服务器内部错误"},
    )


# ── 页面路由（按功能开关条件注册）──

if registry.is_enabled("schedule"):
    @app.get("/schedule")
    def schedule_page(request: Request):
        today = date.today()
        return templates.TemplateResponse(
            request=request,
            name="schedule.html",
            context={"title": "教练排班", "year": today.year, "month": today.month},
        )


if registry.is_enabled("booking"):
    @app.get("/booking")
    def booking_page(request: Request):
        today = date.today()
        return templates.TemplateResponse(
            request=request,
            name="booking.html",
            context={"title": "预约管理", "today": today.isoformat()},
        )


if registry.is_enabled("package"):
    @app.get("/packages")
    def packages_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db), v: str = None):
        from backend.routers.package import _build_product_table, _build_member_table
        from backend.models.models import GroupPackage, LessonPackage, MonthlyPass

        products_html = _build_product_table(
            db.query(GroupPackage).order_by(GroupPackage.id.desc()).all()
        )
        lp_q = db.query(LessonPackage).order_by(LessonPackage.id.desc())
        mp_q = db.query(MonthlyPass).order_by(MonthlyPass.id.desc())
        member_html = _build_member_table(lp_q.all(), mp_q.all())

        headers = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
        return templates.TemplateResponse(
            request=request,
            name="packages.html",
            context={
                "request": request, "user": user, "current_page": "packages",
                "products_html": products_html,
                "member_html": member_html,
            },
            headers=headers,
        )


if registry.is_enabled("commission"):
    @app.get("/commission")
    def commission_page(request: Request, user: User = Depends(get_current_user)):
        return templates.TemplateResponse(
            request=request,
            name="commission.html",
            context={"request": request, "user": user, "current_page": "commission"},
        )


@app.get("/")
def root_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"title": "首页"},
    )


if registry.is_enabled("member"):
    @app.get("/members")
    def members_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="members.html",
            context={"title": "会员管理"},
        )


    @app.get("/members/{member_id}")
    def member_detail_page(member_id: str, request: Request, db: Session = Depends(get_db)):
        member = db.query(Member).filter(Member.member_id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="会员不存在")

        # 画像统计
        week_ago = date.today() - timedelta(days=7)
        last_7d_checkins = db.query(Checkin).filter(
            Checkin.member_id == member_id, Checkin.checkin_date >= week_ago
        ).count()
        total_class_count = db.query(ClassRecord).filter(
            ClassRecord.member_id == member_id
        ).count()

        return templates.TemplateResponse(
            request=request,
            name="member_detail.html",
            context={
                "title": f"会员详情 - {member.name}",
                "member": member,
                "member_id": member_id,
                "today": date.today(),
                "profile": {
                    "last_7d_checkins": last_7d_checkins,
                    "total_class_count": total_class_count,
                },
            },
        )


if registry.is_enabled("member_assets"):
    @app.get("/member-assets")
    def member_assets_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="member_assets.html",
            context={"title": "资产残值"},
        )


if registry.is_enabled("staff"):
    @app.get("/staff")
    def staff_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="staff.html",
            context={"title": "员工管理"},
        )


if registry.is_enabled("course"):
    @app.get("/courses")
    def courses_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="courses.html",
            context={"title": "课程管理"},
        )


if registry.is_enabled("checkin"):
    @app.get("/checkin")
    def checkin_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="checkin.html",
            context={"title": "进场核销"},
        )


if registry.is_enabled("sale"):
    @app.get("/sales")
    def sales_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="sales.html",
            context={"title": "售课记录"},
        )


if registry.is_enabled("class_record"):
    @app.get("/class-records")
    def class_records_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="class_records.html",
            context={"title": "上课记录"},
        )


if registry.is_enabled("wristband"):
    @app.get("/wristband")
    def wristband_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="wristband.html",
            context={"title": "手环管理"},
        )


# ── 仪表盘 API（已迁移至 backend/routers/dashboard.py）──


if registry.is_enabled("recharge"):
    @app.get("/recharges")
    def recharges_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="recharges.html",
            context={"title": "会员充值"},
        )


if registry.is_enabled("body_measurement"):
    @app.get("/body-measurements")
    def body_measurements_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="body_measurements.html",
            context={"title": "体测记录"},
        )


if registry.is_enabled("alert"):
    @app.get("/alerts")
    def alerts_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="alerts.html",
            context={"title": "到期提醒"},
        )


if registry.is_enabled("membership_card"):
    @app.get("/membership-cards")
    def membership_cards_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="membership_cards.html",
            context={"title": "会籍卡管理"},
        )


if registry.is_enabled("product"):
    @app.get("/products")
    def products_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="products.html",
            context={"title": "商品零售"},
        )


if registry.is_enabled("finance"):
    @app.get("/finance")
    def finance_page(request: Request):
        from datetime import date
        today = date.today()
        return templates.TemplateResponse(
            request=request,
            name="finance.html",
            context={"title": "收入支出报表", "today": today},
        )


if registry.is_enabled("finance_review"):
    @app.get("/finance-review")
    def finance_review_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="finance_review.html",
            context={"title": "支出审核"},
        )


if registry.is_enabled("finance_budget"):
    @app.get("/finance-budget")
    def finance_budget_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="finance_budget.html",
            context={"title": "预算管理"},
        )


if registry.is_enabled("finance_profit"):
    @app.get("/finance-profit")
    def finance_profit_page(request: Request):
        from datetime import date
        today = date.today()
        return templates.TemplateResponse(
            request=request,
            name="finance_profit.html",
            context={"title": "利润表", "today": today},
        )


if registry.is_enabled("analytics"):
    @app.get("/analytics")
    def analytics_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="analytics.html",
            context={"title": "数据分析看板"},
        )


if registry.is_enabled("log"):
    @app.get("/logs")
    def logs_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="logs.html",
            context={"title": "操作日志"},
        )


if registry.is_enabled("export_data"):
    @app.get("/export")
    def export_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="export.html",
            context={"title": "数据导出"},
        )


if registry.is_enabled("import_data"):
    @app.get("/import")
    def import_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="import.html",
            context={"title": "数据导入"},
        )


if registry.is_enabled("chat"):
    @app.get("/chat")
    def chat_page(request: Request):
        """AI 对话页面"""
        from backend.routers.chat_router import _CHAT_PAGE_HTML
        from fastapi.responses import HTMLResponse
        return HTMLResponse(_CHAT_PAGE_HTML)


if registry.is_enabled("performance"):
    @app.get("/performance")
    def performance_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="performance.html",
            context={"title": "业绩总览"},
        )


    @app.get("/performance/sales")
    def performance_sales_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="performance_sales.html",
            context={"title": "售课业绩"},
        )


    @app.get("/performance/packages")
    def performance_packages_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="performance_packages.html",
            context={"title": "课程包业绩"},
        )


    @app.get("/performance/cards")
    def performance_cards_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="performance_cards.html",
            context={"title": "会籍卡业绩"},
        )


    @app.get("/performance/checkins")
    def performance_checkins_page(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="performance_checkins.html",
            context={"title": "会员进场统计"},
        )


@app.get("/favicon.ico")
async def favicon():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/favicon.svg")

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    from backend.routers.operation_log import get_system_name
    name = get_system_name(db)
    return {"status": "ok", "version": "3.8.8", "system_name": name}


# 路由注册（按功能开关条件注册）
from backend.routers import member, staff, course, sale, class_record, checkin, body_measurement, recharge, alert, membership_card, product, finance, auth, operation_log, export_data, performance, commission, schedule, booking, package, asset_value, dashboard, import_data, finance_review, finance_budget, finance_profit, analytics

if registry.is_enabled("member"):           app.include_router(member.router)
if registry.is_enabled("staff"):            app.include_router(staff.router)
if registry.is_enabled("course"):           app.include_router(course.router)
if registry.is_enabled("sale"):             app.include_router(sale.router)
if registry.is_enabled("class_record"):     app.include_router(class_record.router)
if registry.is_enabled("checkin"):          app.include_router(checkin.router)
if registry.is_enabled("body_measurement"): app.include_router(body_measurement.router)
if registry.is_enabled("recharge"):         app.include_router(recharge.router)
if registry.is_enabled("alert"):            app.include_router(alert.router)
if registry.is_enabled("membership_card"):  app.include_router(membership_card.router)
if registry.is_enabled("product"):          app.include_router(product.router)
if registry.is_enabled("finance"):          app.include_router(finance.router)
app.include_router(auth.router)                      # 认证 — 始终启用
app.include_router(operation_log.router)              # 操作日志 — 始终启用
app.include_router(operation_log.system_router)       # 系统设置 — 始终启用
if registry.is_enabled("performance"):      app.include_router(performance.router)
if registry.is_enabled("export_data"):      app.include_router(export_data.router)
if registry.is_enabled("commission"):       app.include_router(commission.router)
if registry.is_enabled("schedule"):         app.include_router(schedule.router)
if registry.is_enabled("booking"):          app.include_router(booking.router)
if registry.is_enabled("package"):          app.include_router(package.router)
if registry.is_enabled("member_assets"):    app.include_router(asset_value.router)
app.include_router(mcp_router)                         # MCP 工具 — 始终启用
if registry.is_enabled("chat"):             app.include_router(chat_router)
app.include_router(dashboard.router)                   # 仪表盘 API — 始终启用
if registry.is_enabled("import_data"):      app.include_router(import_data.router)
if registry.is_enabled("finance_review"):   app.include_router(finance_review.router)
if registry.is_enabled("finance_budget"):   app.include_router(finance_budget.router)
if registry.is_enabled("finance_profit"):   app.include_router(finance_profit.router)
if registry.is_enabled("analytics"):        app.include_router(analytics.router)
