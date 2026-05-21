"""
业绩统计 API 路由
V3.1.0 — 业绩总览/售课业绩/课程包业绩/会籍卡业绩/会员进场统计
"""
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy import Integer, cast as sql_cast, case

from backend.database import get_db
from backend.models.models import Sale, LessonPackage, MembershipCard, Checkin

router = APIRouter(prefix="/api/performance", tags=["业绩统计"])

# ══════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════

def get_date_range(period: str, today: date = None):
    """根据 period 返回 (start_date, end_date)，period='全部'时返回 (None, None)"""
    today = today or date.today()
    period = period or "本月"
    if period == "今日":
        return (today, today)
    elif period == "本周":
        start = today - timedelta(days=today.weekday())
        return (start, today)
    elif period == "本月":
        return (today.replace(day=1), today)
    elif period == "上月":
        first = today.replace(day=1)
        last_month_end = first - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return (last_month_start, last_month_end)
    elif period == "本年":
        return (today.replace(month=1, day=1), today)
    else:  # "全部"
        return (None, None)


def calc_remaining_days(end_date_val):
    """计算剩余天数和状态"""
    if not end_date_val:
        return (None, "未知", "")
    if isinstance(end_date_val, str):
        try:
            end_date_val = date.fromisoformat(end_date_val)
        except ValueError:
            return (None, "未知", "")
    remaining = (end_date_val - date.today()).days
    if remaining < 0:
        return (remaining, "已过期", "red")
    elif remaining <= 7:
        return (remaining, "即将到期", "orange")
    else:
        return (remaining, "正常", "green")


def status_badge_html(status: str, color: str = "green") -> str:
    """生成状态标签 HTML"""
    color_map = {
        "green": "bg-green-100 text-green-700",
        "orange": "bg-orange-100 text-orange-700",
        "red": "bg-red-100 text-red-700",
        "gray": "bg-gray-100 text-gray-600",
        "blue": "bg-blue-100 text-blue-700",
    }
    cls = color_map.get(color, color_map["gray"])
    return f'<span class="inline-block px-2 py-0.5 text-xs rounded-full {cls}">{status}</span>'


def build_stats_cards_html(cards: list) -> str:
    """生成统计卡片 HTML 片段"""
    html = '<div class="grid grid-cols-2 md:grid-cols-4 gap-4">'
    for card in cards:
        html += f'''
        <div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
            <div class="text-xs text-gray-400 uppercase tracking-wide">{card["label"]}</div>
            <div class="text-{card.get("color", "gray")}-600 text-3xl font-bold mt-1">{card["value"]}</div>
            <div class="text-xs text-gray-500 mt-1">{card.get("sub", "")}</div>
        </div>'''
    html += '</div>'
    return html


def build_table_html(headers: list, rows: list, table_id: str = "", sort_col: int = -1, sort_dir: str = "") -> str:
    """生成通用表格 HTML 片段（支持可排序表头）"""
    thead_parts = []
    for i, h in enumerate(headers):
        arrow = ""
        if i == sort_col:
            arrow = " ▲" if sort_dir == "asc" else " ▼"
        thead_parts.append(
            f'<th class="px-3 py-2 text-xs font-medium text-gray-500 uppercase text-left cursor-pointer hover:text-gray-700 whitespace-nowrap select-none" '
            f'data-col="{i}">{h}{arrow}</th>'
        )
    thead = "".join(thead_parts)
    tbody = ""
    for row in rows:
        tbody += "<tr class='border-b border-gray-100 hover:bg-gray-50'>" + "".join(
            f'<td class="px-3 py-2 text-sm">{c}</td>' for c in row
        ) + "</tr>"
    if not tbody:
        tbody = '<tr><td colspan="99" class="px-3 py-8 text-center text-gray-400">暂无数据</td></tr>'
    html = f'''
    <div class="bg-white rounded-xl shadow-sm overflow-hidden">
        <div class="overflow-x-auto">
            <table class="w-full" data-table="{table_id}">
                <thead class="bg-gray-50 border-b border-gray-200">{thead}</thead>
                <tbody>{tbody}</tbody>
            </table>
        </div>
    </div>'''
    return html


def build_card_section_html(by_type: list, title: str = "") -> str:
    """生成按类型分组的卡片 HTML"""
    html = f'<div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100"><div class="text-sm font-medium text-gray-700 mb-3">{title}</div><div class="space-y-2">'
    for item in by_type:
        pct = item.get("pct", 0)
        html += f'''
        <div class="flex items-center justify-between text-sm">
            <span class="text-gray-600">{item.get("type", "未知")}</span>
            <div class="flex items-center gap-4">
                <span class="font-medium text-gray-800">{item.get("count", 0)}</span>
                <span class="text-gray-500 w-16 text-right">{item.get("amount", "")}</span>
            </div>
        </div>
        <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div class="h-full bg-blue-500 rounded-full" style="width:{pct}%"></div>
        </div>'''
    html += '</div></div>'
    return html


# ══════════════════════════════════════════════════
# 1. 业绩总览
# ══════════════════════════════════════════════════

@router.get("/overview", response_class=HTMLResponse)
def overview(request: Request):
    """业绩总览页面 HTML 片段（用于 HTMX）"""
    return _overview_html()


@router.get("/overview/cards")
def overview_cards(period: str = Query("本月"), db: Session = Depends(get_db)):
    """业绩总览 4 张统计卡片"""
    start, end = get_date_range(period)

    # 售课
    sale_query = db.query(func.sum(Sale.actual_amount), func.count(Sale.id))
    if start and end:
        sale_query = sale_query.filter(Sale.sale_date >= start, Sale.sale_date <= end)
    sale_total, sale_count = sale_query.first() or (0, 0)
    sale_total = float(sale_total or 0)
    sale_count = sale_count or 0

    # 课程包（统计全部）— 不显示金额（与售课关联重叠），展示课时数
    lesson_packages = db.query(LessonPackage).all()
    pkg_count = len(lesson_packages)
    pkg_active = sum(1 for p in lesson_packages if p.status == "有效")
    pkg_total_hours = sum(p.total_hours or 0 for p in lesson_packages)

    # 会籍卡（按创建时间筛选）
    card_query = db.query(func.sum(MembershipCard.price), func.count(MembershipCard.id))
    if start and end:
        card_query = card_query.filter(MembershipCard.start_date >= start, MembershipCard.start_date <= end)
    card_total, card_count = card_query.first() or (0, 0)
    card_total = float(card_total or 0)
    card_count = card_count or 0
    # active 也按时间段统计
    card_active_query = db.query(func.count(MembershipCard.id)).filter(MembershipCard.status.in_(["有效", "正常"]))
    if start and end:
        card_active_query = card_active_query.filter(MembershipCard.start_date >= start, MembershipCard.start_date <= end)
    card_active = card_active_query.scalar() or 0

    # 进场
    chk_query = db.query(func.count(Checkin.id))
    if start and end:
        chk_query = chk_query.filter(Checkin.checkin_date >= start, Checkin.checkin_date <= end)
    chk_total = chk_query.scalar() or 0

    # 计算日均进场
    if start and end:
        days = (end - start).days + 1
        daily_avg = round(chk_total / days, 1) if days > 0 else 0
    else:
        daily_avg = "--"

    cards = [
        {"label": "💰 售课", "value": f"¥{sale_total:,.0f}", "sub": f"{sale_count} 笔", "color": "blue"},
        {"label": "📦 课程包", "value": f"{pkg_count} 包", "sub": f"有效 {pkg_active} 个 · {pkg_total_hours} 课时", "color": "purple"},
        {"label": "🎫 会籍卡", "value": f"¥{card_total:,.0f}", "sub": f"售出 {card_count} 张 · 有效 {card_active} 张", "color": "green"},
        {"label": "🏃 进场", "value": str(chk_total), "sub": f"日均 {daily_avg} 人次", "color": "orange"},
    ]
    return HTMLResponse(content=build_stats_cards_html(cards))


# ══════════════════════════════════════════════════
# 2. 售课业绩
# ══════════════════════════════════════════════════

@router.get("/sales/stats")
def sale_stats(period: str = Query("本月"), db: Session = Depends(get_db)):
    """售课业绩统计卡片"""
    start, end = get_date_range(period)
    query = db.query(Sale)
    if start and end:
        query = query.filter(Sale.sale_date >= start, Sale.sale_date <= end)

    sales = query.all()
    total_amount = sum(float(s.actual_amount or 0) for s in sales)
    total_count = len(sales)
    days_span = (end - start).days + 1 if start and end else 365
    daily_avg = round(total_amount / days_span, 0) if days_span > 0 else 0

    # 到期状态统计
    expired_amount = sum(float(s.actual_amount or 0) for s in sales if s.end_date and (s.end_date - date.today()).days < 0)
    expiring_amount = sum(float(s.actual_amount or 0) for s in sales if s.end_date and 0 <= (s.end_date - date.today()).days <= 7)

    cards = [
        {"label": "售课总额", "value": f"¥{total_amount:,.0f}", "sub": f"{total_count} 笔", "color": "blue"},
        {"label": "日均", "value": f"¥{daily_avg:,.0f}", "sub": "/日", "color": "green"},
        {"label": "已过期金额", "value": f"¥{expired_amount:,.0f}", "sub": "课程已到期", "color": "red"},
        {"label": "即将到期", "value": f"¥{expiring_amount:,.0f}", "sub": "7天内到期", "color": "orange"},
    ]
    return HTMLResponse(content=build_stats_cards_html(cards))


@router.get("/sales/table")
def sale_table(period: str = Query("本月"), status_filter: str = Query("全部", alias="status"), db: Session = Depends(get_db)):
    """售课表格（含到期状态）"""
    start, end = get_date_range(period)
    query = db.query(Sale)
    if start and end:
        query = query.filter(Sale.sale_date >= start, Sale.sale_date <= end)

    sales = query.order_by(Sale.sale_date.desc()).all()

    headers = ["编号", "会员", "课程", "售课日期", "金额", "到期日", "剩余天数", "状态"]
    rows = []
    for s in sales:
        remaining, _status, _color = calc_remaining_days(s.end_date)

        # 状态筛选
        if status_filter == "normal" and _status != "正常":
            continue
        if status_filter == "expiring" and _status != "即将到期":
            continue
        if status_filter == "expired" and _status != "已过期":
            continue

        remaining_str = f"{remaining}天" if remaining is not None else "--"
        if remaining is not None and remaining < 0:
            remaining_str = f"超期{-remaining}天"

        badge = status_badge_html(_status, _color)
        end_str = s.end_date.isoformat() if s.end_date else "--"
        rows.append([
            s.sale_id or "",
            s.member_name or "",
            s.course_name or "",
            s.sale_date.isoformat() if s.sale_date else "",
            f"¥{float(s.actual_amount or 0):,.0f}",
            end_str,
            remaining_str,
            badge,
        ])

    return HTMLResponse(content=build_table_html(headers, rows, table_id="saleTable"))


# ══════════════════════════════════════════════════
# 3. 课程包业绩
# ══════════════════════════════════════════════════

@router.get("/packages/stats")
def package_stats(db: Session = Depends(get_db)):
    """课程包统计卡片"""
    packages = db.query(LessonPackage).all()
    total_count = len(packages)

    # 课程包金额从 sale 表关联获取
    sale_ids = [p.sale_id for p in packages if p.sale_id]
    if sale_ids:
        sale_rows = db.query(Sale.sale_id, Sale.actual_amount).filter(Sale.sale_id.in_(sale_ids)).all()
        sale_prices = {s[0]: float(s[1] or 0) for s in sale_rows}
    else:
        sale_prices = {}
    total_amount = sum(sale_prices.get(p.sale_id, 0) for p in packages)

    avg_price = round(total_amount / total_count, 0) if total_count > 0 else 0
    total_hours = sum(p.total_hours or 0 for p in packages)
    used_hours = sum(p.used_hours or 0 for p in packages)
    remaining_hours = sum(p.remaining_hours or 0 for p in packages)
    active_count = sum(1 for p in packages if p.status == "有效")
    expired_count = total_count - active_count
    usage_rate = round(used_hours / total_hours * 100, 1) if total_hours > 0 else 0

    cards = [
        {"label": "已售包数", "value": str(total_count), "sub": f"有效 {active_count} 个", "color": "blue"},
        {"label": "总金额", "value": f"¥{total_amount:,.0f}", "sub": f"均价 ¥{avg_price:,.0f}", "color": "green"},
        {"label": "课时消耗", "value": f"{used_hours}/{total_hours}", "sub": f"消耗率 {usage_rate}%", "color": "purple"},
        {"label": "剩余课时", "value": str(remaining_hours), "sub": f"已用完 {expired_count} 个", "color": "orange"},
    ]
    return HTMLResponse(content=build_stats_cards_html(cards))


@router.get("/packages/table")
def package_table(
    sort_col: str = Query("", alias="sort"), 
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db)
):
    """课程包表格（支持服务端排序）"""
    sort_col_idx = int(sort_col) if sort_col else -1

    # 可排序列映射
    sort_map = {
        0: LessonPackage.package_id,
        1: LessonPackage.member_name,
        2: LessonPackage.course_name,
        3: "total_hours",
        4: "used_hours",
        5: "remaining_hours",
        7: LessonPackage.valid_until,
    }

    query = db.query(LessonPackage)
    if sort_col_idx in sort_map:
        col = sort_map[sort_col_idx]
        if isinstance(col, str):
            col = func.coalesce(getattr(LessonPackage, col, None), 0)
        query = query.order_by(col.desc() if sort_dir == "desc" else col.asc())
    else:
        query = query.order_by(LessonPackage.valid_until.desc().nullslast())

    packages = query.all()

    headers = ["编号", "会员", "课程", "总课时", "已用", "剩余", "消耗率", "有效期止", "状态"]
    rows = []
    for p in packages:
        status = p.status or "未知"
        color = "green"
        if status == "已用完" or status == "已过期":
            color = "red"
        elif status != "有效":
            color = "gray"
        badge = status_badge_html(status, color if status == "有效" else "red" if status in ("已用完", "已过期") else "gray")

        total = p.total_hours or 0
        used = p.used_hours or 0
        remaining = p.remaining_hours or 0
        ratio = f"{round(used / total * 100, 0):.0f}%" if total > 0 else "--"
        valid_until = p.valid_until.isoformat() if p.valid_until else "--"

        rows.append([
            p.package_id or "",
            p.member_name or "",
            p.course_name or "",
            str(total),
            str(used),
            str(remaining),
            ratio,
            valid_until,
            badge,
        ])

    return HTMLResponse(content=build_table_html(headers, rows, table_id="packageTable", sort_col=sort_col_idx, sort_dir=sort_dir))


# ══════════════════════════════════════════════════
# 4. 会籍卡业绩
# ══════════════════════════════════════════════════

@router.get("/cards/stats")
def card_stats(period: str = Query("全部"), db: Session = Depends(get_db)):
    """会籍卡统计卡片"""
    start, end = get_date_range(period)
    query = db.query(MembershipCard)
    if start and end:
        query = query.filter(MembershipCard.start_date >= start, MembershipCard.start_date <= end)

    cards_data = query.all()
    total = len(cards_data)
    total_amount = sum(float(c.price or 0) for c in cards_data)
    avg_price = round(total_amount / total, 0) if total > 0 else 0
    active = sum(1 for c in cards_data if c.status == "有效")
    expired = total - active

    cards = [
        {"label": "总卡数", "value": str(total), "sub": f"有效 {active} 张", "color": "blue"},
        {"label": "总金额", "value": f"¥{total_amount:,.0f}", "sub": f"均价 ¥{avg_price:,.0f}", "color": "green"},
        {"label": "有效", "value": str(active), "sub": f"占比 {round(active/total*100,0) if total>0 else 0:.0f}%", "color": "green"},
        {"label": "已过期", "value": str(expired), "sub": f"占比 {round(expired/total*100,0) if total>0 else 0:.0f}%", "color": "red"},
    ]
    return HTMLResponse(content=build_stats_cards_html(cards))


@router.get("/cards/by-type")
def card_by_type(period: str = Query("全部"), db: Session = Depends(get_db)):
    """会籍卡按类型分组统计"""
    start, end = get_date_range(period)
    query = db.query(MembershipCard.card_type, func.count(MembershipCard.id), func.sum(MembershipCard.price))
    if start and end:
        query = query.filter(MembershipCard.start_date >= start, MembershipCard.start_date <= end)
    rows = query.group_by(MembershipCard.card_type).all()

    total_count = sum(r[1] or 0 for r in rows)
    items = []
    for r in rows:
        count = r[1] or 0
        amount = float(r[2] or 0)
        pct = round(count / total_count * 100, 1) if total_count > 0 else 0
        items.append({"type": r[0] or "未知", "count": count, "amount": f"¥{amount:,.0f}", "pct": pct})

    return HTMLResponse(content=build_card_section_html(items, "按卡类型分布"))


@router.get("/cards/table")
def card_table(period: str = Query("全部"), db: Session = Depends(get_db)):
    """会籍卡明细表格"""
    start, end = get_date_range(period)
    query = db.query(MembershipCard)
    if start and end:
        query = query.filter(MembershipCard.start_date >= start, MembershipCard.start_date <= end)

    cards_data = query.order_by(MembershipCard.start_date.desc().nullslast()).all()

    headers = ["编号", "会员", "卡类型", "售价", "天数", "开始日", "截止日", "状态"]
    rows = []
    for c in cards_data:
        color = "green" if c.status == "有效" else "red"
        badge = status_badge_html(c.status or "未知", color)
        rows.append([
            c.card_id or "",
            c.member_name or "",
            c.card_type or "",
            f"¥{float(c.price or 0):,.0f}",
            str(c.duration_days or ""),
            c.start_date.isoformat() if c.start_date else "",
            c.end_date.isoformat() if c.end_date else "",
            badge,
        ])

    return HTMLResponse(content=build_table_html(headers, rows, table_id="cardTable"))


# ══════════════════════════════════════════════════
# 5. 会员进场统计
# ══════════════════════════════════════════════════

@router.get("/checkins/stats")
def checkin_stats(period: str = Query("本月"), db: Session = Depends(get_db)):
    """进场统计卡片"""
    start, end = get_date_range(period)
    query = db.query(Checkin)
    if start and end:
        query = query.filter(Checkin.checkin_date >= start, Checkin.checkin_date <= end)

    chekins_data = query.all()
    total = len(chekins_data)

    # 有进场天数
    unique_days = set()
    for c in chekins_data:
        if c.checkin_date:
            unique_days.add(c.checkin_date.isoformat())
    active_days = len(unique_days)

    days_span = (end - start).days + 1 if start and end else 365
    daily_avg = round(total / days_span, 1) if days_span > 0 else 0

    # 单日最高
    from collections import Counter
    day_counts = Counter(c.checkin_date.isoformat() if c.checkin_date else "" for c in chekins_data)
    peak_day = max(day_counts, key=day_counts.get) if day_counts else ""
    peak_count = day_counts.get(peak_day, 0)

    cards = [
        {"label": "总进场", "value": str(total), "sub": f"{active_days} 天有进场记录", "color": "blue"},
        {"label": "日均进场", "value": str(daily_avg), "sub": "人次/日", "color": "green"},
        {"label": "单日最高", "value": str(peak_count), "sub": f"日期: {peak_day}", "color": "orange"},
    ]
    return HTMLResponse(content=build_stats_cards_html(cards))


@router.get("/checkins/by-type")
def checkin_by_type(period: str = Query("本月"), db: Session = Depends(get_db)):
    """进场按方式统计"""
    start, end = get_date_range(period)
    query = db.query(Checkin.checkin_type, func.count(Checkin.id))
    if start and end:
        query = query.filter(Checkin.checkin_date >= start, Checkin.checkin_date <= end)
    rows = query.group_by(Checkin.checkin_type).all()

    total_count = sum(r[1] or 0 for r in rows)
    items = []
    for r in rows:
        count = r[1] or 0
        pct = round(count / total_count * 100, 1) if total_count > 0 else 0
        items.append({"type": r[0] or "未知", "count": count, "pct": pct})

    return HTMLResponse(content=build_card_section_html(items, "按进场方式分布"))


@router.get("/checkins/by-hour")
def checkin_by_hour(period: str = Query("本月"), db: Session = Depends(get_db)):
    """进场按时段统计"""
    start, end = get_date_range(period)
    query = db.query(Checkin.checkin_time)
    if start and end:
        query = query.filter(Checkin.checkin_date >= start, Checkin.checkin_date <= end)
    times = [r[0] for r in query.all() if r[0]]

    hour_counts = {"清晨(6-9)": 0, "上午(9-12)": 0, "下午(12-17)": 0, "晚上(17-22)": 0, "其他": 0}
    for t in times:
        try:
            hour = int(t.split(":")[0])
        except (ValueError, IndexError):
            hour_counts["其他"] += 1
            continue
        if 6 <= hour < 9:
            hour_counts["清晨(6-9)"] += 1
        elif 9 <= hour < 12:
            hour_counts["上午(9-12)"] += 1
        elif 12 <= hour < 17:
            hour_counts["下午(12-17)"] += 1
        elif 17 <= hour < 22:
            hour_counts["晚上(17-22)"] += 1
        else:
            hour_counts["其他"] += 1

    total = sum(hour_counts.values())
    html = '<div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100"><div class="text-sm font-medium text-gray-700 mb-3">时段分布</div><div class="space-y-3">'
    for period_name, count in hour_counts.items():
        pct = round(count / total * 100, 1) if total > 0 else 0
        bar_width = max(pct, 2) if pct > 0 else 0
        html += f'''
        <div>
            <div class="flex justify-between text-sm mb-1">
                <span class="text-gray-600">{period_name}</span>
                <span class="text-gray-500">{count} 人次 ({pct}%)</span>
            </div>
            <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div class="h-full bg-blue-500 rounded-full" style="width:{bar_width}%"></div>
            </div>
        </div>'''
    html += '</div></div>'
    return HTMLResponse(content=html)


@router.get("/checkins/table")
def checkin_table(period: str = Query("本月"), db: Session = Depends(get_db)):
    """进场明细表格"""
    start, end = get_date_range(period)
    query = db.query(Checkin)
    if start and end:
        query = query.filter(Checkin.checkin_date >= start, Checkin.checkin_date <= end)

    chekins_data = query.order_by(Checkin.checkin_date.desc(), Checkin.checkin_time.desc()).all()

    headers = ["日期", "时间", "会员", "类型", "跟进员工"]
    rows = []
    for c in chekins_data:
        rows.append([
            c.checkin_date.isoformat() if c.checkin_date else "",
            c.checkin_time or "--",
            c.member_name or "",
            c.checkin_type or "--",
            c.staff_followup or "--",
        ])

    return HTMLResponse(content=build_table_html(headers, rows, table_id="checkinTable"))


def _overview_html():
    """业绩总览页面（不含 base.html 继承的 HTML 片段，用于 HTMX 加载）"""
    return """
    <div class="flex items-center justify-between mb-6">
        <div>
            <h2 class="text-xl font-semibold text-gray-800">📊 业绩总览</h2>
            <p class="text-sm text-gray-500 mt-1">核心业务指标概览</p>
        </div>
        <select id="periodSelect"
                class="px-3 py-2 border rounded-lg text-sm bg-white shadow-sm"
                hx-get="/api/performance/overview/cards" hx-trigger="change"
                hx-target="#statsCards" hx-params="period" name="period">
            <option value="今日">今日</option>
            <option value="本周">本周</option>
            <option value="本月" selected>本月</option>
            <option value="上月">上月</option>
            <option value="本年">本年</option>
            <option value="全部">全部</option>
        </select>
    </div>
    <div id="statsCards" hx-get="/api/performance/overview/cards?period=本月" hx-trigger="load">
        <div class="text-center py-8 text-gray-400">加载中...</div>
    </div>
    """
