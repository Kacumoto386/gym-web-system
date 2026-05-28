"""会员小程序 · 到期提醒"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import date, datetime

from backend.database import get_db
from backend.models.models import MembershipCard
from backend.miniapp.common import success
from backend.miniapp.auth import verify_member_token

router = APIRouter(prefix="/alerts", tags=["会员-提醒"])


@router.get("")
async def list_alerts(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """即将到期的会员卡提醒。"""
    member_id = member.get("sub")
    today = date.today()

    cards = (
        db.query(MembershipCard)
        .filter(
            MembershipCard.member_id == member_id,
            MembershipCard.status == "active",
        )
        .all()
    )

    alerts = []
    for c in cards:
        if not c.end_date:
            continue
        days_left = (c.end_date - today).days
        if 0 <= days_left <= 30:  # 30天内到期
            alerts.append({
                "card_id": c.card_id,
                "product_name": c.card_name or "",
                "end_date": c.end_date.isoformat(),
                "days_left": days_left,
                "remaining_classes": c.remaining_classes or 0,
            })

    return success(data=alerts)
