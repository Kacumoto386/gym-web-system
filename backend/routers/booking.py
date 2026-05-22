# -*- coding: utf-8 -*-
"""
预约管理 & 课程签到 API 路由
V3.2.1 - 完整的预约管理
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Form
from fastapi.responses import HTMLResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import date, datetime
from backend.database import get_db
from backend.models.models import Booking, ClassRecord, LessonPackage, Staff, Member, Course

router = APIRouter(prefix="/api/booking", tags=["预约管理"])


# ══════════════════════════════════════════
# 教练列表（用于新增预约表单）
# ══════════════════════════════════════════

@router.get("/coaches")
def get_coaches(db: Session = Depends(get_db)):
    coach_staffs = db.query(Staff).filter(
        Staff.status == "在职",
        Staff.position.contains("教练"),
    ).order_by(Staff.name).all()
    return [
        {"staff_id": s.staff_id, "name": s.name, "position": s.position}
        for s in coach_staffs
    ]


# ══════════════════════════════════════════
# 课程列表（用于新增预约表单）
# ══════════════════════════════════════════

@router.get("/courses")
def get_courses(db: Session = Depends(get_db)):
    courses = db.query(Course).filter(Course.status == "上架").order_by(Course.name).all()
    return [
        {"course_id": c.course_id, "name": c.name, "duration": getattr(c, 'duration', 60) or 60}
        for c in courses
    ]


# ══════════════════════════════════════════
# 会员已购课程列表
# ══════════════════════════════════════════

@router.get("/member-courses")
def get_member_courses(member_id: str = Query(""), db: Session = Depends(get_db)):
    if not member_id:
        return {"courses": []}

    today = date.today()
    pkgs = db.query(LessonPackage).filter(
        LessonPackage.member_id == member_id,
        LessonPackage.status == "正常",
        LessonPackage.remaining_hours > 0,
    ).all()

    # 按课程分组汇总
    course_map = {}
    for p in pkgs:
        course_ids = []
        if p.included_courses:
            course_ids = [c.strip() for c in p.included_courses.split(",") if c.strip()]
        elif p.course_id:
            course_ids = [p.course_id]

        for cid in course_ids:
            if cid not in course_map:
                course_map[cid] = {
                    "course_name": p.course_name or "",
                    "total_remaining": 0,
                    "has_valid": False,
                }
            course_map[cid]["total_remaining"] += p.remaining_hours
            if p.valid_until is None or p.valid_until >= today:
                course_map[cid]["has_valid"] = True

    courses = []
    for cid, info in course_map.items():
        if info["has_valid"]:
            courses.append({
                "course_id": cid,
                "course_name": info["course_name"],
                "total_remaining": info["total_remaining"],
                "expired": False,
            })
        else:
            courses.append({
                "course_id": cid,
                "course_name": info["course_name"],
                "total_remaining": info["total_remaining"],
                "expired": True,
            })

    courses.sort(key=lambda c: c["course_name"])
    return {"courses": courses}


# ══════════════════════════════════════════
# 预约列表（分页）
# ══════════════════════════════════════════

@router.get("/list")
def booking_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    date_from: str = Query(""),
    date_to: str = Query(""),
    date_str: str = Query(""),
    status: str = Query(""),
    member_id: str = Query(""),
    db: Session = Depends(get_db),
):
    q = db.query(Booking)
    if date_str:
        try:
            bd = date.fromisoformat(date_str)
            q = q.filter(Booking.booking_date == bd)
        except ValueError:
            pass
    if date_from:
        try:
            q = q.filter(Booking.booking_date >= date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(Booking.booking_date <= date.fromisoformat(date_to))
        except ValueError:
            pass
    if status:
        q = q.filter(Booking.status == status)
    if member_id:
        q = q.filter(Booking.member_id == member_id)
    total = q.count()
    items = q.order_by(Booking.booking_date.desc(), Booking.start_time.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "booking_id": b.booking_id,
                "booking_date": str(b.booking_date) if b.booking_date else "",
                "start_time": b.start_time or "",
                "end_time": b.end_time or "",
                "member_id": b.member_id,
                "member_name": b.member_name or "",
                "member_phone": b.member_phone or "",
                "course_id": b.course_id or "",
                "course_name": b.course_name or "",
                "coach_id": b.coach_id or "",
                "coach_name": b.coach_name or "",
                "location": b.location or "",
                "status": b.status or "已预约",
                "created_at": str(b.created_at) if b.created_at else "",
            }
            for b in items
        ],
    }


# ══════════════════════════════════════════
# 预约表格 HTML 片段（HTMX）
# ══════════════════════════════════════════

@router.get("/table", response_class=HTMLResponse)
def booking_table(
    date_from: str = Query(""),
    date_to: str = Query(""),
    date_str: str = Query(""),
    status: str = Query(""),
    db: Session = Depends(get_db),
):
    q = db.query(Booking)
    if date_from:
        try:
            q = q.filter(Booking.booking_date >= date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(Booking.booking_date <= date.fromisoformat(date_to))
        except ValueError:
            pass
    if not date_from and not date_to and date_str:
        try:
            bd = date.fromisoformat(date_str)
            q = q.filter(Booking.booking_date == bd)
        except ValueError:
            pass
    if status:
        q = q.filter(Booking.status == status)
    bookings = q.order_by(Booking.start_time, Booking.member_name).all()

    if not bookings:
        return HTMLResponse(content='<div class="text-center py-12 text-gray-400 text-sm">暂无预约记录</div>')

    rows = ""
    status_badges = {
        "已预约": '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">🟢 已预约</span>',
        "已签到": '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">🟡 已签到</span>',
        "已完成": '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">🔵 已完成</span>',
        "已取消": '<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">⛔ 已取消</span>',
    }

    for b in bookings:
        badge = status_badges.get(b.status, b.status or "未知")
        actions = ""
        if b.status == "已预约":
            actions = f"""
                <button onclick="bookingCheckin('{b.booking_id}')" class="text-xs px-2 py-1 bg-yellow-500 text-white rounded hover:bg-yellow-600">签到</button>
                <button onclick="cancelBooking('{b.booking_id}')" class="text-xs px-2 py-1 bg-gray-200 text-gray-600 rounded hover:bg-gray-300">取消</button>
            """
        elif b.status == "已签到":
            actions = f"""
                <button onclick="completeBooking('{b.booking_id}')" class="text-xs px-2 py-1 bg-blue-500 text-white rounded hover:bg-blue-600">完成</button>
            """

        rows += f"""
        <tr class="border-b border-gray-50 hover:bg-gray-50">
            <td class="py-2.5 px-3 text-sm">{b.booking_date}</td>
            <td class="py-2.5 px-3 text-sm">{b.start_time or '-'}</td>
            <td class="py-2.5 px-3 text-sm">{b.member_name or '-'}</td>
            <td class="py-2.5 px-3 text-sm">{b.course_name or '-'}</td>
            <td class="py-2.5 px-3 text-sm">{b.coach_name or '-'}</td>
            <td class="py-2.5 px-3">{badge}</td>
            <td class="py-2.5 px-3"><div class="flex gap-1">{actions}</div></td>
        </tr>"""

    html = f"""
    <div class="overflow-x-auto">
        <table class="w-full text-sm">
            <thead>
                <tr class="bg-gray-50 text-gray-500 text-xs uppercase tracking-wider">
                    <th class="py-2.5 px-3 text-left">日期</th>
                    <th class="py-2.5 px-3 text-left">时间</th>
                    <th class="py-2.5 px-3 text-left">会员</th>
                    <th class="py-2.5 px-3 text-left">课程</th>
                    <th class="py-2.5 px-3 text-left">教练</th>
                    <th class="py-2.5 px-3 text-left">状态</th>
                    <th class="py-2.5 px-3 text-left">操作</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """
    return HTMLResponse(content=html)


# ══════════════════════════════════════════
# 新增预约
# ══════════════════════════════════════════

@router.post("/create")
def create_booking(
    booking_date: str = Form(...),
    start_time: str = Form(""),
    end_time: str = Form(""),
    member_id: str = Form(""),
    member_name: str = Form(""),
    member_phone: str = Form(""),
    course_id: str = Form(""),
    course_name: str = Form(""),
    coach_id: str = Form(""),
    coach_name: str = Form(""),
    location: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        b_date = date.fromisoformat(booking_date)
    except (ValueError, TypeError):
        raise HTTPException(400, "预约日期格式错误")

    # 冲突检测
    if coach_id and start_time:
        conflict = db.query(Booking).filter(
            Booking.booking_date == b_date,
            Booking.coach_id == coach_id,
            Booking.start_time == start_time,
            Booking.status.in_(["已预约", "已签到"]),
        ).first()
        if conflict:
            raise HTTPException(400, f"该教练在 {booking_date} {start_time} 已有预约（会员：{conflict.member_name}）")

    # 购买校验
    today = date.today()
    pkgs = db.query(LessonPackage).filter(
        LessonPackage.member_id == member_id,
        LessonPackage.status == "正常",
        LessonPackage.remaining_hours > 0,
        or_(
            LessonPackage.course_id == course_id,
            LessonPackage.included_courses.contains(course_id),
        ),
    ).all()
    valid_pkgs = [p for p in pkgs if p.valid_until is None or p.valid_until >= today]
    if not valid_pkgs:
        raise HTTPException(400, f"该会员未购买「{course_name}」或课程包已过期/无剩余课时")

    from backend.routers.auto_num import generate_id
    booking_id = generate_id(db, Booking, "booking_id", prefix="BK")

    booking = Booking(
        booking_id=booking_id,
        booking_date=b_date,
        start_time=start_time,
        end_time=end_time,
        member_id=member_id,
        member_name=member_name,
        member_phone=member_phone,
        course_id=course_id,
        course_name=course_name,
        coach_id=coach_id,
        coach_name=coach_name,
        location=location,
        status="已预约",
    )
    db.add(booking)
    db.commit()
    return {"success": True, "booking_id": booking_id, "message": f"预约成功（{member_name} - {course_name}）"}


# ══════════════════════════════════════════
# 编辑预约
# ══════════════════════════════════════════

@router.post("/{booking_id}/update")
def update_booking(
    booking_id: str,
    booking_date: str = Form(""),
    start_time: str = Form(""),
    end_time: str = Form(""),
    member_id: str = Form(""),
    member_name: str = Form(""),
    member_phone: str = Form(""),
    course_id: str = Form(""),
    course_name: str = Form(""),
    coach_id: str = Form(""),
    coach_name: str = Form(""),
    location: str = Form(""),
    status: str = Form(""),
    db: Session = Depends(get_db),
):
    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        raise HTTPException(404, "预约记录不存在")

    if booking_date:
        try:
            booking.booking_date = date.fromisoformat(booking_date)
        except ValueError:
            pass
    if start_time:
        booking.start_time = start_time
    if end_time:
        booking.end_time = end_time
    if member_id:
        booking.member_id = member_id
    if member_name:
        booking.member_name = member_name
    if member_phone:
        booking.member_phone = member_phone
    if course_id:
        booking.course_id = course_id
    if course_name:
        booking.course_name = course_name
    if coach_id:
        booking.coach_id = coach_id
    if coach_name:
        booking.coach_name = coach_name
    if location:
        booking.location = location
    if status:
        booking.status = status

    db.commit()
    return {"success": True, "message": "预约已更新"}


# ══════════════════════════════════════════
# 预约签到（转为进场记录+上课记录）
# ══════════════════════════════════════════

@router.post("/{booking_id}/checkin")
def booking_checkin(booking_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        raise HTTPException(404, "预约记录不存在")
    if booking.status != "已预约":
        raise HTTPException(400, f"当前状态为「{booking.status}」，无法签到")

    booking.status = "已签到"
    db.commit()
    return {"status": "ok", "message": f"{booking.member_name} 签到成功"}


# ══════════════════════════════════════════
# 取消预约
# ══════════════════════════════════════════

@router.post("/{booking_id}/cancel")
def cancel_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        raise HTTPException(404, "预约记录不存在")
    if booking.status == "已取消":
        raise HTTPException(400, "该预约已取消")
    booking.status = "已取消"
    db.commit()
    return {"success": True, "message": "预约已取消"}


# ══════════════════════════════════════════
# 完成预约
# ══════════════════════════════════════════

@router.post("/{booking_id}/complete")
def complete_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        raise HTTPException(404, "预约记录不存在")
    if booking.status != "已签到":
        raise HTTPException(400, f"当前状态为「{booking.status}」，无法标记完成")
    booking.status = "已完成"
    db.commit()
    return {"success": True, "message": "预约已完成"}


# ══════════════════════════════════════════
# 预约详情（JSON，编辑弹窗用）
# ══════════════════════════════════════════

@router.get("/{booking_id}")
def get_booking(booking_id: str, db: Session = Depends(get_db)):
    b = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not b:
        raise HTTPException(404, "预约记录不存在")
    return {
        "booking_id": b.booking_id,
        "booking_date": str(b.booking_date) if b.booking_date else "",
        "start_time": b.start_time or "",
        "end_time": b.end_time or "",
        "member_id": b.member_id,
        "member_name": b.member_name or "",
        "member_phone": b.member_phone or "",
        "course_id": b.course_id or "",
        "course_name": b.course_name or "",
        "coach_id": b.coach_id or "",
        "coach_name": b.coach_name or "",
        "location": b.location or "",
        "status": b.status or "",
    }


# ══════════════════════════════════════════
# 今日预约 HTML 片段（首页用）
# ══════════════════════════════════════════

@router.get("/today", response_class=HTMLResponse)
def today_bookings_html(db: Session = Depends(get_db)):
    today = date.today()
    bookings = db.query(Booking).filter(
        Booking.booking_date == today,
        Booking.status.in_(["已预约", "已签到"]),
    ).order_by(Booking.start_time).all()

    if not bookings:
        return HTMLResponse(content='<div class="text-center py-6 text-gray-400 text-xs">今日无待处理预约</div>')

    items = ""
    for b in bookings:
        status_dot = "🟢" if b.status == "已预约" else "🟡"
        action_btn = ""
        if b.status == "已预约":
            action_btn = f'<button onclick="homeCheckinBooking(\'{b.booking_id}\')" class="text-xs px-2 py-0.5 bg-yellow-500 text-white rounded hover:bg-yellow-600">签到</button>'

        items += f"""
        <div class="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
            <div class="flex items-center gap-2 text-sm">
                <span>{status_dot}</span>
                <span class="font-medium">{b.member_name or '-'}</span>
                <span class="text-gray-400">{b.start_time or ''}</span>
                <span class="text-gray-400">{b.course_name or ''}</span>
            </div>
            <div>{action_btn}</div>
        </div>"""

    return HTMLResponse(content=f"""
    <div class="space-y-0">
        <div class="text-xs text-gray-400 mb-2">今日待处理 ({len(bookings)})</div>
        {items}
    </div>
    """)
