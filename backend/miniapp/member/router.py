"""会员小程序 · 路由汇总"""

from fastapi import APIRouter

from backend.miniapp.member import (
    auth,
    profile,
    card,
    balance,
    checkin,
    booking,
    class_record,
    body,
    alert,
    purchase,
)

router = APIRouter(prefix="/api/miniapp/member", tags=["会员小程序"])

router.include_router(auth.router)
router.include_router(profile.router)
router.include_router(card.router)
router.include_router(balance.router)
router.include_router(checkin.router)
router.include_router(booking.router)
router.include_router(class_record.router)
router.include_router(body.router)
router.include_router(alert.router)
router.include_router(purchase.router)
