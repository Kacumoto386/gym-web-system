"""会员小程序 · 上课记录"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models.models import ClassRecord
from backend.miniapp.common import success
from backend.miniapp.auth import verify_member_token

router = APIRouter(prefix="/class-records", tags=["会员-上课记录"])


@router.get("")
async def list_class_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """我的上课历史。"""
    member_id = member.get("sub")
    query = (
        db.query(ClassRecord)
        .filter(ClassRecord.member_id == member_id)
        .order_by(ClassRecord.class_date.desc())
    )

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    return success(data={
        "items": [
            {
                "record_id": r.record_id,
                "course_name": r.course_name or "",
                "coach_name": r.coach_name or "",
                "class_date": r.class_date,
                "remark": r.notes or "",
            }
            for r in records
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": (page * page_size) < total,
    })


@router.get("/stats")
async def class_record_stats(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """上课统计。"""
    member_id = member.get("sub")
    from datetime import datetime

    month_start = datetime.now().strftime("%Y-%m") + "-01"
    monthly = (
        db.query(func.count(ClassRecord.record_id))
        .filter(
            ClassRecord.member_id == member_id,
            ClassRecord.class_date >= month_start,
        )
        .scalar()
    )
    total = (
        db.query(func.count(ClassRecord.record_id))
        .filter(ClassRecord.member_id == member_id)
        .scalar()
    )

    return success(data={
        "monthly_count": monthly or 0,
        "total_count": total or 0,
    })
