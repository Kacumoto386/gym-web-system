"""员工小程序 · 扫码核销"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

from backend.database import get_db
from backend.models.models import Checkin, Member, MembershipCard
from backend.miniapp.common import success, MiniAppException
from backend.miniapp.auth import verify_staff_token
from backend.services.id_gen import generate_id

router = APIRouter(prefix="/checkin", tags=["员工-核销"])


class ScanCheckinRequest(BaseModel):
    member_id: Optional[str] = ""
    phone: Optional[str] = ""
    consume_type: str  # 次卡扣次 / 储值扣款 / 期限卡签到 / 现金卡扣费 / 无卡体验
    card_id: Optional[str] = ""


@router.post("/scan")
async def scan_checkin(
    body: ScanCheckinRequest,
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """扫码 / 输入会员ID核销进场。"""
    # 查找会员
    member = None
    if body.member_id:
        member = db.query(Member).filter(Member.member_id == body.member_id).first()
    elif body.phone:
        member = db.query(Member).filter(Member.phone == body.phone).first()

    if not member:
        raise MiniAppException(2002, "会员不存在")

    # 核销逻辑
    consume_detail = ""
    if body.consume_type == "次卡扣次" and body.card_id:
        card = (
            db.query(MembershipCard)
            .filter(MembershipCard.card_id == body.card_id)
            .first()
        )
        if card and (card.remaining_classes or 0) > 0:
            card.remaining_classes -= 1
            member.remaining_lessons = (member.remaining_lessons or 1) - 1
            consume_detail = f"次卡扣次：剩余{card.remaining_classes}次"

    now = datetime.now()
    checkin_id = generate_id("CI", db, Checkin.checkin_id)
    checkin = Checkin(
        checkin_id=checkin_id,
        member_id=member.member_id,
        member_name=member.name,
        consume_type=body.consume_type,
        consume_detail=consume_detail or body.consume_type,
        checkin_date=date.today(),
        checkin_time=now.strftime("%H:%M"),
    )
    db.add(checkin)
    db.commit()

    return success(data={
        "checkin_id": checkin_id,
        "member_name": member.name,
        "consume_note": consume_detail or body.consume_type,
        "timestamp": now.strftime("%Y-%m-%d %H:%M"),
    })


@router.get("/recent")
async def recent_checkins(
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """最近 20 条核销记录。"""
    records = (
        db.query(Checkin)
        .order_by(Checkin.checkin_date.desc(), Checkin.checkin_time.desc())
        .limit(20)
        .all()
    )
    return success(data=[
        {
            "checkin_id": c.checkin_id,
            "member_name": c.member_name,
            "consume_type": c.consume_type,
            "consume_note": c.consume_detail,
            "checkin_time": f"{c.checkin_date} {c.checkin_time}" if c.checkin_date else c.checkin_time,
        }
        for c in records
    ])
