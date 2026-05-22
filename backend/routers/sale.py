# -*- coding: utf-8 -*-
"""
售课记录 API 路由 + HTMX HTML 片段端点
V3.3.4 -- 细化展示：剩余课时 + 到期时间
"""
from typing import Optional, List
from fastapi import Request, APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from backend.database import get_db
from backend.models.models import Sale, LessonPackage
from backend.services.id_gen import generate_id
from pydantic import BaseModel

TODAY = date.today()

router = APIRouter(prefix="/api/sales", tags=["售课管理"])


# ═══════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════

def _remaining_tag(days):
    if days is None:
        return ''
    if days < 0:
        return ' <span class="text-red-500 text-xs font-medium">已过期</span>'
    elif days <= 0:
        return ' <span class="text-orange-500 text-xs font-medium">今日到期</span>'
    elif days <= 7:
        return ' <span class="text-orange-500 text-xs font-medium">剩{}天</span>'.format(days)
    elif days <= 30:
        return ' <span class="text-yellow-600 text-xs">剩{}天</span>'.format(days)
    return ''


def _get_lesson_info(db, sale):
    """获取售课的剩余课时和到期信息"""
    if not sale.member_id:
        return None, None, None
    # 查关联的 LessonPackage
    pkgs = db.query(LessonPackage).filter(
        LessonPackage.member_id == sale.member_id,
        LessonPackage.course_name.contains(sale.course_name or ''),
        LessonPackage.status.in_(["有效", "正常"]),
    ).order_by(LessonPackage.id.desc()).limit(5).all()

    remaining = None
    total = None
    used = None
    valid_until = None
    for p in pkgs:
        if p.remaining_hours and p.remaining_hours > 0:
            remaining = (remaining or 0) + p.remaining_hours
            total = (total or 0) + (p.total_hours or 0)
            used = (used or 0) + (p.used_hours or 0)
            if p.valid_until and (valid_until is None or p.valid_until > valid_until):
                valid_until = p.valid_until

    if remaining is None:
        # 无对应 LessonPackage 时回退到 Sale 自身的到期时间
        return sale.total_hours or 0, sale.total_hours or 0, sale.end_date
    # 即使有包但无到期时间，也回退到 Sale 自身的到期时间
    if valid_until is None and sale.end_date:
        valid_until = sale.end_date
    return remaining, total, valid_until


# ═══════════════════════════════════════════
# HTMX HTML 片段
# ═══════════════════════════════════════════

def _build_table(rows: list, db: Session = None) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无售课记录</div>'
    trs = ""
    for s in rows:
        payment_cls = {
            "已付款": "bg-green-100 text-green-700",
            "部分支付": "bg-yellow-100 text-yellow-700",
            "未付款": "bg-red-100 text-red-700",
        }.get(s.payment_status, "bg-gray-100 text-gray-700")

        # 关联查询剩余课时 + 到期
        if db:
            remaining, total_hours, valid_until = _get_lesson_info(db, s)
        else:
            remaining, total_hours, valid_until = None, None, None

        # 课时明细列
        if remaining is not None and total_hours is not None:
            remaining_tag = ''
            if remaining <= 3:
                remaining_tag = ' <span class="text-red-500 text-xs font-medium">即将用完</span>'
            elif remaining <= 0:
                remaining_tag = ' <span class="text-gray-400 text-xs">已用完</span>'
            lesson_col = '剩余 <span class="font-medium">{}</span> / 总 {} 时{}'.format(remaining, total_hours, remaining_tag)
        else:
            lesson_col = str(s.total_hours or 0) + ' 时'

        # 到期时间列
        if valid_until:
            days = (valid_until - TODAY).days
            tag = _remaining_tag(days)
            expire_col = str(valid_until) + tag
        else:
            expire_col = '<span class="text-gray-400">-</span>'

        trs += (
            '<tr class="hover:bg-gray-50 border-b">'
            '<td class="px-4 py-3 text-sm text-gray-500">{}</td>'
            '<td class="px-4 py-3">{}</td>'
            '<td class="px-4 py-3 text-sm text-gray-500">{}</td>'
            '<td class="px-4 py-3">{}</td>'
            '<td class="px-4 py-3 text-sm">{}</td>'
            '<td class="px-4 py-3 text-sm">{}</td>'
            '<td class="px-4 py-3 text-sm">{}</td>'
            '<td class="px-4 py-3 text-sm">{}</td>'
            '<td class="px-4 py-3 text-sm"><span class="px-2 py-0.5 {} rounded text-xs">{}</span></td>'
            '<td class="px-4 py-3 text-sm">{}</td>'
            '<td class="px-4 py-3 text-sm">'
            '<button class="text-blue-600 hover:text-blue-800 mr-2" onclick="alert(\'编辑功能开发中\')">编辑</button>'
            '<button class="text-red-500 hover:text-red-700" '
            'hx-delete="/api/sales/{}" hx-target="#saleTable" '
            'hx-confirm="确认删除售课记录？">删除</button>'
            '</td>'
            '</tr>'
        ).format(
            s.sale_id,
            s.member_name or '',
            s.member_id,
            s.course_name or '',
            lesson_col,
            expire_col,
            '\xa5{:.2f}'.format(s.actual_amount or 0),
            s.payment_method or '',
            payment_cls, s.payment_status or '',
            s.sale_date,
            s.sale_id,
        )
    return (
        '<table class="w-full bg-white rounded-lg shadow-sm">'
        '<thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">'
        '<tr>'
        '<th class="px-4 py-3">编号</th><th class="px-4 py-3">会员</th>'
        '<th class="px-4 py-3">会员号</th><th class="px-4 py-3">课程</th>'
        '<th class="px-4 py-3">课时</th><th class="px-4 py-3">到期</th>'
        '<th class="px-4 py-3">实收金额</th><th class="px-4 py-3">支付方式</th>'
        '<th class="px-4 py-3">状态</th><th class="px-4 py-3">日期</th>'
        '<th class="px-4 py-3">操作</th>'
        '</tr>'
        '</thead>'
        '<tbody>{}</tbody>'
        '</table>'
    ).format(trs)


@router.get("/table", response_class=HTMLResponse)
def sale_table(member_id: str = "", db: Session = Depends(get_db)):
    query = db.query(Sale)
    if member_id:
        query = query.filter(Sale.member_id == member_id)
    rows = query.order_by(Sale.id.desc()).limit(100).all()
    # Pass db to _build_table for lesson info lookup
    html = _build_table(rows, db)
    return HTMLResponse(content=html)


# ═══════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════

class SaleCreate(BaseModel):
    member_id: Optional[str] = ""
    member_name: str = ""
    member_phone: Optional[str] = ""
    course_id: Optional[str] = ""
    course_name: str = ""
    bought_hours: int = 1
    bonus_hours: int = 0
    unit_price: float = 0
    discount: float = 1
    total_price: float = 0
    actual_amount: float = 0
    deposit: float = 0
    payment_method: str = ""
    staff_id: Optional[str] = ""
    staff_name: Optional[str] = ""
    commission_rate: Optional[float] = 0
    source: Optional[str] = ""
    payment_status: str = "已付款"
    remark: Optional[str] = ""
    store_id: Optional[str] = ""
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class SaleOut(BaseModel):
    id: int
    sale_id: str
    member_id: str
    member_name: str
    course_name: str
    total_hours: int
    actual_amount: float
    payment_status: str

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════

@router.get("", response_model=List[SaleOut])
def list_sales(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    member_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Sale)
    if member_id:
        query = query.filter(Sale.member_id == member_id)
    return query.order_by(Sale.id.desc()).offset(skip).limit(limit).all()


@router.get("/{sale_id}", response_model=SaleOut)
def get_sale(sale_id: str, db: Session = Depends(get_db)):
    sale = db.query(Sale).filter(Sale.sale_id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="售课记录不存在")
    return sale


@router.post("", response_model=SaleOut)
def create_sale(request: Request, data: SaleCreate, db: Session = Depends(get_db)):
    sale_id = generate_id("SL", db, Sale.sale_id)
    total = data.bought_hours + data.bonus_hours
    sale = Sale(
        sale_id=sale_id, sale_date=date.today(),
        member_id=data.member_id, member_name=data.member_name,
        member_phone=data.member_phone or "",
        course_id=data.course_id, course_name=data.course_name,
        bought_hours=data.bought_hours, bonus_hours=data.bonus_hours or 0,
        total_hours=total, unit_price=data.unit_price or 0,
        discount=data.discount or 1, total_price=data.total_price or 0,
        actual_amount=data.actual_amount or 0, deposit=data.deposit or 0,
        payment_method=data.payment_method or "",
        staff_id=data.staff_id or "", staff_name=data.staff_name or "",
        commission_rate=data.commission_rate or 0,
        source=data.source or "", payment_status=data.payment_status or "已付款",
        remark=data.remark or "", store_id=data.store_id or "",
        start_date=data.start_date, end_date=data.end_date,
    )
    db.add(sale)
    db.commit()
    db.refresh(sale)
    return sale


@router.put("/{sale_id}", response_model=SaleOut)
def update_sale(sale_id: str, data: SaleCreate, db: Session = Depends(get_db)):
    sale = db.query(Sale).filter(Sale.sale_id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="售课记录不存在")
    for key, val in data.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(sale, key, val)
    db.commit()
    db.refresh(sale)
    return sale


@router.delete("/{sale_id}")
def delete_sale(sale_id: str, request: Request, db: Session = Depends(get_db)):
    sale = db.query(Sale).filter(Sale.sale_id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="售课记录不存在")
    db.delete(sale)
    db.commit()

    return {"success": True, "message": "售课记录 {} 已删除".format(sale_id)}
