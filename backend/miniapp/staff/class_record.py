"""员工小程序 · 上课记录"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date

from backend.database import get_db
from backend.models.models import ClassRecord
from backend.miniapp.common import success
from backend.miniapp.auth import verify_staff_token
from backend.services.id_gen import generate_id

router = APIRouter(prefix="/class-records", tags=["员工-上课记录"])


class CreateClassRecordRequest(BaseModel):
    member_id: str
    member_name: str
    course_name: Optional[str] = ""
    coach_name: Optional[str] = ""
    remark: Optional[str] = ""


@router.get("")
async def list_class_records(
    member_id: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """上课记录列表。"""
    query = db.query(ClassRecord).order_by(ClassRecord.class_date.desc())

    if member_id:
        query = query.filter(ClassRecord.member_id == member_id)
    if date:
        query = query.filter(ClassRecord.class_date == date)

    total = query.count()
    records = query.offset((page - 1) * page_size).limit(page_size).all()

    return success(data={
        "items": [
            {
                "record_id": r.record_id,
                "member_name": r.member_name,
                "course_name": r.course_name,
                "coach_name": r.coach_name,
                "class_date": r.class_date,
                "remark": r.notes,
            }
            for r in records
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": (page * page_size) < total,
    })


@router.post("")
async def create_class_record(
    body: CreateClassRecordRequest,
    db: Session = Depends(get_db),
    staff: dict = Depends(verify_staff_token),
):
    """登记上课记录。"""
    record_id = generate_id("CR", db, ClassRecord.record_id)
    record = ClassRecord(
        record_id=record_id,
        member_id=body.member_id,
        member_name=body.member_name,
        course_name=body.course_name,
        coach_name=body.coach_name,
        class_date=date.today(),
        notes=body.remark,
    )
    db.add(record)
    db.commit()

    return success(data={"record_id": record.record_id, "message": "登记成功"})
