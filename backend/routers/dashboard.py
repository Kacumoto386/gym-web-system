# -*- coding: utf-8 -*-
"""
仪表盘 API 路由 — 首页 HTMX 片段
V3.7.1
"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend.models.models import Member, Checkin, ClassRecord, Sale, Staff, MembershipCard, LessonPackage

router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])


# ══════════════════════════════════════════
# 统计药丸
# ══════════════════════════════════════════

@router.get("/stats", response_class=HTMLResponse)
def dashboard_stats(db: Session = Depends(get_db)):
    today = date.today()

    total_members = db.query(Member).count()
    active_members = db.query(Member).filter(Member.status.in_(["正常", "有效"])).count()
    today_checkins = db.query(Checkin).filter(Checkin.checkin_date == today).count()
    today_classes = db.query(ClassRecord).filter(ClassRecord.class_date == today).count()
    today_sales = db.query(Sale).filter(Sale.sale_date == today).count()
    month_amount = db.query(func.sum(Sale.actual_amount)).filter(
        Sale.sale_date >= today.replace(day=1)
    ).scalar() or 0
    total_staff = db.query(Staff).filter(Staff.status == "在职").count()

    return f"""
    <div class="flex flex-wrap gap-3">
        <div class="inline-flex items-center gap-2 bg-white rounded-lg px-3 py-2 shadow-sm border border-gray-100 min-w-[100px]">
            <span class="text-xs text-gray-500">总会员</span>
            <span class="text-lg font-bold text-gray-800">{total_members}</span>
        </div>
        <div class="inline-flex items-center gap-2 bg-white rounded-lg px-3 py-2 shadow-sm border border-gray-100 min-w-[100px]">
            <span class="text-xs text-gray-500">有效会员</span>
            <span class="text-lg font-bold text-green-600">{active_members}</span>
        </div>
        <div class="inline-flex items-center gap-2 bg-white rounded-lg px-3 py-2 shadow-sm border border-gray-100 min-w-[100px]">
            <span class="text-xs text-gray-500">今日进场</span>
            <span class="text-lg font-bold text-blue-600">{today_checkins}</span>
        </div>
        <div class="inline-flex items-center gap-2 bg-white rounded-lg px-3 py-2 shadow-sm border border-gray-100 min-w-[100px]">
            <span class="text-xs text-gray-500">今日上课</span>
            <span class="text-lg font-bold text-purple-600">{today_classes}</span>
        </div>
        <div class="inline-flex items-center gap-2 bg-white rounded-lg px-3 py-2 shadow-sm border border-gray-100 min-w-[100px]">
            <span class="text-xs text-gray-500">今日售课</span>
            <span class="text-lg font-bold text-orange-600">{today_sales}</span>
        </div>
        <div class="inline-flex items-center gap-2 bg-white rounded-lg px-3 py-2 shadow-sm border border-gray-100 min-w-[120px]">
            <span class="text-xs text-gray-500">本月营收</span>
            <span class="text-lg font-bold text-green-600">¥{month_amount:,.0f}</span>
        </div>
        <div class="inline-flex items-center gap-2 bg-white rounded-lg px-3 py-2 shadow-sm border border-gray-100 min-w-[100px]">
            <span class="text-xs text-gray-500">在岗员工</span>
            <span class="text-lg font-bold text-gray-600">{total_staff}</span>
        </div>
    </div>
    """


# ══════════════════════════════════════════
# 今日进场记录（首页用）
# ══════════════════════════════════════════

@router.get("/today-checkins", response_class=HTMLResponse)
def today_checkins_dashboard(db: Session = Depends(get_db)):
    """首页今日进场记录区块（最近10条 + 按方式统计）"""
    today = date.today()

    checkins = db.query(Checkin).filter(
        Checkin.checkin_date == today
    ).order_by(Checkin.id.desc()).limit(10).all()

    types_count = {}
    total = 0
    for c in checkins:
        total += 1
        ct = c.checkin_type or "核销"
        types_count[ct] = types_count.get(ct, 0) + 1

    rows = ""
    for c in checkins:
        member = db.query(Member).filter(Member.member_id == c.member_id).first()
        level = member.level if member else ""
        phone = member.phone if member else ""

        ct = c.checkin_type or "核销"
        badge_cls = "bg-green-100 text-green-700" if ct == "核销" else "bg-yellow-100 text-yellow-700" if ct == "体验" else "bg-blue-100 text-blue-700"
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
                <span class="text-xs px-2 py-0.5 rounded-full {badge_cls}">{ct}</span>
            </div>
        </div>"""

    if not rows:
        rows = '<div class="py-6 text-center text-gray-400 text-sm">今日暂无进场记录</div>'

    total_checked = db.query(Checkin).filter(Checkin.checkin_date == today).count()
    wristband_count = db.query(Checkin).filter(Checkin.checkin_date == today, Checkin.checkin_type == "刷卡").count()
    experience_count = db.query(Checkin).filter(Checkin.checkin_date == today, Checkin.checkin_type == "体验").count()
    normal_count = total_checked - wristband_count - experience_count

    return f"""
    <div class="bg-white rounded-xl shadow-sm border border-gray-100">
        <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <div class="flex items-center gap-2">
                <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><use href="#icon-check-circle"/></svg>
                <span class="text-sm font-medium text-gray-700">今日进场</span>
                <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{total_checked} 人</span>
            </div>
            <a href="/checkin" class="text-xs text-blue-600 hover:text-blue-800">管理进场 &rarr;</a>
        </div>
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
        <div class="px-4 py-1 max-h-64 overflow-y-auto">
            {rows}
        </div>
    </div>
    """


# ══════════════════════════════════════════
# 今日预约（首页用）
# ══════════════════════════════════════════

@router.get("/today-bookings", response_class=HTMLResponse)
def today_bookings_dashboard(db: Session = Depends(get_db)):
    """首页今日预约课程签到区块"""
    from backend.routers.booking import today_bookings_html
    return today_bookings_html(db)


# ══════════════════════════════════════════
# 即将到期摘要（首页用—top5最紧急）
# ══════════════════════════════════════════

def _status_tag(days):
    if days < 0:
        return '<span class="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">已过期 {}天</span>'.format(abs(days))
    elif days == 0:
        return '<span class="text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded">今日到期</span>'
    elif days <= 7:
        return '<span class="text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded">{}天后到期</span>'.format(days)
    else:
        return '<span class="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">{}天后</span>'.format(days)


@router.get("/expiring-summary", response_class=HTMLResponse)
def expiring_summary(db: Session = Depends(get_db)):
    today = date.today()
    items = []

    # 会籍到期
    cards = db.query(MembershipCard).filter(
        MembershipCard.status == "正常",
        MembershipCard.end_date != None,
        MembershipCard.end_date <= today + timedelta(days=30),
        MembershipCard.is_product != 1,
    ).order_by(MembershipCard.end_date).limit(10).all()
    for c in cards:
        days = (c.end_date - today).days
        items.append({
            "type": "会籍", "member_name": c.member_name,
            "item_name": c.card_type, "expire_date": c.end_date,
            "remaining_days": days,
        })

    # 课程到期
    lessons = db.query(LessonPackage).filter(
        LessonPackage.status == "正常",
        LessonPackage.valid_until != None,
        LessonPackage.valid_until <= today + timedelta(days=30),
    ).order_by(LessonPackage.valid_until).limit(10).all()
    for lp in lessons:
        days = (lp.valid_until - today).days
        items.append({
            "type": "课程", "member_name": lp.member_name,
            "item_name": lp.course_name, "expire_date": lp.valid_until,
            "remaining_days": days,
        })

    # 会员到期
    members = db.query(Member).filter(
        Member.status == "正常",
        Member.end_date != None,
        Member.end_date <= today + timedelta(days=30),
    ).order_by(Member.end_date).limit(10).all()
    for m in members:
        days = (m.end_date - today).days
        items.append({
            "type": "会员", "member_name": m.name,
            "item_name": "会员到期", "expire_date": m.end_date,
            "remaining_days": days,
        })

    # 按剩余天数升序，取 top 5
    items.sort(key=lambda x: x["remaining_days"])
    items = items[:5]

    if not items:
        return """
        <div class="bg-white rounded-xl shadow-sm border border-gray-100">
            <div class="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
                <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><use href="#icon-check-circle"/></svg>
                <span class="text-sm font-medium text-gray-700">即将到期</span>
            </div>
            <div class="px-4 py-6 text-center text-gray-400 text-xs">近期无到期提醒</div>
        </div>
        """

    rows_html = ""
    for item in items:
        type_cls = {"会籍": "bg-purple-100 text-purple-700", "课程": "bg-blue-100 text-blue-700", "会员": "bg-green-100 text-green-700"}.get(item["type"], "bg-gray-100 text-gray-600")
        rows_html += f"""
        <div class="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
            <div class="flex items-center gap-2">
                <span class="text-xs px-1.5 py-0.5 rounded {type_cls}">{item['type'][:1]}</span>
                <span class="text-xs font-medium text-gray-800">{item["member_name"]}</span>
                <span class="text-xs text-gray-400">{item["item_name"]}</span>
            </div>
            {_status_tag(item["remaining_days"])}
        </div>"""

    count = len(items)
    return f"""
    <div class="bg-white rounded-xl shadow-sm border border-gray-100">
        <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
            <div class="flex items-center gap-2">
                <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><use href="#icon-bell"/></svg>
                <span class="text-sm font-medium text-gray-700">即将到期</span>
                <span class="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">{count} 项</span>
            </div>
            <a href="/alerts" class="text-xs text-blue-600 hover:text-blue-800">查看全部 &rarr;</a>
        </div>
        <div class="px-4 py-1 max-h-64 overflow-y-auto">
            {rows_html}
        </div>
    </div>
    """


# ══════════════════════════════════════════
# 近7日趋势（进场 + 售课金额）
# ══════════════════════════════════════════

@router.get("/trends", response_class=HTMLResponse)
def dashboard_trends(db: Session = Depends(get_db)):
    today = date.today()
    days_ago = today - timedelta(days=6)

    # 进场按日聚合
    checkin_rows = db.query(
        Checkin.checkin_date,
        func.count(Checkin.id).label("cnt"),
    ).filter(
        Checkin.checkin_date >= days_ago,
        Checkin.checkin_date <= today,
    ).group_by(Checkin.checkin_date).all()
    checkin_map = {r.checkin_date: r.cnt for r in checkin_rows}

    # 售课金额按日聚合
    sale_rows = db.query(
        Sale.sale_date,
        func.count(Sale.id).label("cnt"),
        func.sum(Sale.actual_amount).label("amount"),
    ).filter(
        Sale.sale_date >= days_ago,
        Sale.sale_date <= today,
    ).group_by(Sale.sale_date).all()
    sale_map = {r.sale_date: {"cnt": r.cnt, "amount": float(r.amount or 0)} for r in sale_rows}

    days = []
    max_checkin = 0
    max_sale = 0
    for i in range(7):
        d = days_ago + timedelta(days=i)
        c = checkin_map.get(d, 0)
        s = sale_map.get(d, {"cnt": 0, "amount": 0})
        days.append({"date": d, "checkins": c, "sales": s["amount"]})
        if c > max_checkin:
            max_checkin = c
        if s["amount"] > max_sale:
            max_sale = s["amount"]

    max_checkin = max_checkin or 1
    max_sale = max_sale or 1

    bars_html = ""
    for d in days:
        h_c = max(round(d["checkins"] / max_checkin * 70), 4) if d["checkins"] > 0 else 2
        h_s = max(round(d["sales"] / max_sale * 70), 4) if d["sales"] > 0 else 2
        label = d["date"].strftime("%m/%d")
        bars_html += f"""
        <div class="flex-1 flex flex-col items-center gap-1">
            <div class="flex gap-0.5 items-end" style="height:80px">
                <div class="w-3 bg-blue-400 rounded-t" style="height:{h_c}%" title="进场 {d['checkins']} 人次"></div>
                <div class="w-3 bg-green-400 rounded-t" style="height:{h_s}%" title="售课 ¥{d['sales']:,.0f}"></div>
            </div>
            <span class="text-xs text-gray-400">{label}</span>
        </div>"""

    return f"""
    <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
        <div class="flex items-center gap-2 mb-3">
            <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24"><use href="#icon-trending-up"/></svg>
            <span class="text-sm font-medium text-gray-700">近7日趋势</span>
        </div>
        <div class="flex items-end gap-1 min-h-[100px]">
            {bars_html}
        </div>
        <div class="flex gap-4 mt-3 text-xs text-gray-400">
            <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 bg-blue-400 rounded"></span> 进场人次</span>
            <span class="flex items-center gap-1"><span class="w-2.5 h-2.5 bg-green-400 rounded"></span> 售课金额</span>
        </div>
    </div>
    """
