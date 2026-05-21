# -*- coding: utf-8 -*-
"""
体测记录 API 路由 + HTMX HTML 片段端点
V3.0.0
"""
from typing import Optional, List
from fastapi import Request,  APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import date
from backend.database import get_db
from backend.models.models import BodyMeasurement
from backend.services.id_gen import generate_id
from pydantic import BaseModel

router = APIRouter(prefix="/api/body-measurements", tags=["体测管理"])


# ═══════════════════════════════════════════
# HTMX HTML 片段
# ═══════════════════════════════════════════

def _build_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无体测记录</div>'
    trs = ""
    for b in rows:
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{b.measure_id}</td>
            <td class="px-4 py-3">{b.member_name or ''}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{b.member_id}</td>
            <td class="px-4 py-3 text-sm">{b.measure_date}</td>
            <td class="px-4 py-3 text-sm">{b.height or '-'}</td>
            <td class="px-4 py-3 text-sm">{b.weight or '-'}</td>
            <td class="px-4 py-3 text-sm">{b.body_fat or '-'}%</td>
            <td class="px-4 py-3 text-sm">{b.bmi or '-'}</td>
            <td class="px-4 py-3 text-sm">{b.muscle_mass or '-'}</td>
            <td class="px-4 py-3 text-sm">{b.basal_metabolism or '-'}</td>
            <td class="px-4 py-3 text-sm">
                <button class="text-red-500 hover:text-red-700" hx-delete="/api/body-measurements/{b.measure_id}" hx-target="#bodyTable" hx-confirm="确认删除此体测记录？">删除</button>
            </td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">会员</th><th class="px-4 py-3">会员编号</th><th class="px-4 py-3">日期</th><th class="px-4 py-3">身高</th><th class="px-4 py-3">体重</th><th class="px-4 py-3">体脂率</th><th class="px-4 py-3">BMI</th><th class="px-4 py-3">肌肉量</th><th class="px-4 py-3">基础代谢</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("/table", response_class=HTMLResponse)
def body_table(member_id: str = "", db: Session = Depends(get_db)):
    query = db.query(BodyMeasurement)
    if member_id:
        query = query.filter(BodyMeasurement.member_id == member_id)
    return _build_table(query.order_by(BodyMeasurement.measure_date.desc()).limit(100).all())


# ═══════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════

class BodyMeasurementCreate(BaseModel):
    member_id: str
    member_name: str
    measure_date: str  # ISO date
    height: Optional[float] = 0
    weight: Optional[float] = 0
    body_fat: Optional[float] = 0
    bmi: Optional[float] = 0
    muscle_mass: Optional[float] = 0
    basal_metabolism: Optional[int] = 0
    body_age: Optional[int] = 0
    remark: Optional[str] = ""


class BodyMeasurementOut(BaseModel):
    id: int
    measure_id: str
    member_id: str
    member_name: str
    measure_date: Optional[date] = None
    height: float
    weight: float
    body_fat: float
    bmi: float
    muscle_mass: float
    basal_metabolism: int

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════

@router.get("", response_model=List[BodyMeasurementOut])
def list_body(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    member_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(BodyMeasurement)
    if member_id:
        query = query.filter(BodyMeasurement.member_id == member_id)
    return query.order_by(BodyMeasurement.measure_date.desc()).offset(skip).limit(limit).all()


@router.get("/{measure_id}", response_model=BodyMeasurementOut)
def get_body(measure_id: str, db: Session = Depends(get_db)):
    b = db.query(BodyMeasurement).filter(BodyMeasurement.measure_id == measure_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="体测记录不存在")
    return b


@router.post("", response_model=BodyMeasurementOut)
def create_body(data: BodyMeasurementCreate, db: Session = Depends(get_db)):
    measure_id = generate_id("BM", db, BodyMeasurement.measure_id)
    try:
        d = date.fromisoformat(data.measure_date) if data.measure_date else date.today()
    except ValueError:
        d = date.today()
    b = BodyMeasurement(
        measure_id=measure_id, measure_date=d,
        member_id=data.member_id, member_name=data.member_name,
        height=data.height or 0, weight=data.weight or 0,
        body_fat=data.body_fat or 0, bmi=data.bmi or 0,
        muscle_mass=data.muscle_mass or 0,
        basal_metabolism=data.basal_metabolism or 0,
        body_age=data.body_age or 0,
        remark=data.remark or "",
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@router.delete("/{measure_id}")
def delete_body(measure_id: str, request: Request, db: Session = Depends(get_db)):
    b = db.query(BodyMeasurement).filter(BodyMeasurement.measure_id == measure_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="体测记录不存在")
    db.delete(b)
    db.commit()

    return {"success": True, "message": f"体测记录 {measure_id} 已删除"}
