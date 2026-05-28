"""会员小程序 · 体测记录"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.models import BodyMeasurement
from backend.miniapp.common import success
from backend.miniapp.auth import verify_member_token

router = APIRouter(prefix="/body-measurements", tags=["会员-体测"])


@router.get("")
async def list_measurements(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """体测历史列表。"""
    member_id = member.get("sub")
    records = (
        db.query(BodyMeasurement)
        .filter(BodyMeasurement.member_id == member_id)
        .order_by(BodyMeasurement.measure_date.desc())
        .all()
    )
    return success(data=[
        {
            "id": r.id,
            "height": r.height,
            "weight": r.weight,
            "body_fat": r.body_fat,
            "measure_date": r.measure_date.isoformat() if r.measure_date else None,
            "remark": r.remark or "",
        }
        for r in records
    ])


@router.get("/latest")
async def latest_measurement(
    db: Session = Depends(get_db),
    member: dict = Depends(verify_member_token),
):
    """最近一次体测。"""
    member_id = member.get("sub")
    record = (
        db.query(BodyMeasurement)
        .filter(BodyMeasurement.member_id == member_id)
        .order_by(BodyMeasurement.measure_date.desc())
        .first()
    )
    if not record:
        return success(data=None)

    return success(data={
        "id": record.id,
        "height": record.height,
        "weight": record.weight,
        "body_fat": record.body_fat,
        "measure_date": record.measure_date.isoformat() if record.measure_date else None,
    })
