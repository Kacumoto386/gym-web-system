# -*- coding: utf-8 -*-
"""
教练排班日历化 API 路由 + HTMX HTML 片段端点
V3.1.5 — 基于 Booking 表的月历视图
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timedelta
import calendar
from backend.database import get_db
from backend.models.models import Booking, Staff

router = APIRouter(prefix="/api/schedule", tags=["教练排班"])


# ═══════════════════════════════════════════
# 月历数据 API
# ═══════════════════════════════════════════

@router.get("/monthly")
def get_monthly_schedule(
    year: int = Query(0),
    month: int = Query(0),
    coach_id: str = Query(""),
    db: Session = Depends(get_db),
):
    """获取指定年月 + 教练的排班数据"""
    today = date.today()
    year = year or today.year
    month = month or today.month

    query = db.query(Booking).filter(
        func.extract("year", Booking.booking_date) == year,
        func.extract("month", Booking.booking_date) == month,
    )

    if coach_id:
        query = query.filter(Booking.coach_id == coach_id)

    bookings = query.order_by(Booking.booking_date, Booking.start_time).all()

    # 按日期分组
    day_map = {}
    for b in bookings:
        d = str(b.booking_date)
        if d not in day_map:
            day_map[d] = []
        day_map[d].append({
            "booking_id": b.booking_id,
            "start_time": b.start_time or "",
            "end_time": b.end_time or "",
            "member_name": b.member_name or "",
            "course_name": b.course_name or "",
            "coach_id": b.coach_id or "",
            "coach_name": b.coach_name or "",
            "status": b.status or "已预约",
            "location": b.location or "",
        })

    # 构建月历数据
    _, days_in_month = calendar.monthrange(year, month)

    days = []
    for d in range(1, days_in_month + 1):
        date_str = f"{year}-{month:02d}-{d:02d}"
        dt = date(year, month, d)
        is_today = (dt == today)
        day_bookings = day_map.get(date_str, [])
        status_counts = {}
        for bk in day_bookings:
            s = bk["status"]
            status_counts[s] = status_counts.get(s, 0) + 1
        days.append({
            "date": date_str,
            "day": d,
            "weekday": dt.weekday(),
            "is_today": is_today,
            "is_past": dt < today,
            "bookings": day_bookings,
            "count": len(day_bookings),
            "status_counts": status_counts,
        })

    # 教练列表
    coaches = db.query(Staff).filter(
        (Staff.status == "在职") | (Staff.status == "")
    ).order_by(Staff.name).all()

    return {
        "year": year,
        "month": month,
        "days": days,
        "coaches": [
            {"staff_id": s.staff_id, "name": s.name, "position": s.position or ""}
            for s in coaches
        ],
        "total_bookings": len(bookings),
    }


@router.get("/calendar", response_class=HTMLResponse)
def calendar_html(
    year: int = Query(0),
    month: int = Query(0),
    coach_id: str = Query(""),
    db: Session = Depends(get_db),
):
    """月历视图 HTML 片段"""
    data = get_monthly_schedule(year, month, coach_id, db)
    year, month = data["year"], data["month"]

    # 星期头
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]

    # 日历第一天的偏移
    first_day = date(year, month, 1)
    start_weekday = first_day.weekday()  # 0=周一

    # 构建网格
    days = data["days"]
    total_cells = start_weekday + len(days)
    rows_needed = (total_cells + 6) // 7

    cells_html = ""

    # 填充空白
    cell_idx = 0
    for _ in range(start_weekday):
        cells_html += '<td class="p-1"></td>'
        cell_idx += 1

    for day_data in days:
        d = day_data["day"]
        count = day_data["count"]
        is_today = day_data["is_today"]
        is_past = day_data["is_past"]

        # 状态圆点
        status_dots = ""
        sc = day_data["status_counts"]
        if sc.get("已完成", 0) > 0:
            status_dots += "🔵"
        if sc.get("已签到", 0) > 0:
            status_dots += "🟡"
        if sc.get("已预约", 0) > 0:
            status_dots += "🟢"
        if sc.get("已取消", 0) > 0:
            status_dots += "⚪"

        # 当天/非当天样式
        day_cls = "bg-blue-50 border-blue-300" if is_today else ""
        if is_past:
            day_cls += " opacity-60"

        cells_html += f'''<td class="p-0.5 align-top {day_cls}">
            <div class="min-h-[60px] p-1 rounded cursor-pointer hover:bg-gray-50"
                 onclick="showDayDetail('{day_data["date"]}')">
                <div class="text-xs font-medium {'text-blue-600' if is_today else 'text-gray-700'}">{d}</div>
                <div class="text-xs text-gray-400">{status_dots}</div>
                <div class="text-xs text-gray-500 mt-0.5">{f"{count}节" if count else ""}</div>
            </div>
        </td>'''

        cell_idx += 1
        if cell_idx % 7 == 0:
            cells_html += '</tr><tr>'

    # 补全最后一行
    while cell_idx % 7 != 0:
        cells_html += '<td class="p-1"></td>'
        cell_idx += 1

    html = f'''
    <div class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table class="w-full text-sm">
            <thead>
                <tr class="bg-gray-50">
                    {"".join(f'<th class="px-1 py-2 text-xs text-gray-500 font-medium text-center">{w}</th>' for w in weekdays)}
                </tr>
            </thead>
            <tbody>
                <tr>
                    {cells_html}
                </tr>
            </tbody>
        </table>
    </div>
    '''
    return HTMLResponse(content=html)


@router.get("/stats", response_class=HTMLResponse)
def calendar_stats(
    year: int = Query(0),
    month: int = Query(0),
    coach_id: str = Query(""),
    db: Session = Depends(get_db),
):
    """月统计摘要 HTML 片段"""
    data = get_monthly_schedule(year, month, coach_id, db)
    bookings = []
    for day in data["days"]:
        bookings.extend(day["bookings"])

    total = len(bookings)
    booked = sum(1 for b in bookings if b["status"] == "已预约")
    signed = sum(1 for b in bookings if b["status"] == "已签到")
    completed = sum(1 for b in bookings if b["status"] == "已完成")
    days_with_class = sum(1 for day in data["days"] if day["count"] > 0)

    html = f'''
    <div class="grid grid-cols-4 gap-3">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-3 text-center">
            <div class="text-xs text-gray-400 mb-1">月度总课节</div>
            <div class="text-xl font-semibold text-gray-800">{total}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-3 text-center">
            <div class="text-xs text-gray-400 mb-1">有课天数</div>
            <div class="text-xl font-semibold text-blue-600">{days_with_class}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-3 text-center">
            <div class="text-xs text-gray-400 mb-1">待签到</div>
            <div class="text-xl font-semibold text-yellow-600">{booked}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-3 text-center">
            <div class="text-xs text-gray-400 mb-1">已完成</div>
            <div class="text-xl font-semibold text-green-600">{completed}</div>
        </div>
    </div>
    '''
    return HTMLResponse(content=html)


@router.get("/day-detail", response_class=HTMLResponse)
def day_detail_html(
    date_str: str = Query(""),
    coach_id: str = Query(""),
    db: Session = Depends(get_db),
):
    """某天的预约详情 HTML 片段"""
    from datetime import date
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        return HTMLResponse(content='<div class="text-center py-4 text-gray-400">日期格式错误</div>')

    query = db.query(Booking).filter(Booking.booking_date == d)
    if coach_id:
        query = query.filter(Booking.coach_id == coach_id)
    bookings = query.order_by(Booking.start_time).all()

    if not bookings:
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[d.weekday()]
        return HTMLResponse(content=f'''
            <div class="text-center py-8 text-gray-400">
                <div class="text-sm font-medium">{d} {weekday}</div>
                当天无排课
            </div>
        ''')

    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday = weekday_names[d.weekday()]

    rows = ""
    for b in bookings:
        status_cls = {
            "已预约": "bg-yellow-100 text-yellow-700",
            "已签到": "bg-green-100 text-green-700",
            "已完成": "bg-blue-100 text-blue-700",
            "已取消": "bg-gray-100 text-gray-500",
        }.get(b.status, "bg-gray-100 text-gray-700")

        time_range = f"{b.start_time or '--'}"
        if b.end_time:
            time_range += f" - {b.end_time}"

        rows += f'''<tr class="hover:bg-gray-50 border-b">
            <td class="px-3 py-2.5 text-sm text-gray-500">{time_range}</td>
            <td class="px-3 py-2.5 text-sm font-medium">{b.member_name or ''}</td>
            <td class="px-3 py-2.5 text-sm text-gray-600">{b.course_name or ''}</td>
            <td class="px-3 py-2.5 text-sm">{b.coach_name or ''}</td>
            <td class="px-3 py-2.5"><span class="px-2 py-0.5 rounded text-xs {status_cls}">{b.status or ''}</span></td>
        </tr>'''

    html = f'''
    <div class="mt-4 bg-white rounded-xl shadow-sm border border-gray-100">
        <div class="px-4 py-3 border-b border-gray-100 flex justify-between items-center">
            <span class="text-sm font-medium text-gray-700">{d} {weekday}</span>
            <span class="text-xs text-gray-400">{len(bookings)} 节课程</span>
        </div>
        <table class="w-full">
            <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
                <tr><th class="px-3 py-2">时间</th><th class="px-3 py-2">会员</th><th class="px-3 py-2">课程</th><th class="px-3 py-2">教练</th><th class="px-3 py-2">状态</th></tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    '''
    return HTMLResponse(content=html)


@router.get("/coach-list")
def coach_list(db: Session = Depends(get_db)):
    """获取教练列表（所有有预约记录的在职员工）"""
    # 先查所有有预约记录的教练
    coach_ids = db.query(Booking.coach_id).distinct().all()
    coach_ids = [c[0] for c in coach_ids if c[0]]

    # 加上所有在职员工
    staffs = db.query(Staff).filter(
        (Staff.status == "在职") | (Staff.status == "")
    ).order_by(Staff.name).all()

    result = [{"staff_id": "", "name": "全部教练"}]
    for s in staffs:
        result.append({"staff_id": s.staff_id, "name": s.name, "position": s.position or ""})
    return result
