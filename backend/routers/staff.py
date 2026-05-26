# -*- coding: utf-8 -*-
"""
员工管理 API 路由 + HTMX HTML 片段端点
V3.0.0
"""
from typing import Optional, List
from fastapi import Request,  APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend.database import get_db
from backend.routers.operation_log import record_log
from backend.models.models import Staff
from backend.services.id_gen import generate_id
from pydantic import BaseModel

router = APIRouter(prefix="/api/staff", tags=["员工管理"])


# ═══════════════════════════════════════════
# HTMX HTML 片段
# ═══════════════════════════════════════════

def _build_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无员工数据</div>'
    trs = ""
    for s in rows:
        status_cls = "bg-green-100 text-green-700" if s.status == "在职" else "bg-red-100 text-red-700"
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{s.staff_id}</td>
            <td class="px-4 py-3">{s.name}</td>
            <td class="px-4 py-3 text-sm">{s.gender or ''}</td>
            <td class="px-4 py-3 text-sm">{s.phone or ''}</td>
            <td class="px-4 py-3 text-sm">{s.position or ''}</td>
            <td class="px-4 py-3 text-sm">{'%.2f' % (s.base_salary or 0)}</td>
            <td class="px-4 py-3 text-sm">{'%.1f%%' % ((s.sale_commission_rate or 0) * 100)}</td>
            <td class="px-4 py-3 text-sm"><span class="px-2 py-0.5 {status_cls} rounded text-xs">{s.status or '在职'}</span></td>
            <td class="px-4 py-3 text-sm">
                <button class="text-blue-600 hover:text-blue-800 mr-2" onclick="openEditStaff('{s.staff_id}')">编辑</button>
                <button class="text-red-500 hover:text-red-700" hx-delete="/api/staff/{s.staff_id}" hx-target="#staffTable" hx-confirm="确认删除员工 {s.name}？">删除</button>
            </td>
        </tr>"""
    return f"""<div class="overflow-x-auto"><table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">姓名</th><th class="px-4 py-3">性别</th><th class="px-4 py-3">手机号</th><th class="px-4 py-3">岗位</th><th class="px-4 py-3">基本工资</th><th class="px-4 py-3">销售提成</th><th class="px-4 py-3">状态</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table></div>"""


@router.get("/table", response_class=HTMLResponse)
def staff_table(db: Session = Depends(get_db)):
    members = db.query(Staff).order_by(Staff.id.desc()).limit(50).all()
    return _build_table(members)


@router.get("/search", response_class=HTMLResponse)
def staff_search(q: str = "", db: Session = Depends(get_db)):
    query = db.query(Staff)
    if q.strip():
        kw = q.strip()
        query = query.filter(Staff.name.contains(kw) | Staff.phone.contains(kw) | Staff.staff_id.contains(kw))
    return _build_table(query.order_by(Staff.id.desc()).limit(50).all())


@router.get("/active")
def staff_active(db: Session = Depends(get_db)):
    """获取所有在职员工（供跟进教练下拉使用）"""
    staffs = db.query(Staff).filter(
        or_(Staff.status == "在职", Staff.status == "")
    ).order_by(Staff.name).all()
    return [{"staff_id": s.staff_id, "name": s.name, "position": s.position or ""} for s in staffs]


@router.get("/search-json")
def staff_search_json(q: str = Query(""), db: Session = Depends(get_db)):
    """搜索员工，返回 JSON 列表"""
    query = db.query(Staff)
    kw = q.strip()
    if kw:
        query = query.filter(
            Staff.staff_id.contains(kw) |
            Staff.name.contains(kw) |
            Staff.phone.contains(kw)
        )
    return [
        {"staff_id": s.staff_id, "name": s.name, "phone": s.phone or "",
         "position": s.position or "", "status": s.status or ""}
        for s in query.order_by(Staff.staff_id).limit(50).all()
    ]


# ═══════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════

class StaffCreate(BaseModel):
    name: str = ""
    gender: Optional[str] = ""
    phone: Optional[str] = ""
    position: Optional[str] = ""
    base_salary: Optional[float] = 0
    sale_commission_rate: Optional[float] = 0
    class_commission_rate: Optional[float] = 0
    id_card: Optional[str] = ""
    bank_card: Optional[str] = ""
    remark: Optional[str] = ""
    store_id: Optional[str] = ""


class StaffOut(BaseModel):
    id: int
    staff_id: str
    name: str
    gender: str
    phone: str
    position: str
    status: str
    base_salary: float = 0
    sale_commission_rate: float = 0
    class_commission_rate: float = 0
    id_card: str = ""
    bank_card: str = ""
    remark: str = ""

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════

@router.get("", response_model=List[StaffOut])
def list_staff(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Staff)
    if keyword:
        query = query.filter(
            Staff.name.contains(keyword)
            | Staff.phone.contains(keyword)
            | Staff.staff_id.contains(keyword)
        )
    return query.order_by(Staff.id.desc()).offset(skip).limit(limit).all()


@router.get("/{staff_id}", response_model=StaffOut)
def get_staff(staff_id: str, db: Session = Depends(get_db)):
    staff = db.query(Staff).filter(Staff.staff_id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="员工不存在")
    return staff


@router.post("", response_model=StaffOut)
def create_staff(request: Request, data: StaffCreate, db: Session = Depends(get_db)):
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=422, detail="员工姓名不能为空")
    staff_id = generate_id("S", db, Staff.staff_id)
    staff = Staff(staff_id=staff_id, name=data.name.strip(), gender=data.gender,
                  phone=data.phone, position=data.position,
                  base_salary=data.base_salary or 0,
                  sale_commission_rate=data.sale_commission_rate or 0,
                  class_commission_rate=data.class_commission_rate or 0,
                  id_card=data.id_card or "", bank_card=data.bank_card or "",
                  remark=data.remark or "", status="在职",
                  store_id=data.store_id or "")
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.put("/{staff_id}", response_model=StaffOut)
def update_staff(staff_id: str, data: StaffCreate, db: Session = Depends(get_db)):
    staff = db.query(Staff).filter(Staff.staff_id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="员工不存在")
    for key, val in data.model_dump(exclude_unset=True).items():
        if val is not None:
            # name 不能清空
            if key == "name" and (not val or not val.strip()):
                continue
            setattr(staff, key, val.strip() if isinstance(val, str) else val)
    db.commit()
    db.refresh(staff)
    return staff


@router.delete("/{staff_id}")
def delete_staff(staff_id: str, request: Request, db: Session = Depends(get_db)):
    staff = db.query(Staff).filter(Staff.staff_id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="员工不存在")
    # 记录操作日志
    token = request.cookies.get("access_token", "")
    op = "系统"
    if token:
        from jose import jwt
        from backend.routers.auth import SECRET_KEY, ALGORITHM
        try:
            op = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub", "系统")
        except Exception:
            pass
    record_log(db, op, "delete", "员工", staff_id, f"删除员工：{staff.name}({staff_id})")
    db.delete(staff)
    db.commit()

    return {"success": True, "message": f"员工 {staff_id} 已删除"}
