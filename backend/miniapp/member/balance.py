"""会员小程序 · 储值余额 + 充值记录"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.models import Recharge
from backend.miniapp.common import success
from backend.miniapp.auth import verify_member_token

router = APIRouter(prefix="/balance", tags=["会员-储值"])


@router.get("")
async def get_balance(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """储值余额 + 最近充值记录。"""
    member_id = member.get("sub")

    # 查询最近充值记录
    recharges = (
        db.query(Recharge)
        .filter(Recharge.member_id == member_id)
        .order_by(Recharge.created_at.desc())
        .limit(10)
        .all()
    )
    # 计算余额（预开发阶段简单方式，后续可优化）
    balance = sum(
        float(r.amount or 0) for r in recharges
    ) - sum(
        float(r.amount or 0) for r in recharges if r.remark == "consumed"
    )

    return success(data={
        "balance": round(balance, 2),
        "recent_recharges": [
            {
                "recharge_id": r.recharge_id,
                "amount": float(r.amount or 0),
                "remark": r.remark or "",
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recharges
        ],
    })


@router.get("/history")
async def recharge_history(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """充值历史列表。"""
    member_id = member.get("sub")
    records = (
        db.query(Recharge)
        .filter(Recharge.member_id == member_id)
        .order_by(Recharge.created_at.desc())
        .all()
    )
    return success(data=[
        {
            "recharge_id": r.recharge_id,
            "amount": float(r.amount or 0),
            "method": r.payment_method or "",
            "remark": r.remark or "",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ])
