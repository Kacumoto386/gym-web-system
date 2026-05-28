"""员工小程序 · 课程预约"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from backend.database import get_db
from backend.models.models import Booking, Staff, Member
from backend.miniapp.common import success, MiniAppException
from backend.miniapp.auth import verify_staff_token
from backend.services.id_gen import generate_id

router = APIRouter(prefix="/bookings", tags=["员工-预约"])


class CreateBookingRequest(BaseModel):
    member_id: str
    coach_id: str
    booking_date: str
    start_time: str
    end_time: str
    remark: Optional[str] = ""


@router.get("/coaches")
async def list_coaches(
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """可预约教练列表。"""
    coaches = db.query(Staff).filter(Staff.position == "教练").all()
    return success(data=[
        {
            "staff_id": c.staff_id,
            "name": c.name,
            "phone": c.phone,
        }
        for c in coaches
    ])


@router.get("/slots")
async def get_coach_slots(
    coach_id: str = Query(...),
    date: str = Query(...),
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """教练可约时段（查询已有预约，返回空闲时段）。"""
    bookings = (
        db.query(Booking)
        .filter(
            Booking.coach_id == coach_id,
            Booking.booking_date == date,
            Booking.status.in_(["confirmed", "pending"]),
        )
        .all()
    )

    # 返回已占用时段，由小程序端计算空闲时段
    return success(data={
        "booked_slots": [
            {
                "start_time": b.start_time,
                "end_time": b.end_time,
                "member_name": b.member_name,
            }
            for b in bookings
        ]
    })


@router.post("")
async def create_booking(
    body: CreateBookingRequest,
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """创建预约。"""
    member = db.query(Member).filter(Member.member_id == body.member_id).first()
    if not member:
        raise MiniAppException(2002, "会员不存在")

    coach = db.query(Staff).filter(Staff.staff_id == body.coach_id).first()
    if not coach:
        raise MiniAppException(2002, "教练不存在")

    # 检查时间冲突
    conflict = (
        db.query(Booking)
        .filter(
            Booking.coach_id == body.coach_id,
            Booking.booking_date == body.booking_date,
            Booking.status.in_(["confirmed", "pending"]),
            Booking.start_time < body.end_time,
            Booking.end_time > body.start_time,
        )
        .first()
    )
    if conflict:
        raise MiniAppException(3001, "该时段已被预约")

    booking_id = generate_id("BK", db, Booking.booking_id)
    booking = Booking(
        booking_id=booking_id,
        member_id=body.member_id,
        member_name=member.name,
        coach_id=body.coach_id,
        coach_name=coach.name,
        booking_date=body.booking_date,
        start_time=body.start_time,
        end_time=body.end_time,
        status="confirmed",
        remark=body.remark,
    )
    db.add(booking)
    db.commit()

    return success(data={
        "booking_id": booking_id,
        "message": "预约成功",
    })


@router.put("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: str,
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """取消预约。"""
    booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
    if not booking:
        raise MiniAppException(2002, "预约不存在")

    booking.status = "cancelled"
    db.commit()

    return success(message="预约已取消")
