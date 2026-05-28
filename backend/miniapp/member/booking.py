"""会员小程序 · 预约管理"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from backend.database import get_db
from backend.models.models import Booking, Staff
from backend.miniapp.common import success, MiniAppException
from backend.miniapp.auth import verify_member_token
from backend.services.id_gen import generate_id

router = APIRouter(prefix="/bookings", tags=["会员-预约"])


class CreateBookingRequest(BaseModel):
    coach_id: str
    booking_date: str
    start_time: str
    end_time: str
    remark: Optional[str] = ""


@router.get("")
async def list_bookings(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """我的预约列表。"""
    member_id = member.get("sub")
    query = (
        db.query(Booking)
        .filter(Booking.member_id == member_id)
        .order_by(Booking.booking_date.desc())
    )
    if status:
        query = query.filter(Booking.status == status)

    records = query.all()
    return success(data=[
        {
            "booking_id": b.booking_id,
            "coach_name": b.staff_name,
            "booking_date": b.booking_date,
            "start_time": b.start_time,
            "end_time": b.end_time,
            "status": b.status,
            "remark": b.remark or "",
        }
        for b in records
    ])


@router.get("/coaches")
async def list_coaches(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """可预约教练列表。"""
    coaches = db.query(Staff).filter(Staff.role == "教练").all()
    return success(data=[
        {
            "staff_id": c.staff_id,
            "name": c.name,
        }
        for c in coaches
    ])


@router.post("")
async def create_booking(
    body: CreateBookingRequest,
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """创建预约。"""
    member_id = member.get("sub")
    from backend.models.models import Member
    member_info = db.query(Member).filter(Member.member_id == member_id).first()

    coach = db.query(Staff).filter(Staff.staff_id == body.coach_id).first()
    if not coach:
        raise MiniAppException(2002, "教练不存在")

    # 检查时间冲突
    conflict = (
        db.query(Booking)
        .filter(
            Booking.staff_id == body.coach_id,
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
        member_id=member_id,
        member_name=member_info.name if member_info else "",
        staff_id=body.coach_id,
        staff_name=coach.name,
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
    member: dict = Depends(verify_member_token),
):
    """取消预约。"""
    booking = (
        db.query(Booking)
        .filter(
            Booking.booking_id == booking_id,
            Booking.member_id == member.get("sub"),
        )
        .first()
    )
    if not booking:
        raise MiniAppException(2002, "预约不存在")

    booking.status = "cancelled"
    db.commit()
    return success(message="预约已取消")
