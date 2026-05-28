"""员工小程序 · 业绩提成查询"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime

from backend.database import get_db
from backend.models.models import Sale, MembershipCard
from backend.miniapp.common import success
from backend.miniapp.auth import verify_staff_token

router = APIRouter(prefix="/performance", tags=["员工-业绩"])


@router.get("/summary")
async def performance_summary(
    year: int = Query(datetime.now().year),
    month: int = Query(datetime.now().month),
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """本月业绩概览（售卡+售课金额）。"""
    staff_id = staff.get("sub")
    staff_name = staff.get("name", "")

    # 售卡金额
    card_total = (
        db.query(MembershipCard)
        .filter(
            MembershipCard.staff_name == staff_name,
        )
        .all()
    )
    card_amount = sum(float(c.actual_amount or 0) for c in card_total)

    # 售课金额
    sale_total = (
        db.query(Sale)
        .filter(
            Sale.staff_name == staff_name,
        )
        .all()
    )
    sale_amount = sum(float(s.actual_amount or 0) for s in sale_total)

    return success(data={
        "staff_id": staff_id,
        "staff_name": staff_name,
        "card_sales": round(card_amount, 2),
        "course_sales": round(sale_amount, 2),
        "total": round(card_amount + sale_amount, 2),
    })


@router.get("/sales")
async def performance_sales(
    year: int = Query(datetime.now().year),
    month: int = Query(datetime.now().month),
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """售课/售卡明细。"""
    staff_name = staff.get("name", "")

    cards = (
        db.query(MembershipCard)
        .filter(MembershipCard.staff_name == staff_name)
        .order_by(MembershipCard.created_at.desc())
        .all()
    )
    sales = (
        db.query(Sale)
        .filter(Sale.staff_name == staff_name)
        .order_by(Sale.created_at.desc())
        .all()
    )

    return success(data={
        "card_sales": [
            {
                "card_id": c.card_id,
                "member_name": c.member_name,
                "product_name": c.card_name,
                "paid_amount": float(c.actual_amount or 0),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in cards
        ],
        "course_sales": [
            {
                "sale_id": s.sale_id,
                "member_name": s.member_name,
                "product_name": s.course_name,
                "paid_amount": float(s.actual_amount or 0),
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sales
        ],
    })


@router.get("/commission")
async def performance_commission(
    year: int = Query(datetime.now().year),
    month: int = Query(datetime.now().month),
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """本月预估提成（复用现有 commission 计算逻辑）。"""
    staff_id = staff.get("sub")
    # 复用 commission.py 的 calculate 逻辑
    from backend.routers.commission import calculate_commission
    result = calculate_commission(staff_id=staff_id, year=year, month=month, db=db)
    return success(data=result)
