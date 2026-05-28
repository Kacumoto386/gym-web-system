"""会员小程序 · 签到记录"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.models import Checkin
from backend.miniapp.common import success
from backend.miniapp.auth import verify_member_token

router = APIRouter(prefix="/checkins", tags=["会员-签到"])


@router.get("")
async def list_checkins(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """我的签到历史。"""
    member_id = member.get("sub")
    query = (
        db.query(Checkin)
        .filter(Checkin.member_id == member_id)
        .order_by(Checkin.checkin_time.desc())
    )

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    return success(data={
        "items": [
            {
                "checkin_id": c.checkin_id,
                "consume_type": c.consume_type,
                "consume_detail": c.consume_detail,
                "checkin_time": c.checkin_time or "",
            }
            for c in records
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": (page * page_size) < total,
    })


@router.get("/stats")
async def checkin_stats(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """签到统计（本月次数、累计次数）。"""
    member_id = member.get("sub")
    from sqlalchemy import func
    from datetime import datetime

    # 本月签到次数
    month_start = datetime.now().strftime("%Y-%m") + "-01"
    monthly = (
        db.query(func.count(Checkin.checkin_id))
        .filter(
            Checkin.member_id == member_id,
            Checkin.checkin_time >= month_start,
        )
        .scalar()
    )

    # 累计签到次数
    total = (
        db.query(func.count(Checkin.checkin_id))
        .filter(Checkin.member_id == member_id)
        .scalar()
    )

    return success(data={
        "monthly_count": monthly or 0,
        "total_count": total or 0,
    })
