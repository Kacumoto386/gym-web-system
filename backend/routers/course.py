# -*- coding: utf-8 -*-
"""
课程管理 API 路由 + HTMX HTML 片段端点
V3.2.5 — 批量操作 + 统计卡片 + 上架/下架切换 + 详情展开
"""
from typing import Optional, List
from fastapi import Request,  APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.models import Course
from backend.services.id_gen import generate_id
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api/courses", tags=["课程管理"])


# ═══════════════════════════════════════════
# HTMX HTML 片段
# ═══════════════════════════════════════════

def _type_badge(t: str) -> str:
    colors = {
        "私教课": "bg-purple-100 text-purple-700",
        "团课": "bg-orange-100 text-orange-700",
        "小班课": "bg-teal-100 text-teal-700",
        "体验课": "bg-pink-100 text-pink-700",
    }
    return colors.get(t, "bg-blue-100 text-blue-700")


def _status_badge(s: str) -> str:
    if s == "上架":
        return "bg-green-100 text-green-700"
    return "bg-gray-100 text-gray-700"


def _build_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无课程数据</div>'
    trs = ""
    for c in rows:
        type_cls = _type_badge(c.course_type)
        status_cls = _status_badge(c.status)
        trs += f"""<tr class="hover:bg-gray-50 border-b group">
            <td class="px-3 py-2.5">
                <input type="checkbox" class="batch-check rounded border-gray-300 text-blue-600" value="{c.course_id}">
            </td>
            <td class="px-3 py-2.5 text-sm text-gray-500">{c.course_id}</td>
            <td class="px-3 py-2.5 font-medium text-gray-800">{c.name}</td>
            <td class="px-3 py-2.5"><span class="px-2 py-0.5 {type_cls} rounded text-xs">{c.course_type or ''}</span></td>
            <td class="px-3 py-2.5 text-sm text-gray-600">{c.sport_type or '-'}</td>
            <td class="px-3 py-2.5 text-sm">{'%.2f' % (c.standard_price or 0)}</td>
            <td class="px-3 py-2.5 text-sm text-red-500">{'%.2f' % (c.discount_price or 0)}</td>
            <td class="px-3 py-2.5 text-sm">{c.standard_hours or 0} 节</td>
            <td class="px-3 py-2.5">
                <span class="status-badge px-2 py-0.5 {status_cls} rounded text-xs cursor-pointer"
                      onclick="toggleStatus('{c.course_id}')"
                      title="点击切换上架/下架">{c.status or '上架'}</span>
            </td>
            <td class="px-3 py-2.5 text-sm">
                <div class="flex gap-1">
                    <button class="text-blue-600 hover:text-blue-800 text-xs px-2 py-1 rounded hover:bg-blue-50"
                            onclick="openEditCourse('{c.course_id}')">编辑</button>
                    <button class="text-red-500 hover:text-red-700 text-xs px-2 py-1 rounded hover:bg-red-50"
                            hx-delete="/api/courses/{c.course_id}" hx-target="#courseTable"
                            hx-confirm="确认删除课程 {c.name}？">删除</button>
                </div>
            </td>
        </tr>
        <tr class="hidden border-b bg-gray-50/50" id="detail-{c.course_id}">
            <td colspan="10" class="px-6 py-3">
                <div class="grid grid-cols-4 gap-4 text-sm">
                    <div><span class="text-gray-400">教练</span><br><span class="text-gray-700">{c.coach or '-'}</span></div>
                    <div><span class="text-gray-400">上课地点</span><br><span class="text-gray-700">{c.location or '-'}</span></div>
                    <div><span class="text-gray-400">有效期</span><br><span class="text-gray-700">{c.valid_days or 0} 天</span></div>
                    <div><span class="text-gray-400">最大预约</span><br><span class="text-gray-700">{c.max_bookings or 0} 人</span></div>
                    <div class="col-span-2"><span class="text-gray-400">描述</span><br><span class="text-gray-700">{c.description or '-'}</span></div>
                    <div class="col-span-2"><span class="text-gray-400">备注</span><br><span class="text-gray-700">{c.remark or '-'}</span></div>
                </div>
            </td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr>
                <th class="px-3 py-3 w-8"><input type="checkbox" id="selectAll" class="rounded border-gray-300 text-blue-600" onchange="toggleSelectAll(this)"></th>
                <th class="px-3 py-3">编号</th>
                <th class="px-3 py-3">课程名</th>
                <th class="px-3 py-3">类型</th>
                <th class="px-3 py-3">运动类型</th>
                <th class="px-3 py-3">标准价</th>
                <th class="px-3 py-3">优惠价</th>
                <th class="px-3 py-3">课时</th>
                <th class="px-3 py-3">状态</th>
                <th class="px-3 py-3">操作</th>
            </tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


# ═══════════════════════════════════════════
# 统计卡片
# ═══════════════════════════════════════════

def _build_cards(rows: list) -> str:
    total = len(rows)
    online = sum(1 for c in rows if c.status == "上架")
    offline = total - online
    types = {}
    for c in rows:
        t = c.course_type or "其他"
        types[t] = types.get(t, 0) + 1
    type_list = "".join(
        f'<span class="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{t} {n}门</span>'
        for t, n in sorted(types.items(), key=lambda x: -x[1])
    )
    return f"""<div class="grid grid-cols-4 gap-4 mb-4">
        <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-blue-500">
            <div class="text-xs text-gray-400">总课程</div>
            <div class="text-2xl font-bold text-gray-800">{total}</div>
        </div>
        <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-green-500">
            <div class="text-xs text-gray-400">上架中</div>
            <div class="text-2xl font-bold text-green-600">{online}</div>
        </div>
        <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-gray-400">
            <div class="text-xs text-gray-400">已下架</div>
            <div class="text-2xl font-bold text-gray-500">{offline}</div>
        </div>
        <div class="bg-white rounded-lg shadow-sm p-4 border-l-4 border-purple-500">
            <div class="text-xs text-gray-400">类型分布</div>
            <div class="mt-1 flex flex-wrap gap-1">{type_list}</div>
        </div>
    </div>"""


@router.get("/cards", response_class=HTMLResponse)
def course_cards(db: Session = Depends(get_db)):
    return _build_cards(db.query(Course).order_by(Course.id.desc()).all())


@router.get("/table", response_class=HTMLResponse)
def course_table(db: Session = Depends(get_db)):
    return _build_table(db.query(Course).order_by(Course.id.desc()).limit(50).all())


@router.get("/search", response_class=HTMLResponse)
def course_search(q: str = "", course_type: str = "", db: Session = Depends(get_db)):
    query = db.query(Course)
    if q.strip():
        query = query.filter(Course.name.contains(q.strip()) | Course.course_id.contains(q.strip()))
    if course_type:
        query = query.filter(Course.course_type == course_type)
    return _build_table(query.order_by(Course.id.desc()).limit(50).all())


# ═══════════════════════════════════════════
# 批量操作
# ═══════════════════════════════════════════

class BatchAction(BaseModel):
    course_ids: List[str]
    action: str  # "online" | "offline" | "delete"


@router.post("/batch")
def batch_action(data: BatchAction, db: Session = Depends(get_db)):
    courses = db.query(Course).filter(Course.course_id.in_(data.course_ids)).all()
    if not courses:
        raise HTTPException(status_code=404, detail="未找到指定课程")
    count = len(courses)
    if data.action == "online":
        for c in courses:
            c.status = "上架"
    elif data.action == "offline":
        for c in courses:
            c.status = "下架"
    elif data.action == "delete":
        for c in courses:
            db.delete(c)
    else:
        raise HTTPException(status_code=400, detail=f"不支持的操作: {data.action}")
    db.commit()
    action_label = {"online": "上架", "offline": "下架", "delete": "删除"}
    return {"success": True, "message": f"已{action_label.get(data.action, data.action)}{count}个课程"}


# ═══════════════════════════════════════════
# 上架/下架切换
# ═══════════════════════════════════════════

@router.post("/{course_id}/toggle-status")
def toggle_status(course_id: str, db: Session = Depends(get_db)):
    c = db.query(Course).filter(Course.course_id == course_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="课程不存在")
    c.status = "下架" if c.status == "上架" else "上架"
    db.commit()
    return {"success": True, "status": c.status}


# ═══════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════

class CourseCreate(BaseModel):
    name: str
    sport_type: Optional[str] = ""
    course_type: Optional[str] = ""
    standard_hours: Optional[int] = 1
    standard_price: Optional[float] = 0
    discount_price: Optional[float] = 0
    valid_days: Optional[int] = 0
    max_bookings: Optional[int] = 0
    coach: Optional[str] = ""
    location: Optional[str] = ""
    description: Optional[str] = ""
    remark: Optional[str] = ""
    store_id: Optional[str] = ""


class CourseOut(BaseModel):
    id: int
    course_id: str
    name: str
    sport_type: str = ""
    course_type: str = ""
    standard_hours: int = 1
    standard_price: float = 0
    discount_price: float = 0
    valid_days: int = 0
    max_bookings: int = 0
    coach: str = ""
    location: str = ""
    description: str = ""
    status: str = ""
    remark: str = ""

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════

@router.get("", response_model=List[CourseOut])
def list_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    keyword: Optional[str] = None,
    course_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Course)
    if keyword:
        query = query.filter(Course.name.contains(keyword) | Course.course_id.contains(keyword))
    if course_type:
        query = query.filter(Course.course_type == course_type)
    return query.order_by(Course.id.desc()).offset(skip).limit(limit).all()


@router.get("/search-json")
def course_search_json(q: str = Query(""), db: Session = Depends(get_db)):
    """搜索课程，返回 JSON 列表"""
    query = db.query(Course)
    kw = q.strip()
    if kw:
        query = query.filter(
            Course.course_id.contains(kw) |
            Course.name.contains(kw)
        )
    return [
        {"course_id": c.course_id, "name": c.name, "standard_price": c.standard_price or 0,
         "standard_hours": c.standard_hours or 1, "course_type": c.course_type or ""}
        for c in query.order_by(Course.course_id).limit(50).all()
    ]


@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: str, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    return course


@router.post("", response_model=CourseOut)
def create_course(request: Request, data: CourseCreate, db: Session = Depends(get_db)):
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=422, detail="课程名称不能为空")
    course_id = generate_id("C", db, Course.course_id)
    course = Course(course_id=course_id, name=data.name.strip(),
                    sport_type=data.sport_type or "",
                    course_type=data.course_type or "",
                    standard_hours=data.standard_hours or 1,
                    standard_price=data.standard_price or 0,
                    discount_price=data.discount_price or 0,
                    valid_days=data.valid_days or 0, status="上架",
                    coach=data.coach or "", location=data.location or "",
                    description=data.description or "",
                    remark=data.remark or "", store_id=data.store_id or "")
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.put("/{course_id}", response_model=CourseOut)
def update_course(course_id: str, data: CourseCreate, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    for key, val in data.model_dump(exclude_unset=True).items():
        if val is not None:
            if key == "name" and (not val or not val.strip()):
                continue
            setattr(course, key, val.strip() if isinstance(val, str) else val)
    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}")
def delete_course(course_id: str, request: Request, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    db.delete(course)
    db.commit()
    return {"success": True, "message": f"课程 {course_id} 已删除"}
