"""会员小程序 · 个人主页（会员信息 + 汇总统计）"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models.models import Member, MembershipCard
from backend.miniapp.common import success
from backend.miniapp.auth import verify_member_token

router = APIRouter(prefix="/profile", tags=["会员-主页"])


@router.get("")
async def get_profile(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """获取会员个人资料 + 汇总统计。

    返回:
      - member: 基本信息
      - card_count: 有效会籍卡数量
      - total_remaining: 总剩余课时
      - balance: 储值余额
    """
    member_id = member.get("sub")
    member_info = db.query(Member).filter(Member.member_id == member_id).first()
    if not member_info:
        return success(data=None)

    # 有效会籍卡汇总
    cards = (
        db.query(MembershipCard)
        .filter(
            MembershipCard.member_id == member_id,
            MembershipCard.status == "active",
        )
        .all()
    )
    card_count = len(cards)

    return success(data={
        "name": member_info.name,
        "phone": member_info.phone,
        "member_id": member_info.member_id,
        "gender": member_info.gender,
        "card_count": card_count,
        "total_remaining": member_info.remaining_lessons or 0,
        "balance": float(member_info.balance or 0),
    })


@router.get("/dashboard")
async def get_dashboard(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """首页仪表盘聚合数据。

    返回: 会员信息 + 有效会籍卡列表 + 本月签到 + 待处理预约 + 到期提醒
    """
    member_id = member.get("sub")
    member_info = db.query(Member).filter(Member.member_id == member_id).first()
    if not member_info:
        return success(data=None)

    from backend.models.models import Checkin, Booking
    from datetime import date, datetime

    today = date.today()
    month_start = today.strftime("%Y-%m") + "-01"

    # 本月签到
    monthly_checkins = (
        db.query(func.count(Checkin.checkin_id))
        .filter(
            Checkin.member_id == member_id,
            Checkin.checkin_time >= month_start,
        )
        .scalar()
    ) or 0

    # 待处理预约
    pending_bookings = (
        db.query(func.count(Booking.booking_id))
        .filter(
            Booking.member_id == member_id,
            Booking.status.in_(["confirmed", "pending"]),
        )
        .scalar()
    ) or 0

    # 有效会籍卡
    cards = (
        db.query(MembershipCard)
        .filter(
            MembershipCard.member_id == member_id,
            MembershipCard.status == "active",
        )
        .all()
    )

    # 到期提醒（30天内）
    alerts = []
    for c in cards:
        if not c.end_date:
            continue
        days_left = (c.end_date - today).days
        if 0 <= days_left <= 30:
            alerts.append({
                "card_id": c.card_id,
                "product_name": c.card_name or "",
                "end_date": c.end_date.isoformat(),
                "days_left": days_left,
            })

    return success(data={
        "member": {
            "name": member_info.name,
            "phone": member_info.phone,
            "member_id": member_info.member_id,
        },
        "card_count": len(cards),
        "total_remaining": member_info.remaining_lessons or 0,
        "monthly_checkins": monthly_checkins,
        "pending_bookings": pending_bookings,
        "recent_cards": [
            {
                "card_id": c.card_id,
                "product_name": c.card_name or "",
                "card_type": c.card_type or "",
                "end_date": c.end_date.isoformat() if c.end_date else "",
                "remaining_classes": c.remaining_classes or 0,
            }
            for c in cards[:5]
        ],
        "alerts": alerts,
    })
