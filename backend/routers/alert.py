# -*- coding: utf-8 -*-
"""
到期提醒 API 路由 + HTMX HTML 片段端点
V3.6.9 — 实时查询各业务表到期数据，替代空 alert 表
"""
from typing import Optional, List
from fastapi import Request, APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import extract
from datetime import date, datetime, timedelta
from backend.database import get_db
from backend.models.models import MembershipCard, LessonPackage, MonthlyPass, Member

router = APIRouter(prefix="/api/alerts", tags=["到期提醒"])

# ═══════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════

def _calc_remaining_days(d):
    """计算距离今天的天数（负值=已过期）"""
    if d is None:
        return None
    today = date.today()
    if isinstance(d, datetime):
        d = d.date()
    return (d - today).days


def _status_badge(days):
    """生成状态标签 HTML — 参考 asset_value.py _status_tag"""
    if days is None:
        return '<span class="text-xs bg-gray-100 text-gray-400 px-2 py-0.5 rounded">未知</span>'
    if days < 0:
        return '<span class="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">已过期</span>'
    if days == 0:
        return '<span class="text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded">今日到期</span>'
    if days <= 7:
        return '<span class="text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded">即将到期</span>'
    if days <= 30:
        return '<span class="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">30天内到期</span>'
    return '<span class="text-xs bg-green-100 text-green-600 px-2 py-0.5 rounded">有效</span>'


def _build_summary_cards(total, expiring_soon, expired, birthday_today):
    return f"""<div class="grid grid-cols-4 gap-4 mb-6">
    <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-gray-400">
        <div class="text-xs text-gray-500 uppercase tracking-wide">总提醒</div>
        <div class="text-2xl font-bold text-gray-800">{total}</div>
    </div>
    <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-orange-400">
        <div class="text-xs text-gray-500 uppercase tracking-wide">即将到期 (≤7天)</div>
        <div class="text-2xl font-bold text-orange-600">{expiring_soon}</div>
    </div>
    <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-red-400">
        <div class="text-xs text-gray-500 uppercase tracking-wide">已过期</div>
        <div class="text-2xl font-bold text-red-600">{expired}</div>
    </div>
    <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-pink-400">
        <div class="text-xs text-gray-500 uppercase tracking-wide">今日生日</div>
        <div class="text-2xl font-bold text-pink-600">{birthday_today}</div>
    </div>
</div>"""


def _days_tag(days):
    if days is None:
        return "-"
    if days < 0:
        return f'<span class="text-red-500 font-medium">已过期 {abs(days)} 天</span>'
    if days == 0:
        return '<span class="text-orange-500 font-medium">今日到期</span>'
    return f'<span class="text-gray-600">{days} 天</span>'


# ═══════════════════════════════════════════
# 各来源查询函数
# ═══════════════════════════════════════════

def _query_expiring_cards(db):
    """会籍到期 — 30天内到期或已过期"""
    today = date.today()
    cutoff = today + timedelta(days=30)
    rows = db.query(MembershipCard).filter(
        MembershipCard.status == '正常',
        MembershipCard.end_date.isnot(None),
        MembershipCard.end_date <= cutoff,
        MembershipCard.is_product != 1,
    ).order_by(MembershipCard.end_date.asc()).all()
    result = []
    for r in rows:
        days = _calc_remaining_days(r.end_date)
        result.append({
            "type": "会籍到期",
            "member_id": r.member_id,
            "member_name": r.member_name or "",
            "item_name": r.card_name or r.card_type or "会籍卡",
            "expire_date": r.end_date.strftime("%Y-%m-%d") if r.end_date else "",
            "remaining_days": days,
        })
    return result


def _query_expiring_lessons(db):
    """课程到期 — 30天内到期或已过期"""
    today = date.today()
    cutoff = today + timedelta(days=30)
    rows = db.query(LessonPackage).filter(
        LessonPackage.status == '正常',
        LessonPackage.valid_until.isnot(None),
        LessonPackage.valid_until <= cutoff,
    ).order_by(LessonPackage.valid_until.asc()).all()
    result = []
    for r in rows:
        days = _calc_remaining_days(r.valid_until)
        result.append({
            "type": "课程到期",
            "member_id": r.member_id,
            "member_name": r.member_name or "",
            "item_name": r.course_name or "课程包",
            "expire_date": r.valid_until.strftime("%Y-%m-%d") if r.valid_until else "",
            "remaining_days": days,
        })
    return result


def _query_expiring_monthly(db):
    """包月到期 — 30天内到期或已过期"""
    today = date.today()
    cutoff = today + timedelta(days=30)
    rows = db.query(MonthlyPass).filter(
        MonthlyPass.status == '正常',
        MonthlyPass.valid_until.isnot(None),
        MonthlyPass.valid_until <= cutoff,
    ).order_by(MonthlyPass.valid_until.asc()).all()
    result = []
    for r in rows:
        days = _calc_remaining_days(r.valid_until)
        result.append({
            "type": "包月到期",
            "member_id": r.member_id,
            "member_name": r.member_name or "",
            "item_name": r.pass_name or "包月",
            "expire_date": r.valid_until.strftime("%Y-%m-%d") if r.valid_until else "",
            "remaining_days": days,
        })
    return result


def _query_expiring_members(db):
    """会员到期 — 30天内到期或已过期"""
    today = date.today()
    cutoff = today + timedelta(days=30)
    rows = db.query(Member).filter(
        Member.status == '正常',
        Member.end_date.isnot(None),
        Member.end_date <= cutoff,
    ).order_by(Member.end_date.asc()).all()
    result = []
    for r in rows:
        days = _calc_remaining_days(r.end_date)
        result.append({
            "type": "会员到期",
            "member_id": r.member_id,
            "member_name": r.name or "",
            "item_name": r.name or "会员",
            "expire_date": r.end_date.strftime("%Y-%m-%d") if r.end_date else "",
            "remaining_days": days,
        })
    return result


def _query_birthdays(db):
    """生日提醒 — 本月或下月过生日的会员"""
    today = date.today()
    current_month = today.month
    next_month = current_month + 1
    if next_month > 12:
        next_month = 1
    rows = db.query(Member).filter(
        Member.status == '正常',
        Member.birth_date.isnot(None),
        extract('month', Member.birth_date).in_([current_month, next_month]),
    ).all()
    result = []
    for r in rows:
        if r.birth_date is None:
            continue
        bd = r.birth_date
        if isinstance(bd, datetime):
            bd = bd.date()
        # 计算下一次生日还有多少天
        this_year_bday = date(today.year, bd.month, bd.day)
        if this_year_bday >= today:
            days = (this_year_bday - today).days
            next_bday = this_year_bday
        else:
            next_bday = date(today.year + 1, bd.month, bd.day)
            days = (next_bday - today).days
        result.append({
            "type": "生日提醒",
            "member_id": r.member_id,
            "member_name": r.name or "",
            "item_name": bd.strftime("%m-%d"),
            "expire_date": bd.strftime("%Y-%m-%d"),
            "remaining_days": days,
            "next_birthday": next_bday.strftime("%Y-%m-%d"),
        })
    # 按剩余天数排序
    result.sort(key=lambda x: x["remaining_days"])
    return result


# ═══════════════════════════════════════════
# 渲染函数
# ═══════════════════════════════════════════

SECTION_STYLES = {
    "会籍到期": ("border-green-400", "bg-green-50", "bg-green-500", "green"),
    "课程到期": ("border-blue-400", "bg-blue-50", "bg-blue-500", "blue"),
    "包月到期": ("border-purple-400", "bg-purple-50", "bg-purple-500", "purple"),
    "会员到期": ("border-yellow-400", "bg-yellow-50", "bg-yellow-500", "yellow"),
    "生日提醒": ("border-pink-400", "bg-pink-50", "bg-pink-500", "pink"),
}


def _build_section(alert_type, rows):
    """构建非生日类型的分组区块（表格结构）"""
    bcolor, hbg, dot, _ = SECTION_STYLES.get(alert_type, ("border-gray-400", "bg-gray-50", "bg-gray-500", "gray"))
    trs = ""
    for r in rows:
        badge = _status_badge(r["remaining_days"])
        days_display = _days_tag(r["remaining_days"])
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 font-medium text-gray-800">{r["member_name"]}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{r["member_id"]}</td>
            <td class="px-4 py-3 text-sm text-gray-700">{r["item_name"]}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{r["expire_date"]}</td>
            <td class="px-4 py-3 text-sm">{days_display}</td>
            <td class="px-4 py-3">{badge}</td>
        </tr>"""
    return f"""<div class="mb-6 border-l-4 {bcolor} bg-white rounded-lg shadow-sm overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 {hbg}">
        <h3 class="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
            <span class="inline-block w-3 h-3 {dot} rounded-full"></span>
            {alert_type}
            <span class="text-gray-400 font-normal text-xs">({len(rows)}条)</span>
        </h3>
    </div>
    <table class="w-full">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr>
                <th class="px-4 py-3">会员姓名</th>
                <th class="px-4 py-3">会员编号</th>
                <th class="px-4 py-3">项目</th>
                <th class="px-4 py-3">到期日期</th>
                <th class="px-4 py-3">剩余天数</th>
                <th class="px-4 py-3">状态</th>
            </tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>
</div>"""


def _build_birthday_section(rows):
    """生日提醒分组区块（不同列结构）"""
    trs = ""
    for r in rows:
        if r["remaining_days"] == 0:
            days_display = '<span class="text-pink-500 font-medium">🎂 今日生日</span>'
        else:
            days_display = _days_tag(r["remaining_days"])
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 font-medium text-gray-800">{r["member_name"]}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{r["member_id"]}</td>
            <td class="px-4 py-3 text-sm text-gray-700">{r["item_name"]}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{r["next_birthday"]}</td>
            <td class="px-4 py-3 text-sm">{days_display}</td>
        </tr>"""
    return f"""<div class="mb-6 border-l-4 border-pink-400 bg-white rounded-lg shadow-sm overflow-hidden">
    <div class="flex items-center justify-between px-4 py-3 bg-pink-50">
        <h3 class="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
            <span class="inline-block w-3 h-3 bg-pink-500 rounded-full"></span>
            生日提醒
            <span class="text-gray-400 font-normal text-xs">({len(rows)}条)</span>
        </h3>
    </div>
    <table class="w-full">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr>
                <th class="px-4 py-3">会员姓名</th>
                <th class="px-4 py-3">会员编号</th>
                <th class="px-4 py-3">出生日期</th>
                <th class="px-4 py-3">即将到来</th>
                <th class="px-4 py-3">天数</th>
            </tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>
</div>"""


# ═══════════════════════════════════════════
# HTMX HTML 片段端点
# ═══════════════════════════════════════════

@router.get("/table", response_class=HTMLResponse)
def alert_table(
    tab: str = Query("all", description="all/expiring/expired"),
    alert_type: str = Query("", description="筛选类型"),
    q: str = Query("", description="搜索会员姓名"),
    db: Session = Depends(get_db),
):
    """实时查询所有到期数据，按类型分组渲染"""
    all_data = []
    all_data.extend(_query_expiring_cards(db))
    all_data.extend(_query_expiring_lessons(db))
    all_data.extend(_query_expiring_monthly(db))
    all_data.extend(_query_expiring_members(db))
    all_data.extend(_query_birthdays(db))

    # 筛选
    if tab == "expiring":
        all_data = [d for d in all_data if d["remaining_days"] is not None and 0 <= d["remaining_days"] <= 30]
    elif tab == "expired":
        all_data = [d for d in all_data if d["remaining_days"] is not None and d["remaining_days"] < 0]

    if alert_type:
        all_data = [d for d in all_data if d["type"] == alert_type]

    if q:
        ql = q.lower()
        all_data = [d for d in all_data if ql in d["member_name"].lower()]

    # 汇总统计
    total = len(all_data)
    expiring_soon = sum(1 for d in all_data if d["remaining_days"] is not None and 0 <= d["remaining_days"] <= 7)
    expired = sum(1 for d in all_data if d["remaining_days"] is not None and d["remaining_days"] < 0)
    birthday_today = sum(1 for d in all_data if d["type"] == "生日提醒" and d["remaining_days"] == 0)

    html = _build_summary_cards(total, expiring_soon, expired, birthday_today)

    # 按类型分组
    type_order = ["会籍到期", "课程到期", "包月到期", "会员到期", "生日提醒"]
    sections = []
    for t in type_order:
        rows = [d for d in all_data if d["type"] == t]
        if not rows:
            continue
        rows.sort(key=lambda x: (x["remaining_days"] if x["remaining_days"] is not None else 9999))
        if t == "生日提醒":
            sections.append(_build_birthday_section(rows))
        else:
            sections.append(_build_section(t, rows))

    if not sections:
        return html + '<div class="text-center py-8 text-gray-400">暂无匹配的提醒数据</div>'

    return html + "".join(sections)


# ═══════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════

@router.get("")
def list_alerts(
    tab: str = Query("all", description="all/expiring/expired"),
    alert_type: Optional[str] = Query(None, description="筛选类型"),
    q: str = Query("", description="搜索会员姓名"),
    db: Session = Depends(get_db),
):
    """JSON 格式返回所有到期数据（供 API 调用）"""
    all_data = []
    all_data.extend(_query_expiring_cards(db))
    all_data.extend(_query_expiring_lessons(db))
    all_data.extend(_query_expiring_monthly(db))
    all_data.extend(_query_expiring_members(db))
    all_data.extend(_query_birthdays(db))

    if tab == "expiring":
        all_data = [d for d in all_data if d["remaining_days"] is not None and 0 <= d["remaining_days"] <= 30]
    elif tab == "expired":
        all_data = [d for d in all_data if d["remaining_days"] is not None and d["remaining_days"] < 0]

    if alert_type:
        all_data = [d for d in all_data if d["type"] == alert_type]

    if q:
        ql = q.lower()
        all_data = [d for d in all_data if ql in d["member_name"].lower()]

    all_data.sort(key=lambda x: (x["remaining_days"] if x["remaining_days"] is not None else 9999))
    return all_data
