"""员工小程序 · 会员录入 + 会员查询"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend.models.models import Member, MembershipCard
from backend.miniapp.common import success, MiniAppException
from backend.miniapp.auth import verify_staff_token

router = APIRouter(prefix="/members", tags=["员工-会员管理"])


class CreateMemberRequest(BaseModel):
    name: str
    phone: str
    gender: Optional[str] = "男"
    height: Optional[float] = None
    weight: Optional[float] = None
    body_fat: Optional[float] = None


class UpdateMemberRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    body_fat: Optional[float] = None


@router.post("")
async def create_member(
    body: CreateMemberRequest,
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """新增会员。"""
    # 生成 member_id（复用现有生成逻辑）
    from backend.services.id_gen import generate_id
    member_id = generate_id("M", db, Member.member_id)

    member = Member(
        member_id=member_id,
        name=body.name,
        phone=body.phone,
        gender=body.gender,
        height=body.height,
        weight=body.weight,
        body_fat=body.body_fat,
    )
    db.add(member)
    db.commit()

    return success(data={
        "member_id": member_id,
        "name": body.name,
        "phone": body.phone,
        "created_at": member.created_at.isoformat() if member.created_at else None,
    })


@router.put("/{member_id}")
async def update_member(
    member_id: str,
    body: UpdateMemberRequest,
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise MiniAppException(2002, "会员不存在")

    update_data = body.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(member, field, value)
    db.commit()

    return success(data={"member_id": member_id})


@router.get("/search")
async def search_member(
    keyword: str = Query("", description="姓名或手机号"),
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """按姓名或手机号搜索会员。"""
    query = db.query(Member)
    if keyword:
        query = query.filter(
            Member.name.contains(keyword) | Member.phone.contains(keyword)
        )
    members = query.order_by(Member.created_at.desc()).limit(20).all()

    return success(data=[
        {
            "member_id": m.member_id,
            "name": m.name,
            "phone": m.phone,
            "gender": m.gender,
            "remaining_lessons": m.remaining_lessons or 0,
        }
        for m in members
    ])


@router.get("/{member_id}")
async def get_member(
    member_id: str,
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """会员基本信息 + 会籍卡列表。"""
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise MiniAppException(2002, "会员不存在")

    cards = db.query(MembershipCard).filter(
        MembershipCard.member_id == member_id
    ).all()

    return success(data={
        "member_id": member.member_id,
        "name": member.name,
        "phone": member.phone,
        "gender": member.gender,
        "height": member.height,
        "weight": member.weight,
        "body_fat": member.body_fat,
        "remaining_lessons": member.remaining_lessons or 0,
        "cards": [
            {
                "card_id": c.card_id,
                "product_name": c.card_name,
                "card_type": c.card_type,
                "total_classes": c.total_classes,
                "remaining_classes": c.remaining_classes,
                "status": c.status,
            }
            for c in cards
        ],
    })


@router.get("/{member_id}/checkins")
async def get_member_checkins(
    member_id: str,
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """会员的签到记录。"""
    from backend.models.models import Checkin
    records = (
        db.query(Checkin)
        .filter(Checkin.member_id == member_id)
        .order_by(Checkin.checkin_time.desc())
        .limit(50)
        .all()
    )
    return success(data=[
        {
            "checkin_id": c.checkin_id,
            "checkin_time": f"{c.checkin_date} {c.checkin_time}" if c.checkin_date else c.checkin_time,
            "consume_type": c.consume_type,
            "consume_detail": c.consume_detail,
        }
        for c in records
    ])
