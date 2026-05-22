"""
FastAPI 应用入口
V3.6.3 — 会员管理页面 UI 紧凑化 + 表格列宽优化
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（覆盖已有环境变量）
dotenv_path = Path(__file__).parent.parent / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path, override=True)


sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from backend.database import init_db, get_db
from backend.models.models import Member, Staff, Checkin, Sale, Course, ClassRecord, Wristband
from backend.routers.auth import get_current_user, User
from backend.routers.operation_log import record_log
from backend.routers.mcp_router import router as mcp_router
from backend.routers.chat_router import router as chat_router

app = FastAPI(
    title="鼠小弟健身管理系统",
    description="Web 版健身管理系统 V3.6.1 — ConversationRuntime AI 对话",
    version="3.6.1",
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

    # 提取资源名
    path_part = path.lstrip("/api/").split("/")[0] if path.startswith("/api/") else ""
    resource_map = {
        "members": "会员", "staff": "员工", "courses": "课程",
        "sales": "售课记录", "class-records": "上课记录", "checkins": "进场记录",
        "wristbands": "手环", "body-measurements": "体测记录", "recharges": "充值记录",
        "alerts": "到期提醒", "membership-cards": "会籍卡", "products": "商品",
        "product-sales": "商品零售", "finance": "财务",
    }
    resource = resource_map.get(path_part, path_part or "未知")

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
            # 资源ID（从路径末尾取）
            parts = path.rstrip("/").split("/")
            resource_id = parts[-1] if parts and not parts[-1].startswith("api") else ""

            action = {"POST": "create", "PUT": "update", "DELETE": "delete"}.get(method, "unknown")
            record_log(db, operator, action, resource, resource_id, f"{method} {path}")
        except Exception:
            pass

    return response


# ── 页面路由 ──

@app.get("/schedule")
def schedule_page(request: Request):
    today = date.today()
    return templates.TemplateResponse(
        request=request,
        name="schedule.html",
        context={"title": "教练排班", "year": today.year, "month": today.month},
    )


@app.get("/booking")
def booking_page(request: Request):
    today = date.today()
    return templates.TemplateResponse(
        request=request,
        name="booking.html",
        context={"title": "预约管理", "today": today.isoformat()},
    )


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
    return templates.TemplateResponse(
        request=request,
        name="member_detail.html",
        context={
            "title": f"会员详情 - {member.name}",
            "member": member,
            "member_id": member_id,
            "today": date.today(),
        },
    )


@app.get("/member-assets")
def member_assets_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="member_assets.html",
        context={"title": "资产残值"},
    )


@app.get("/staff")
def staff_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="staff.html",
        context={"title": "员工管理"},
    )


@app.get("/courses")
def courses_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="courses.html",
        context={"title": "课程管理"},
    )


@app.get("/checkin")
def checkin_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="checkin.html",
        context={"title": "进场核销"},
    )


@app.get("/sales")
def sales_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="sales.html",
        context={"title": "售课记录"},
    )


@app.get("/class-records")
def class_records_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="class_records.html",
        context={"title": "上课记录"},
    )


@app.get("/wristband")
def wristband_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="wristband.html",
        context={"title": "手环管理"},
    )


# ── 仪表盘统计 API ──

@app.get("/api/dashboard/stats", response_class=HTMLResponse)
def dashboard_stats(db: Session = Depends(get_db)):
    today = date.today()
    today_str = today.isoformat()

    # 统计数字
    total_members = db.query(Member).count()
    active_members = db.query(Member).filter(Member.status.in_(["正常", "有效"])).count()
    total_staff = db.query(Staff).filter(Staff.status == "在职").count()
    today_checkins = db.query(Checkin).filter(Checkin.checkin_date == today).count()
    total_courses = db.query(Course).filter(Course.status == "上架").count()
    total_sales_month = db.query(Sale).filter(
        Sale.sale_date >= today.replace(day=1)
    ).count()
    month_amount = db.query(Sale).filter(
        Sale.sale_date >= today.replace(day=1)
    ).with_entities(Sale.actual_amount).all()
    month_revenue = sum(float(a[0] or 0) for a in month_amount)
    today_classes = db.query(ClassRecord).filter(ClassRecord.class_date == today).count()
    today_sales = db.query(Sale).filter(Sale.sale_date == today).count()

    return f"""
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
            <div class="text-xs text-gray-400 uppercase tracking-wide">总会员</div>
            <div class="text-3xl font-bold text-gray-800 mt-1">{total_members}</div>
            <div class="text-xs text-green-600 mt-1">有效 {active_members} 人</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
            <div class="text-xs text-gray-400 uppercase tracking-wide">今日进场</div>
            <div class="text-3xl font-bold text-blue-600 mt-1">{today_checkins}</div>
            <div class="text-xs text-gray-500 mt-1">今日上课 {today_classes} 节</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
            <div class="text-xs text-gray-400 uppercase tracking-wide">本月售课</div>
            <div class="text-3xl font-bold text-purple-600 mt-1">{total_sales_month}</div>
            <div class="text-xs text-gray-500 mt-1">今日售课 {today_sales} 笔</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
            <div class="text-xs text-gray-400 uppercase tracking-wide">本月营收</div>
            <div class="text-3xl font-bold text-green-600 mt-1">¥{month_revenue:,.0f}</div>
            <div class="text-xs text-gray-500 mt-1">在岗员工 {total_staff} 人</div>
        </div>
    </div>
    """


@app.get("/recharges")
def recharges_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="recharges.html",
        context={"title": "会员充值"},
    )


# ── 首页今日预约课程签到 ──

@app.get("/api/dashboard/today-bookings", response_class=HTMLResponse)
def today_bookings_dashboard(db: Session = Depends(get_db)):
    """首页今日预约课程签到区块"""
    from backend.routers.booking import today_bookings_html
    return today_bookings_html(db)


# ── 首页今日进场记录 + 快速签到 ──

@app.get("/api/dashboard/today-checkins", response_class=HTMLResponse)
def today_checkins_dashboard(db: Session = Depends(get_db)):
    """首页今日进场记录区块（最近10条 + 按方式统计）"""
    today = date.today()

    # 最近10条进场记录
    checkins = db.query(Checkin).filter(
        Checkin.checkin_date == today
    ).order_by(Checkin.id.desc()).limit(10).all()

    # 按核销方式统计
    types_count = {}
    total = 0
    for c in checkins:
        total += 1
        ct = c.checkin_type or "核销"
        types_count[ct] = types_count.get(ct, 0) + 1

    # 查找会员详细数据
    rows = ""
    for c in checkins:
        # 查找会员头像/等级
        member = db.query(Member).filter(Member.member_id == c.member_id).first()
        level = member.level if member else ""
        phone = member.phone if member else ""

        # 进场方式图标
        ct = c.checkin_type or "核销"
        icon = "✅" if ct == "核销" else "👋" if ct == "体验" else "🏷️" if ct == "刷卡" else "✅"

        time_str = c.checkin_date.isoformat() if hasattr(c.checkin_date, 'isoformat') else str(c.checkin_date)
        rows += f"""
        <div class="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
            <div class="flex items-center gap-3">
                <span class="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold">{c.member_name[0] if c.member_name else '?'}</span>
                <div>
                    <span class="text-sm font-medium text-gray-800">{c.member_name}</span>
                    <span class="text-xs text-gray-400 ml-2">{phone}</span>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <span class="text-xs px-2 py-0.5 rounded-full {'bg-green-100 text-green-700' if ct == '核销' else 'bg-yellow-100 text-yellow-700' if ct == '体验' else 'bg-blue-100 text-blue-700'}">{icon} {ct}</span>
            </div>
        </div>"""

    if not rows:
        rows = '<div class="py-6 text-center text-gray-400 text-sm">今日暂无进场记录</div>'

    # 统计卡片
    total_checked = db.query(Checkin).filter(Checkin.checkin_date == today).count()
    wristband_count = db.query(Checkin).filter(Checkin.checkin_date == today, Checkin.checkin_type == "刷卡").count()
    experience_count = db.query(Checkin).filter(Checkin.checkin_date == today, Checkin.checkin_type == "体验").count()
    normal_count = total_checked - wristband_count - experience_count

    return f"""
    <div class="bg-white rounded-xl shadow-sm border border-gray-100">
        <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <div class="flex items-center gap-2">
                <span class="text-base">📊</span>
                <span class="text-sm font-medium text-gray-700">今日进场</span>
                <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{total_checked} 人</span>
            </div>
            <a href="/checkin" class="text-xs text-blue-600 hover:text-blue-800">管理进场 &rarr;</a>
        </div>
        <!-- 进场方式统计 -->
        <div class="grid grid-cols-3 gap-1 px-4 py-2 bg-gray-50 border-b border-gray-100">
            <div class="text-center">
                <div class="text-lg font-bold text-gray-800">{normal_count}</div>
                <div class="text-xs text-gray-400">核销入场</div>
            </div>
            <div class="text-center">
                <div class="text-lg font-bold text-yellow-600">{wristband_count}</div>
                <div class="text-xs text-gray-400">🏷️ 刷卡入场</div>
            </div>
            <div class="text-center">
                <div class="text-lg font-bold text-green-600">{experience_count}</div>
                <div class="text-xs text-gray-400">👋 无卡体验</div>
            </div>
        </div>
        <!-- 进场记录列表 -->
        <div class="px-4 py-1 max-h-64 overflow-y-auto">
            {rows}
        </div>
    </div>
    """


@app.get("/body-measurements")
def body_measurements_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="body_measurements.html",
        context={"title": "体测记录"},
    )


@app.get("/alerts")
def alerts_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="alerts.html",
        context={"title": "到期提醒"},
    )


@app.get("/membership-cards")
def membership_cards_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="membership_cards.html",
        context={"title": "会籍卡管理"},
    )


@app.get("/products")
def products_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={"title": "商品零售"},
    )


@app.get("/finance")
def finance_page(request: Request):
    from datetime import date
    today = date.today()
    return templates.TemplateResponse(
        request=request,
        name="finance.html",
        context={"title": "收入支出报表", "today": today},
    )


@app.get("/logs")
def logs_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="logs.html",
        context={"title": "操作日志"},
    )


@app.get("/export")
def export_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="export.html",
        context={"title": "数据导出"},
    )


# ── 业绩统计页面路由 ──

@app.get("/chat")
def chat_page(request: Request):
    """AI 对话页面"""
    from backend.routers.chat_router import _CHAT_PAGE_HTML
    from fastapi.responses import HTMLResponse
    return HTMLResponse(_CHAT_PAGE_HTML)


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


@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    from backend.routers.operation_log import get_system_name
    name = get_system_name(db)
    return {"status": "ok", "version": "3.6.1", "system_name": name}


# 路由注册
from backend.routers import member, staff, course, sale, class_record, checkin, body_measurement, recharge, alert, membership_card, product, finance, auth, operation_log, export_data, performance, commission, schedule, booking, package, asset_value
app.include_router(member.router)
app.include_router(staff.router)
app.include_router(course.router)
app.include_router(sale.router)
app.include_router(class_record.router)
app.include_router(checkin.router)
app.include_router(body_measurement.router)
app.include_router(recharge.router)
app.include_router(alert.router)
app.include_router(membership_card.router)
app.include_router(product.router)
app.include_router(finance.router)
app.include_router(auth.router)
app.include_router(operation_log.router)
app.include_router(operation_log.system_router)  # 系统设置
app.include_router(performance.router)
app.include_router(export_data.router)
app.include_router(commission.router)
app.include_router(schedule.router)
app.include_router(booking.router)
app.include_router(package.router)
app.include_router(asset_value.router)
app.include_router(mcp_router)
app.include_router(chat_router)
