"""会员小程序 · 会籍卡信息"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.models import MembershipCard
from backend.miniapp.common import success, MiniAppException
from backend.miniapp.auth import verify_member_token

router = APIRouter(prefix="/cards", tags=["会员-会籍卡"])


@router.get("")
async def list_cards(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """我的会籍卡列表。"""
    member_id = member.get("sub")
    cards = (
        db.query(MembershipCard)
        .filter(MembershipCard.member_id == member_id)
        .order_by(MembershipCard.created_at.desc())
        .all()
    )
    return success(data=[
        {
            "card_id": c.card_id,
            "product_name": c.card_name or "",
            "card_type": c.card_type or "",
            "total_classes": c.total_classes or 0,
            "remaining_classes": c.remaining_classes or 0,
            "status": c.status,
            "start_date": c.start_date.isoformat() if c.start_date else "",
            "end_date": c.end_date.isoformat() if c.end_date else "",
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cards
    ])


@router.get("/{card_id}")
async def get_card(
    card_id: str,
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """单卡详情。"""
    card = (
        db.query(MembershipCard)
        .filter(
            MembershipCard.card_id == card_id,
            MembershipCard.member_id == member.get("sub"),
        )
        .first()
    )
    if not card:
        raise MiniAppException(2002, "会籍卡不存在")

    return success(data={
        "card_id": card.card_id,
        "product_name": card.card_name or "",
        "card_type": card.card_type or "",
        "total_classes": card.total_classes or 0,
        "bonus_classes": card.bonus_classes or 0,
        "remaining_classes": 0,
        "amount": float(card.price or 0),
        "paid_amount": float(card.actual_amount or 0),
        "status": card.status,
        "start_date": card.start_date.isoformat() if card.start_date else "",
        "end_date": card.end_date.isoformat() if card.end_date else "",
        "salesperson": card.staff_name or "",
        "remark": card.remark or "",
    })


@router.get("/{card_id}/history")
async def get_card_history(
    card_id: str,
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """卡的使用记录。"""
    from backend.models.models import Checkin

    records = (
        db.query(Checkin)
        .filter(
            Checkin.member_id == member.get("sub"),
            Checkin.consume_type.in_(["次卡扣次", "期限卡签到", "现金卡扣费"]),
        )
        .order_by(Checkin.checkin_time.desc())
        .limit(50)
        .all()
    )
    return success(data=[
        {
            "checkin_id": c.checkin_id,
            "consume_type": c.consume_type,
            "consume_detail": c.consume_detail,
            "checkin_time": c.checkin_time or "",
        }
        for c in records
    ])
