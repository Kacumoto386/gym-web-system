# -*- coding: utf-8 -*-
"""
会员资产残值查询 API 路由
V3.3.4 — 细化数据展示

细化内容:
1. 跳过 member_id='-' 的脏数据
2. 课程包 course_id 含逗号时取多课程平均价
3. Course.name 字段修正 (DB 中为 name 而非 course_name)
4. 主表格增加到期天数/剩余次数列
5. 明细弹窗增加状态标签和日期进度条
6. CSV 导出增加到期状态列
"""
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models.models import (
    Member, MembershipCard, LessonPackage, Course, Sale, MonthlyPass, GroupPackage
)

router = APIRouter(prefix="/api/asset-values", tags=["资产残值"])

TODAY = date.today()


# ══════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════

def _calc_remaining_days(end_date_val) -> int:
    """计算到期剩余天数，已过期返回负数"""
    if not end_date_val:
        return 0
    if isinstance(end_date_val, str):
        try:
            end = date.fromisoformat(end_date_val)
        except ValueError:
            return 0
    else:
        end = end_date_val
    return (end - TODAY).days


def _remaining_days_tag(days: int) -> str:
    """生成到期剩余天数标签 HTML"""
    if days is None:
        return '<span class="text-gray-400 text-xs">无期限</span>'
    if days < 0:
        return f'<span class="text-red-500 font-medium">已过期 {abs(days)} 天</span>'
    elif days == 0:
        return '<span class="text-orange-500 font-medium">今日到期</span>'
    elif days <= 7:
        return f'<span class="text-orange-500 font-medium">{days} 天</span>'
    else:
        return f'<span class="text-gray-500">{days} 天</span>'


def _card_type_label(card: MembershipCard) -> str:
    """返回有意义的会籍卡类型名"""
    ct = (card.card_type or "").strip()
    if ct:
        return ct
    # 无 card_type 时通过字段推断
    if card.total_classes and card.total_classes > 0:
        return "次卡"
    if card.face_value and float(card.face_value) > 0:
        return "现金卡"
    if card.duration_days and card.duration_days > 0:
        return "期限卡"
    return "会籍卡"


def _card_remaining_count(card: MembershipCard) -> tuple:
    """返回 (剩余次数描述, 剩余数值/余额)
    对次卡：剩余次数；对现金卡：剩余余额；对期限卡：剩余天数
    """
    ct = (card.card_type or "").strip()
    price = float(card.price or 0)
    consumed = float(card.consumed_amount or 0)

    if "次卡" in ct or card.total_classes:
        total = card.total_classes or 0
        bonus = card.bonus_classes or 0
        total_with_bonus = total + bonus
        if total_with_bonus > 0:
            unit_val = price / total_with_bonus if price > 0 else 0
            used_count = round(consumed / unit_val) if unit_val > 0 else 0
            remaining = max(total_with_bonus - used_count, 0)
            desc = "剩余 {} 次 / 共 {}+{}次".format(remaining, total, bonus) if bonus else "剩余 {} 次 / 共 {} 次".format(remaining, total_with_bonus)
            return (desc, remaining)
        return ("", 0)

    if "现金卡" in ct or float(card.face_value or 0) > 0:
        remaining_balance = max(price - consumed, 0)
        return ("余额 ¥{:.2f} / 面值 ¥{:.2f}".format(remaining_balance, price), remaining_balance)

    # 期限卡 / 默认
    remaining_days = _calc_remaining_days(card.end_date)
    dur = card.duration_days or 0
    if dur:
        return ("剩余 {} 天 / 共 {} 天".format(remaining_days, dur), remaining_days)
    return ("剩余 {} 天".format(remaining_days), remaining_days)


# ══════════════════════════════════════════════════
# 核心计算函数
# ══════════════════════════════════════════════════

def calc_card_residual(card: MembershipCard) -> float:
    """计算单张会籍卡的残值"""
    # 跳过无会员卡
    if not card.member_id or card.member_id.strip() in ("", "-"):
        return 0.0

    if card.status not in ("正常", "有效"):
        return 0.0

    price = float(card.price or 0)

    # 过期判断
    remaining_days = _calc_remaining_days(card.end_date)
    if remaining_days <= 0:
        return 0.0

    # 次卡
    if card.card_type and "次卡" in card.card_type:
        total = card.total_classes or 0
        if total <= 0:
            return 0.0
        consumed = float(card.consumed_amount or 0)
        remaining_value = price - consumed
        return max(remaining_value, 0.0)

    # 现金卡/期限卡：price - consumed
    consumed = float(card.consumed_amount or 0)
    remaining = price - consumed
    return max(remaining, 0.0)


def calc_sale_unit_price(db: Session, member_id: str, course_id: str = "") -> float:
    """从 Sale 表计算某会员某课程的单课时均价
    对多课程组合（如 "C005,C008"）取所有匹配课程的平均单价
    """
    query = db.query(Sale).filter(Sale.member_id == member_id)
    if course_id:
        cids = [c.strip() for c in course_id.split(",") if c.strip()]
        if len(cids) > 1:
            query = query.filter(Sale.course_id.in_(cids))
        else:
            query = query.filter(Sale.course_id == course_id)
    sales = query.order_by(Sale.id.desc()).limit(20).all()
    # 收集所有有效单价
    prices = []
    for s in sales:
        total_h = s.total_hours or 0
        if total_h > 0 and (s.actual_amount or 0) > 0:
            prices.append(float(s.actual_amount) / total_h)
    if prices:
        return sum(prices) / len(prices)
    return 0.0


def calc_lesson_package_residual(db: Session, pkg: LessonPackage) -> dict:
    """计算单个课程包的残值"""
    remaining = pkg.remaining_hours or 0
    if remaining <= 0:
        return {"remaining": 0, "unit_price": 0.0, "total": 0.0,
                "total_hours": pkg.total_hours or 0, "used_hours": pkg.used_hours or 0}

    unit = calc_sale_unit_price(db, pkg.member_id or "", pkg.course_id or "")
    if unit <= 0 and pkg.course_id:
        # 尝试从 Course 表取标准价
        cids = [c.strip() for c in pkg.course_id.split(",") if c.strip()]
        if len(cids) > 1:
            # 多课程取平均
            courses = db.query(Course).filter(Course.course_id.in_(cids)).all()
            prices = [float(c.standard_price or 0) for c in courses if c.standard_price and float(c.standard_price) > 0]
            unit = sum(prices) / len(prices) if prices else 0.0
        else:
            course = db.query(Course).filter(Course.course_id == pkg.course_id).first()
            if course:
                unit = float(course.standard_price or 0)
    if unit <= 0 and pkg.sale_id:
        sale = db.query(Sale).filter(Sale.sale_id == pkg.sale_id).first()
        if sale and (sale.total_hours or 0) > 0 and (sale.actual_amount or 0) > 0:
            unit = float(sale.actual_amount) / sale.total_hours

    total = remaining * unit
    return {"remaining": remaining, "unit_price": round(unit, 2), "total": round(total, 2),
            "total_hours": pkg.total_hours or 0, "used_hours": pkg.used_hours or 0,
            "remaining_days": _calc_remaining_days(pkg.valid_until)}


def calc_monthly_pass_residual(pass_obj: MonthlyPass) -> dict:
    """计算包月团课/包月私教的残值"""
    if pass_obj.status not in ("正常", "有效"):
        return {"remaining": 0, "unit_price": 0.0, "total": 0.0, "remaining_days": 0}
    if not pass_obj.valid_until:
        return {"remaining": 0, "unit_price": 0.0, "total": 0.0, "remaining_days": 0}

    remaining_days = _calc_remaining_days(pass_obj.valid_until)
    if remaining_days <= 0:
        return {"remaining": 0, "unit_price": 0.0, "total": 0.0, "remaining_days": 0}

    price = float(pass_obj.price or 0)
    duration = (pass_obj.valid_until - pass_obj.valid_from).days if pass_obj.valid_from else 30
    if duration <= 0:
        duration = 30

    daily_value = price / duration
    total = round(daily_value * remaining_days, 2)

    return {
        "remaining": remaining_days,
        "unit_price": round(daily_value, 2),
        "total": total,
        "remaining_days": remaining_days,
    }


def get_course_name(db: Session, course_id: str) -> str:
    """获取课程名称，支持逗号分隔多课程ID"""
    if not course_id:
        return ""
    cids = [c.strip() for c in course_id.split(",") if c.strip()]
    names = []
    for cid in cids:
        course = db.query(Course).filter(Course.course_id == cid).first()
        if course:
            names.append(course.name or "")
    return ", ".join(n for n in names if n)


def _card_display_name(card: MembershipCard) -> str:
    """获取会籍卡展示名称，优先 card_name，其次 remark，最后根据数据推断"""
    if card.card_name:
        return card.card_name
    if card.remark and card.remark not in ("-", ""):
        if not card.remark.startswith("来自产品"):
            return card.remark
    ct = (card.card_type or "").strip()
    if ct:
        days = card.duration_days or 0
        if "次卡" in ct:
            total = card.total_classes or 0
            bonus = card.bonus_classes or 0
            base = card.card_name if card.card_name and card.card_name != "会籍卡" else ct
            if total > 0:
                return "{} {}+{}次".format(base, total, bonus) if bonus else "{} {}次".format(base, total)
            return base
        elif "现金卡" in ct or ct == "现金":
            return "现金卡 ¥{:.0f}".format(float(card.face_value or card.price or 0))
        else:
            return "{} {}天".format(ct, days) if days else ct
    # 无 card_type：通过起止日期和价格推断；如有 total_classes 也算次卡
    price = float(card.price or 0)
    if card.total_classes and card.total_classes > 0:
        bonus = card.bonus_classes or 0
        base = card.card_name if card.card_name and card.card_name != "会籍卡" else "次卡"
        return "{} {}+{}次".format(base, card.total_classes, bonus) if bonus else "{} {}次".format(base, card.total_classes)
    if card.end_date and card.start_date:
        actual_days = (card.end_date - card.start_date).days
        if actual_days > 0:
            if actual_days <= 31:    return "月卡 ¥{:.0f}".format(price)
            if actual_days <= 93:    return "季卡 ¥{:.0f}".format(price)
            if actual_days <= 366:   return "年卡 ¥{:.0f}".format(price)
            return "长期卡 ¥{:.0f}".format(price)
    return "会籍卡 ¥{:.0f}".format(price) if price else "会籍卡"


def get_member_asset_detail(db: Session, member_id: str) -> dict:
    """计算单个会员的完整资产残值明细"""
    result = {
        "member_id": member_id,
        "member_name": "",
        "phone": "",
        "card_residual": 0.0,
        "card_detail": [],
        "lesson_residual": 0.0,
        "lesson_detail": [],
        "package_residual": 0.0,
        "package_detail": [],
        "total": 0.0,
    }

    # 跳过无效会员
    if not member_id or member_id.strip() in ("", "-"):
        return result

    member = db.query(Member).filter(Member.member_id == member_id).first()
    if member:
        result["member_name"] = member.name or ""
        result["phone"] = member.phone or ""

    # ── 1. 会籍卡 ──
    cards = db.query(MembershipCard).filter(
        MembershipCard.member_id == member_id,
        MembershipCard.status.in_(["正常", "有效"])
    ).all()
    card_total = 0.0
    for c in cards:
        val = calc_card_residual(c)
        if val > 0:
            card_total += val
            remaining_days = _calc_remaining_days(c.end_date)
            remaining_desc, remaining_count = _card_remaining_count(c)
            result["card_detail"].append({
                "card_id": c.card_id,
                "card_name": _card_display_name(c),
                "card_type": _card_type_label(c),
                "price": float(c.price or 0),
                "face_value": float(c.face_value or 0),
                "consumed": float(c.consumed_amount or 0),
                "residual": round(val, 2),
                "start_date": str(c.start_date) if c.start_date else "",
                "end_date": str(c.end_date) if c.end_date else "",
                "remaining_days": remaining_days,
                "remaining_desc": remaining_desc,
                "remaining_count": remaining_count,
                "total_classes": c.total_classes or 0,
            })
    result["card_residual"] = round(card_total, 2)

    # ── 2. 私教课 ──
    lesson_pkgs = db.query(LessonPackage).filter(
        LessonPackage.member_id == member_id,
        LessonPackage.package_type == "normal",
        LessonPackage.status.in_(["正常", "有效"]),
    ).all()
    lesson_total = 0.0
    for p in lesson_pkgs:
        detail = calc_lesson_package_residual(db, p)
        if detail["total"] > 0:
            lesson_total += detail["total"]
            course_name = p.course_name or get_course_name(db, p.course_id or "")
            result["lesson_detail"].append({
                "package_id": p.package_id,
                "course_name": course_name,
                "total_hours": p.total_hours or 0,
                "used_hours": p.used_hours or 0,
                "remaining_hours": p.remaining_hours or 0,
                "unit_price": detail["unit_price"],
                "residual": detail["total"],
                "valid_from": str(p.valid_from) if p.valid_from else "",
                "valid_until": str(p.valid_until) if p.valid_until else "",
                "remaining_days": detail.get("remaining_days", 0),
            })
    result["lesson_residual"] = round(lesson_total, 2)

    # ── 3. 课程包 + 包月 ──
    group_pkgs = db.query(LessonPackage).filter(
        LessonPackage.member_id == member_id,
        LessonPackage.package_type == "group",
        LessonPackage.status.in_(["正常", "有效"]),
    ).all()
    group_total = 0.0
    for p in group_pkgs:
        detail = calc_lesson_package_residual(db, p)
        if detail["total"] > 0:
            group_total += detail["total"]
            course_name = p.course_name or get_course_name(db, p.course_id or "")
            result["package_detail"].append({
                "package_id": p.package_id,
                "course_name": course_name,
                "total_hours": p.total_hours or 0,
                "used_hours": p.used_hours or 0,
                "remaining_hours": p.remaining_hours or 0,
                "unit_price": detail["unit_price"],
                "residual": detail["total"],
                "valid_from": str(p.valid_from) if p.valid_from else "",
                "valid_until": str(p.valid_until) if p.valid_until else "",
                "remaining_days": detail.get("remaining_days", 0),
            })

    monthly_passes = db.query(MonthlyPass).filter(
        MonthlyPass.member_id == member_id,
        MonthlyPass.status.in_(["正常", "有效"]),
    ).all()
    for mp in monthly_passes:
        detail = calc_monthly_pass_residual(mp)
        if detail["total"] > 0:
            group_total += detail["total"]
            result["package_detail"].append({
                "package_id": mp.pass_id,
                "course_name": mp.pass_name or "包月{}".format(mp.pass_type or ""),
                "total_hours": 0,
                "used_hours": 0,
                "remaining_hours": detail["remaining"],
                "unit_price": detail["unit_price"],
                "residual": detail["total"],
                "valid_from": str(mp.valid_from) if mp.valid_from else "",
                "valid_until": str(mp.valid_until) if mp.valid_until else "",
                "remaining_days": detail.get("remaining_days", 0),
            })

    result["package_residual"] = round(group_total, 2)

    # 总计
    result["total"] = round(card_total + lesson_total + group_total, 2)
    return result


def _status_tag(remaining_days, card_type=""):
    """生成状态标签 HTML"""
    if remaining_days is None:
        return '<span class="text-xs bg-gray-100 text-gray-400 px-2 py-0.5 rounded">未知</span>'
    if remaining_days < 0:
        return '<span class="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">已过期</span>'
    if remaining_days == 0:
        return '<span class="text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded">今日到期</span>'
    if remaining_days <= 7:
        return '<span class="text-xs bg-orange-100 text-orange-600 px-2 py-0.5 rounded">即将到期</span>'
    if remaining_days <= 30:
        return '<span class="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">30天内到期</span>'
    return '<span class="text-xs bg-green-100 text-green-600 px-2 py-0.5 rounded">有效</span>'


def _progress_bar(current, total, color="blue"):
    """生成进度条 HTML"""
    if total <= 0:
        return '<div class="w-full bg-gray-200 rounded-full h-1.5"></div>'
    pct = min(current / total * 100, 100)
    colors = {"blue": "bg-blue-500", "green": "bg-green-500", "orange": "bg-orange-500", "red": "bg-red-500"}
    bar_color = colors.get(color, "bg-blue-500")
    return '<div class="w-full bg-gray-200 rounded-full h-1.5"><div class="{} rounded-full h-1.5" style="width: {}%"></div></div>'.format(bar_color, round(pct, 1))


def build_assets_table(members_data: list) -> str:
    """生成资产残值表格 HTML（含到期/状态列）"""
    if not members_data:
        return '<div class="text-center py-8 text-gray-400">暂无数据</div>'

    trs = ""
    for m in members_data:
        total = m["total"]
        total_str = '¥{:,.2f}'.format(total)
        row_class = "hover:bg-blue-50 cursor-pointer" if total > 0 else "hover:bg-gray-50"

        # 汇总到期天数（取所有资产中最短剩余天数）
        min_days = None
        has_expired = False
        for detail_list in [m.get("card_detail", []), m.get("lesson_detail", []), m.get("package_detail", [])]:
            for item in detail_list:
                d = item.get("remaining_days")
                if d is not None:
                    if d < 0:
                        has_expired = True
                    if min_days is None or d < min_days:
                        min_days = d

        status_html = _status_tag(min_days)
        if has_expired and min_days is not None:
            status_html = '<span class="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded">⚠ 有到期</span>'

        # 资产项数
        item_count = len(m.get("card_detail", [])) + len(m.get("lesson_detail", [])) + len(m.get("package_detail", []))
        count_tag = '<span class="text-xs text-gray-400">{}项</span>'.format(item_count)

        trs += '<tr class="border-b {}" onclick="showMemberDetail(\'{}\')">'.format(row_class, m["member_id"])
        trs += '<td class="px-4 py-3 text-sm text-gray-500">{}</td>'.format(m["member_id"])
        trs += '<td class="px-4 py-3 font-medium text-gray-800">{}</td>'.format(m["member_name"] or "(无名)")
        trs += '<td class="px-4 py-3 text-sm text-gray-500">{}</td>'.format(m["phone"] or "")
        trs += '<td class="px-4 py-3 text-sm">{}</td>'.format('¥{:,.2f} {}'.format(m["card_residual"], count_tag) if m["card_residual"] > 0 else '<span class="text-gray-300">—</span>')
        trs += '<td class="px-4 py-3 text-sm">{}</td>'.format('¥{:,.2f}'.format(m["lesson_residual"]) if m["lesson_residual"] > 0 else '<span class="text-gray-300">—</span>')
        trs += '<td class="px-4 py-3 text-sm">{}</td>'.format('¥{:,.2f}'.format(m["package_residual"]) if m["package_residual"] > 0 else '<span class="text-gray-300">—</span>')
        trs += '<td class="px-4 py-3 text-sm">{}</td>'.format(total_str)
        trs += '<td class="px-4 py-3 text-center">{}</td>'.format(status_html)
        trs += '</tr>'

    table_head = '''<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr>
                <th class="px-4 py-3">编号</th>
                <th class="px-4 py-3">姓名</th>
                <th class="px-4 py-3">手机</th>
                <th class="px-4 py-3">🎫 会籍卡</th>
                <th class="px-4 py-3">🏋️ 私教课</th>
                <th class="px-4 py-3">📦 课程包</th>
                <th class="px-4 py-3">💰 总计</th>
                <th class="px-4 py-3 text-center">状态</th>
            </tr>
        </thead>
        <tbody>'''
    return table_head + "".join(trs) + "</tbody></table>"


def build_summary_cards(data: list) -> str:
    """生成汇总统计卡片"""
    total_people = len(data)
    total_value = sum(m["total"] for m in data)
    card_total = sum(m["card_residual"] for m in data)
    lesson_total = sum(m["lesson_residual"] for m in data)
    pkg_total = sum(m["package_residual"] for m in data)
    max_member = max(data, key=lambda x: x["total"]) if data else None

    avg_value = round(total_value / total_people, 2) if total_people > 0 else 0

    # 资产健康度
    near_expire = sum(1 for m in data if any(
        d.get("remaining_days") is not None and 0 <= d.get("remaining_days", 999) <= 30
        for dl in [m.get("card_detail", []), m.get("lesson_detail", []), m.get("package_detail", [])]
        for d in dl
    ))
    expired = sum(1 for m in data if any(
        d.get("remaining_days") is not None and d.get("remaining_days", 999) < 0
        for dl in [m.get("card_detail", []), m.get("lesson_detail", []), m.get("package_detail", [])]
        for d in dl
    ))

    html = '''
    <div class="grid grid-cols-2 md:grid-cols-6 gap-3">
        <div class="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
            <div class="text-xs text-gray-400 uppercase tracking-wide">查询人数</div>
            <div class="text-2xl font-bold text-gray-800 mt-1">{}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
            <div class="text-xs text-gray-400 uppercase tracking-wide">💰 总残值</div>
            <div class="text-2xl font-bold text-green-600 mt-1">¥{:,.2f}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
            <div class="text-xs text-gray-400 uppercase tracking-wide">人均残值</div>
            <div class="text-2xl font-bold text-blue-600 mt-1">¥{:,.2f}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
            <div class="text-xs text-gray-400 uppercase tracking-wide">会籍卡 / 私教课</div>
            <div class="text-lg font-bold text-gray-800 mt-1">¥{:,.2f} / ¥{:,.2f}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
            <div class="text-xs text-gray-400 uppercase tracking-wide">课程包</div>
            <div class="text-2xl font-bold text-purple-600 mt-1">¥{:,.2f}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
            <div class="text-xs text-gray-400 uppercase tracking-wide">资产健康</div>
            <div class="text-sm font-bold mt-1">
                <span class="{} font-medium">{}</span> 到期
                <span class="{} font-medium ml-1">{}</span> 过期
            </div>
        </div>
    </div>'''.format(
        total_people,
        total_value, avg_value,
        card_total, lesson_total,
        pkg_total,
        "text-orange-600" if near_expire > 0 else "text-gray-400",
        "{}项".format(near_expire) if near_expire > 0 else "无",
        "text-red-600" if expired > 0 else "text-gray-400",
        "{}项".format(expired) if expired > 0 else "无"
    )

    # 最高资产会员
    if max_member and max_member["total"] > 0:
        html += '''
    <div class="mt-2 text-xs text-gray-400">
        资产最高：<span class="font-medium text-gray-600">{}</span>
        ¥{:,.2f}
    </div>'''.format(max_member["member_name"], max_member["total"])

    return html


# ══════════════════════════════════════════════════
# API 端点
# ══════════════════════════════════════════════════

@router.get("/table", response_class=HTMLResponse)
def asset_table(
    q: str = Query(""),
    show_all: bool = Query(False, alias="showAll"),
    db: Session = Depends(get_db),
):
    """资产残值表格 HTML 片段（搜索 + 表格）"""
    # 查询会员 — 跳过脏数据
    member_query = db.query(Member).filter(Member.member_id != None, Member.member_id != "", Member.member_id != "-")
    kw = q.strip()
    if kw:
        member_query = member_query.filter(
            Member.name.contains(kw)
            | Member.phone.contains(kw)
            | Member.member_id.contains(kw)
        )

    # 只查有资产记录的会员
    if not show_all and not kw:
        member_ids_with_cards = {
            r[0] for r in db.query(MembershipCard.member_id).filter(
                MembershipCard.status.in_(["正常", "有效"]),
                MembershipCard.member_id != None,
                MembershipCard.member_id != "",
                MembershipCard.member_id != "-",
            ).all()
        }
        member_ids_with_pkgs = {
            r[0] for r in db.query(LessonPackage.member_id).filter(
                LessonPackage.status.in_(["正常", "有效"]),
                LessonPackage.member_id != None,
                LessonPackage.member_id != "",
                LessonPackage.member_id != "-",
            ).all()
        }
        member_ids_with_mp = {
            r[0] for r in db.query(MonthlyPass.member_id).filter(
                MonthlyPass.status.in_(["正常", "有效"]),
                MonthlyPass.member_id != None,
                MonthlyPass.member_id != "",
                MonthlyPass.member_id != "-",
            ).all()
        }
        ids_with_assets = member_ids_with_cards | member_ids_with_pkgs | member_ids_with_mp
        if ids_with_assets:
            member_query = member_query.filter(Member.member_id.in_(ids_with_assets))

    members = member_query.order_by(Member.id.desc()).limit(200).all()

    # 计算每个会员的资产残值
    results = []
    for m in members:
        detail = get_member_asset_detail(db, m.member_id)
        results.append(detail)

    # 按总残值降序排列
    results.sort(key=lambda x: x["total"], reverse=True)

    # 汇总卡片
    summary = build_summary_cards(results)

    # 表格
    table = build_assets_table(results)

    return summary + '<div class="mt-4" id="assetsTableWrap">' + table + '</div>'


@router.get("/member/{member_id}/detail")
def member_asset_detail(member_id: str, db: Session = Depends(get_db)):
    """单个会员的资产残值明细 JSON"""
    detail = get_member_asset_detail(db, member_id)
    return detail


@router.get("/export")
def export_assets(
    q: str = Query(""),
    show_all: bool = Query(False, alias="showAll"),
    db: Session = Depends(get_db),
):
    """导出资产残值为 CSV"""
    import io
    import csv

    member_query = db.query(Member).filter(Member.member_id != None, Member.member_id != "", Member.member_id != "-")
    kw = q.strip()
    if kw:
        member_query = member_query.filter(
            Member.name.contains(kw)
            | Member.phone.contains(kw)
            | Member.member_id.contains(kw)
        )

    if not show_all and not kw:
        member_ids_with_cards = {
            r[0] for r in db.query(MembershipCard.member_id).filter(
                MembershipCard.status.in_(["正常", "有效"]),
                MembershipCard.member_id != None,
                MembershipCard.member_id != "",
                MembershipCard.member_id != "-",
            ).all()
        }
        member_ids_with_pkgs = {
            r[0] for r in db.query(LessonPackage.member_id).filter(
                LessonPackage.status.in_(["正常", "有效"]),
                LessonPackage.member_id != None,
                LessonPackage.member_id != "",
                LessonPackage.member_id != "-",
            ).all()
        }
        member_ids_with_mp = {r[0] for r in db.query(MonthlyPass.member_id).filter(
            MonthlyPass.status.in_(["正常", "有效"]),
            MonthlyPass.member_id != None,
            MonthlyPass.member_id != "",
            MonthlyPass.member_id != "-",
        ).all()}
        ids_with_assets = member_ids_with_cards | member_ids_with_pkgs | member_ids_with_mp
        if ids_with_assets:
            member_query = member_query.filter(Member.member_id.in_(ids_with_assets))

    members = member_query.order_by(Member.id.desc()).limit(200).all()

    results = []
    for m in members:
        detail = get_member_asset_detail(db, m.member_id)
        results.append(detail)

    results.sort(key=lambda x: x["total"], reverse=True)

    output = io.StringIO()
    output.write('\ufeff')  # BOM for Excel
    writer = csv.writer(output)
    writer.writerow([
        "会员编号", "姓名", "手机号",
        "会籍卡残值", "会籍卡明细",
        "私教课残值", "私教课明细",
        "课程包残值", "课程包明细",
        "总残值", "资产状态"
    ])

    for r in results:
        card_detail_str = "; ".join(
            '{}: ¥{:.2f} (到期{})'.format(c["card_type"], c["residual"], c["end_date"])
            for c in r.get("card_detail", [])
        ) if r.get("card_detail") else ""
        lesson_detail_str = "; ".join(
            '{}: ¥{:.2f} (已用{}/共{}节, 到期{})'.format(
                l["course_name"], l["residual"], l["used_hours"], l["total_hours"], l["valid_until"])
            for l in r.get("lesson_detail", [])
        ) if r.get("lesson_detail") else ""
        pkg_detail_str = "; ".join(
            '{}: ¥{:.2f} (剩余{}次, 到期{})'.format(
                p["course_name"], p["residual"], p["remaining_hours"], p["valid_until"])
            for p in r.get("package_detail", [])
        ) if r.get("package_detail") else ""

        # 状态判断
        min_days = None
        for dl in [r.get("card_detail", []), r.get("lesson_detail", []), r.get("package_detail", [])]:
            for d in dl:
                days = d.get("remaining_days")
                if days is not None and (min_days is None or days < min_days):
                    min_days = days
        status_label = "正常"
        if min_days is not None and min_days < 0:
            status_label = "已过期"
        elif min_days is not None and min_days <= 7:
            status_label = "即将到期({}天)".format(min_days)

        writer.writerow([
            r["member_id"], r["member_name"], r["phone"],
            r["card_residual"], card_detail_str,
            r["lesson_residual"], lesson_detail_str,
            r["package_residual"], pkg_detail_str,
            r["total"], status_label,
        ])

    csv_content = output.getvalue()
    filename = "assets_{}.csv".format(date.today().isoformat())
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=\"{}\"".format(filename)
        },
    )
