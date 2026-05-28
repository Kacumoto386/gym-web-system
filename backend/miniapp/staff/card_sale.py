"""员工小程序 · 会员购卡"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date

from backend.database import get_db
from backend.models.models import MembershipCard, Member, CardProduct, Sale
from backend.miniapp.common import success, MiniAppException
from backend.miniapp.auth import verify_staff_token
from backend.services.id_gen import generate_id

router = APIRouter(prefix="/cards", tags=["员工-购卡"])


class SellCardRequest(BaseModel):
    member_id: str
    product_name: str
    card_type: str  # 次卡 / 期限卡 / 储值卡 / 现金卡
    total_classes: Optional[int] = 0
    bonus_classes: Optional[int] = 0
    amount: float
    paid_amount: float
    salesperson: Optional[str] = ""
    validity_days: Optional[int] = 365
    start_date: Optional[str] = ""
    remark: Optional[str] = ""


@router.get("/products")
async def list_card_products(
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """可售卡种列表。"""
    products = db.query(CardProduct).filter(
        CardProduct.status.in_(["上架", "正常"])
    ).all()
    return success(data=[
        {
            "id": p.id,
            "name": p.card_name,
            "price": float(p.price) if p.price else 0,
            "validity_days": p.duration_days or 0,
        }
        for p in products
    ])


@router.post("/sell")
async def sell_card(
    body: SellCardRequest,
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """会员购卡。"""
    member = db.query(Member).filter(Member.member_id == body.member_id).first()
    if not member:
        raise MiniAppException(2002, "会员不存在")

    card_id = generate_id("MC", db, MembershipCard.card_id)

    card = MembershipCard(
        card_id=card_id,
        member_id=body.member_id,
        member_name=member.name,
        card_name=body.product_name,
        card_type=body.card_type,
        total_classes=body.total_classes or 0,
        bonus_classes=body.bonus_classes or 0,
        remaining_classes=(body.total_classes or 0) + (body.bonus_classes or 0),
        price=body.amount,
        actual_amount=body.paid_amount,
        staff_name=body.salesperson,
        duration_days=body.validity_days or 365,
        start_date=body.start_date or "",
        remark=body.remark,
        status="正常",
    )
    db.add(card)

    # 次卡售出后累加剩余次数到会员
    if body.card_type == "次卡":
        add_classes = (body.total_classes or 0) + (body.bonus_classes or 0)
        if add_classes:
            member.remaining_lessons = (member.remaining_lessons or 0) + add_classes

    # 同时记录售卡到售课表
    sale_id = generate_id("SA", db, Sale.sale_id)
    sale = Sale(
        sale_id=sale_id,
        sale_date=date.today(),
        member_id=body.member_id,
        member_name=member.name,
        course_name=body.product_name,
        bought_hours=0,
        total_price=body.amount,
        actual_amount=body.paid_amount,
        staff_name=body.salesperson,
    )
    db.add(sale)
    db.commit()

    return success(data={
        "card_id": card_id,
        "member_name": member.name,
        "remaining_lessons": member.remaining_lessons or 0,
        "message": "购卡成功",
    })
