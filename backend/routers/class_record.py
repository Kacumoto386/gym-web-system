# -*- coding: utf-8 -*-
"""
上课记录 API 路由 + HTMX HTML 片段端点
V3.2.6 — 编辑增强 + 统计卡片 + 状态管理 + 搜索筛选 + 评价反馈
"""
from typing import Optional, List
from fastapi import Request,  APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime
from backend.database import get_db
from backend.models.models import ClassRecord, Member
from backend.services.id_gen import generate_id
from pydantic import BaseModel

router = APIRouter(prefix="/api/class-records", tags=["上课管理"])


# ═══════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════

_STATUS_COLORS = {
    "已完成": "bg-green-100 text-green-700",
    "已预约": "bg-blue-100 text-blue-700",
    "已签到": "bg-yellow-100 text-yellow-700",
    "已取消": "bg-red-100 text-red-700",
}


def _status_badge(s: str) -> str:
    return _STATUS_COLORS.get(s, "bg-gray-100 text-gray-700")


# ═══════════════════════════════════════════
# 统计卡片
# ═══════════════════════════════════════════

@router.get("/cards", response_class=HTMLResponse)
def class_record_cards(db: Session = Depends(get_db)):
    query = db.query(ClassRecord)
    total = query.count()
    completed = query.filter(ClassRecord.status == "已完成").count()
    signed = query.filter(ClassRecord.status == "已签到").count()
    coaches = db.query(ClassRecord.coach_name).filter(
        ClassRecord.coach_name != "", ClassRecord.coach_name.isnot(None)
    ).distinct().count()
    sum_hours = db.query(func.sum(ClassRecord.consumed_hours)).scalar() or 0

    return f"""<div class="grid grid-cols-5 gap-4 mb-4">
        <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-blue-500">
            <div class="text-xs text-gray-400">总记录</div>
            <div class="text-2xl font-bold text-gray-800">{total}</div>
        </div>
        <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-green-500">
            <div class="text-xs text-gray-400">已完成</div>
            <div class="text-2xl font-bold text-green-600">{completed}</div>
        </div>
        <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-yellow-500">
            <div class="text-xs text-gray-400">已签到</div>
            <div class="text-2xl font-bold text-yellow-600">{signed}</div>
        </div>
        <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-purple-500">
            <div class="text-xs text-gray-400">授课教练</div>
            <div class="text-2xl font-bold text-purple-600">{coaches}</div>
        </div>
        <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-orange-500">
            <div class="text-xs text-gray-400">总耗课时</div>
            <div class="text-2xl font-bold text-orange-600">{sum_hours}</div>
        </div>
    </div>"""


# ═══════════════════════════════════════════
# 表格
# ═══════════════════════════════════════════

def _build_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无上课记录</div>'
    trs = ""
    for r in rows:
        sc = _status_badge(r.status)
        ev = r.evaluation or ""
        ev_badge = ""
        if ev == "好评":
            ev_badge = '<span class="text-xs text-green-500 ml-1">👍</span>'
        elif ev == "中评":
            ev_badge = '<span class="text-xs text-yellow-500 ml-1">👌</span>'
        elif ev == "差评":
            ev_badge = '<span class="text-xs text-red-500 ml-1">👎</span>'
        trs += f"""<tr class="hover:bg-gray-50 border-b group" onclick="toggleDetail('{r.record_id}')">
            <td class="px-3 py-2.5 text-xs text-gray-500">{r.record_id}</td>
            <td class="px-3 py-2.5">{r.member_name or ''}</td>
            <td class="px-3 py-2.5 text-sm text-gray-500">{r.member_phone or ''}</td>
            <td class="px-3 py-2.5 text-sm">{r.course_name or ''}</td>
            <td class="px-3 py-2.5 text-sm text-gray-600">{r.coach_name or '-'}</td>
            <td class="px-3 py-2.5 text-sm">{r.class_date}</td>
            <td class="px-3 py-2.5 text-sm text-gray-500">{r.start_time or ''}~{r.end_time or ''}</td>
            <td class="px-3 py-2.5 text-sm">{r.consumed_hours or 0}</td>
            <td class="px-3 py-2.5"><span class="px-2 py-0.5 {sc} rounded text-xs">{r.status or ''}</span>{ev_badge}</td>
            <td class="px-3 py-2.5 text-sm" onclick="event.stopPropagation()">
                <div class="flex gap-1">
                    <button class="text-blue-600 hover:text-blue-800 text-xs px-2 py-1 rounded hover:bg-blue-50"
                            onclick="openEditRecord('{r.record_id}')">编辑</button>
                    <button class="text-red-500 hover:text-red-700 text-xs px-2 py-1 rounded hover:bg-red-50"
                            hx-delete="/api/class-records/{r.record_id}" hx-target="#classRecordTable"
                            hx-confirm="确认删除此上课记录？">删除</button>
                </div>
            </td>
        </tr>
        <tr class="hidden border-b bg-gray-50" id="detail-{r.record_id}">
            <td colspan="10" class="px-6 py-3" onclick="event.stopPropagation()">
                <div class="grid grid-cols-3 gap-4 text-sm">
                    <div><span class="text-gray-400">会员电话</span><br><span class="text-gray-700">{r.member_phone or '-'}</span></div>
                    <div><span class="text-gray-400">签到时间</span><br><span class="text-gray-700">{r.sign_in_time.strftime('%Y-%m-%d %H:%M') if r.sign_in_time else '-'}</span></div>
                    <div><span class="text-gray-400">进场核销</span><br><span class="text-gray-700">{r.checkin_record or '-'}</span></div>
                    <div><span class="text-gray-400">评价</span><br><span class="text-gray-700">{ev or '-'}</span></div>
                    <div><span class="text-gray-400">提成</span><br><span class="text-gray-700">{'¥%.2f' % r.commission_amount if r.commission_amount else '-'}</span></div>
                    <div><span class="text-gray-400">签到人数</span><br><span class="text-gray-700">{r.sign_in_count or 1} 人</span></div>
                    <div class="col-span-3"><span class="text-gray-400">会员反馈</span><br><span class="text-gray-600">{r.feedback or '-'}</span></div>
                    <div class="col-span-3"><span class="text-gray-400">上课心得</span><br><span class="text-gray-600">{r.notes or '-'}</span></div>
                </div>
            </td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-3 py-3">编号</th><th class="px-3 py-3">会员</th><th class="px-3 py-3">手机号</th><th class="px-3 py-3">课程</th><th class="px-3 py-3">教练</th><th class="px-3 py-3">日期</th><th class="px-3 py-3">时间</th><th class="px-3 py-3">课时</th><th class="px-3 py-3">状态</th><th class="px-3 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("/table", response_class=HTMLResponse)
def class_record_table(
    member_id: str = "", class_date: str = "",
    status: str = "", coach: str = "",
    keyword: str = "",
    db: Session = Depends(get_db)
):
    query = db.query(ClassRecord)
    if member_id:
        query = query.filter(ClassRecord.member_id == member_id)
    if class_date:
        try:
            d = date.fromisoformat(class_date)
            query = query.filter(ClassRecord.class_date == d)
        except ValueError:
            pass
    if status:
        query = query.filter(ClassRecord.status == status)
    if coach:
        query = query.filter(ClassRecord.coach_name.contains(coach))
    if keyword:
        kw = keyword.strip()
        query = query.filter(
            ClassRecord.member_name.contains(kw) |
            ClassRecord.course_name.contains(kw) |
            ClassRecord.record_id.contains(kw)
        )
    records = query.order_by(ClassRecord.id.desc()).limit(100).all()

    # 从 Member 表补充缺失的手机号
    member_ids = set(r.member_id for r in records if r.member_id and not r.member_phone)
    if member_ids:
        members = db.query(Member).filter(Member.member_id.in_(member_ids)).all()
        phone_map = {m.member_id: m.phone or "" for m in members}
        for r in records:
            if not r.member_phone and r.member_id in phone_map:
                r.member_phone = phone_map[r.member_id]

    return _build_table(records)


# ═══════════════════════════════════════════
# 统计接口（给编辑弹窗选择教练/课程用）
# ═══════════════════════════════════════════

@router.get("/coaches", response_class=HTMLResponse)
def get_coach_options(db: Session = Depends(get_db)):
    rows = db.query(ClassRecord.coach_name).filter(
        ClassRecord.coach_name != "", ClassRecord.coach_name.isnot(None)
    ).distinct().all()
    opts = "".join(f'<option value="{r[0]}">{r[0]}</option>' for r in rows if r[0])
    return f"""<select name="coach_name" id="edit_coach_name" class="w-full px-3 py-2 border rounded-lg text-sm">
        <option value="">请选择</option>{opts}</select>"""


@router.get("/status-options", response_class=HTMLResponse)
def get_status_options():
    opts = "".join(f'<option value="{s}">{s}</option>' for s in _STATUS_COLORS.keys())
    return f"""<select name="status" id="edit_status" class="w-full px-3 py-2 border rounded-lg text-sm">
        <option value="">请选择</option>{opts}</select>"""


# ═══════════════════════════════════════════
# 评价接口
# ═══════════════════════════════════════════

class EvaluationUpdate(BaseModel):
    evaluation: str
    feedback: Optional[str] = ""


@router.post("/{record_id}/evaluation")
def update_evaluation(record_id: str, data: EvaluationUpdate, db: Session = Depends(get_db)):
    record = db.query(ClassRecord).filter(ClassRecord.record_id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="上课记录不存在")
    record.evaluation = data.evaluation
    if data.feedback:
        record.feedback = data.feedback.strip()
    db.commit()
    return {"success": True, "evaluation": record.evaluation}


# ═══════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════

class ClassRecordCreate(BaseModel):
    member_id: str
    member_name: str
    member_phone: Optional[str] = ""
    course_id: str
    course_name: str
    coach_id: Optional[str] = ""
    coach_name: Optional[str] = ""
    start_time: Optional[str] = ""
    end_time: Optional[str] = ""
    consumed_hours: int = 1
    notes: Optional[str] = ""
    store_id: Optional[str] = ""


class ClassRecordUpdate(BaseModel):
    member_id: Optional[str] = None
    member_name: Optional[str] = None
    member_phone: Optional[str] = None
    course_id: Optional[str] = None
    course_name: Optional[str] = None
    coach_id: Optional[str] = None
    coach_name: Optional[str] = None
    class_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    consumed_hours: Optional[int] = None
    status: Optional[str] = None
    evaluation: Optional[str] = None
    feedback: Optional[str] = None
    notes: Optional[str] = None


class ClassRecordOut(BaseModel):
    id: int
    record_id: str
    class_date: date
    member_id: str
    member_name: str
    member_phone: str = ""
    course_id: str = ""
    course_name: str = ""
    coach_id: str = ""
    coach_name: str = ""
    start_time: str = ""
    end_time: str = ""
    consumed_hours: int = 1
    status: str = ""
    evaluation: str = ""
    feedback: str = ""
    commission_amount: float = 0
    sign_in_count: int = 1
    sign_in_time: Optional[datetime] = None
    checkin_record: str = ""
    notes: str = ""

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════

@router.get("", response_model=List[ClassRecordOut])
def list_class_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    member_id: Optional[str] = None,
    class_date: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(ClassRecord)
    if member_id:
        query = query.filter(ClassRecord.member_id == member_id)
    if class_date:
        try:
            d = date.fromisoformat(class_date)
            query = query.filter(ClassRecord.class_date == d)
        except ValueError:
            pass
    if status:
        query = query.filter(ClassRecord.status == status)
    return query.order_by(ClassRecord.id.desc()).offset(skip).limit(limit).all()


@router.get("/{record_id}", response_model=ClassRecordOut)
def get_class_record(record_id: str, db: Session = Depends(get_db)):
    record = db.query(ClassRecord).filter(ClassRecord.record_id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="上课记录不存在")
    return record


@router.post("", response_model=ClassRecordOut)
def create_class_record(request: Request, data: ClassRecordCreate, db: Session = Depends(get_db)):
    record_id = generate_id("CL", db, ClassRecord.record_id)
    record = ClassRecord(
        record_id=record_id, class_date=date.today(),
        member_id=data.member_id, member_name=data.member_name,
        member_phone=data.member_phone or "",
        course_id=data.course_id, course_name=data.course_name,
        coach_id=data.coach_id or "", coach_name=data.coach_name or "",
        start_time=data.start_time or "", end_time=data.end_time or "",
        consumed_hours=data.consumed_hours or 1,
        notes=data.notes or "", status="已完成",
        store_id=data.store_id or "",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.put("/{record_id}", response_model=ClassRecordOut)
def update_class_record(record_id: str, data: ClassRecordUpdate, db: Session = Depends(get_db)):
    record = db.query(ClassRecord).filter(ClassRecord.record_id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="上课记录不存在")
    update_dict = data.model_dump(exclude_unset=True)

    # 校验：结束时间不能早于开始时间
    start_time = update_dict.get("start_time") or record.start_time
    end_time = update_dict.get("end_time") or record.end_time
    if start_time and end_time and end_time <= start_time:
        raise HTTPException(status_code=422, detail="结束时间不能早于开始时间")

    for key, val in update_dict.items():
        if val is not None:
            if key == "class_date" and isinstance(val, str):
                try:
                    val = date.fromisoformat(val)
                except ValueError:
                    continue
            setattr(record, key, val.strip() if isinstance(val, str) else val)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{record_id}")
def delete_class_record(record_id: str, db: Session = Depends(get_db)):
    record = db.query(ClassRecord).filter(ClassRecord.record_id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="上课记录不存在")
    db.delete(record)
    db.commit()
    return {"success": True, "message": f"上课记录 {record_id} 已删除"}
