"""员工小程序 · 路由汇总"""

from fastapi import APIRouter

from backend.miniapp.staff import (
    auth,
    member,
    card_sale,
    course_sale,
    booking,
    checkin,
    class_record,
    performance,
)

router = APIRouter(prefix="/api/miniapp/staff", tags=["员工小程序"])

router.include_router(auth.router)
router.include_router(member.router)
router.include_router(card_sale.router)
router.include_router(course_sale.router)
router.include_router(booking.router)
router.include_router(checkin.router)
router.include_router(class_record.router)
router.include_router(performance.router)
