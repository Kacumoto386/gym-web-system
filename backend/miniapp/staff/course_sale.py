"""员工小程序 · 购课 / 课程包"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date

from backend.database import get_db
from backend.models.models import Sale, Member, Package
from backend.miniapp.common import success, MiniAppException
from backend.miniapp.auth import verify_staff_token
from backend.services.id_gen import generate_id

router = APIRouter(prefix="/sales", tags=["员工-购课"])


class CreateSaleRequest(BaseModel):
    member_id: str
    package_id: Optional[str] = None
    product_name: Optional[str] = ""
    quantity: int = 1
    amount: float
    paid_amount: float
    salesperson: Optional[str] = ""
    remark: Optional[str] = ""


@router.get("/packages")
async def list_packages(
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """可购课程包列表。"""
    packages = db.query(Package).all()
    return success(data=[
        {
            "package_id": p.package_id,
            "name": p.name,
            "price": float(p.price) if p.price else 0,
            "total_classes": p.total_classes or 0,
            "validity_days": p.validity_days or 0,
        }
        for p in packages
    ])


@router.post("")
async def create_sale(
    body: CreateSaleRequest,
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """售课 / 售卖课程包。"""
    member = db.query(Member).filter(Member.member_id == body.member_id).first()
    if not member:
        raise MiniAppException(2002, "会员不存在")

    sale_id = generate_id("SA", db, Sale.sale_id)
    sale = Sale(
        sale_id=sale_id,
        sale_date=date.today(),
        member_id=body.member_id,
        member_name=member.name,
        course_name=body.product_name,
        bought_hours=body.quantity,
        total_price=body.amount,
        actual_amount=body.paid_amount,
        staff_name=body.salesperson,
        remark=body.remark,
    )
    db.add(sale)
    db.commit()

    return success(data={
        "sale_id": sale_id,
        "message": "售课成功",
    })
