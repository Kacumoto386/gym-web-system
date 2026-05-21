# -*- coding: utf-8 -*-
"""
会员充值 API 路由 + HTMX HTML 片段端点
V3.0.0
"""
from typing import Optional, List
from fastapi import Request,  APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import date
from backend.database import get_db
from backend.models.models import Recharge, Member
from backend.services.id_gen import generate_id
from pydantic import BaseModel

router = APIRouter(prefix="/api/recharges", tags=["充值管理"])


# ═══════════════════════════════════════════
# HTMX HTML 片段
# ═══════════════════════════════════════════

def _build_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无充值记录</div>'
    trs = ""
    for r in rows:
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{r.recharge_id}</td>
            <td class="px-4 py-3">{r.member_name or ''}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{r.member_id}</td>
            <td class="px-4 py-3 text-sm">{r.recharge_date}</td>
            <td class="px-4 py-3 text-sm font-medium text-green-600">+{r.amount or 0}</td>
            <td class="px-4 py-3 text-sm text-green-500">+{r.bonus or 0}</td>
            <td class="px-4 py-3 text-sm">{'%.2f' % (r.actual_amount or 0)}</td>
            <td class="px-4 py-3 text-sm">{r.payment_method or ''}</td>
            <td class="px-4 py-3 text-sm">{r.recharge_type or ''}</td>
            <td class="px-4 py-3 text-sm">{r.operator_id or ''}</td>
            <td class="px-4 py-3 text-sm">
                <button class="text-red-500 hover:text-red-700" hx-delete="/api/recharges/{r.recharge_id}" hx-target="#rechargeTable" hx-confirm="确认删除此充值记录？">删除</button>
            </td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">会员</th><th class="px-4 py-3">会员编号</th><th class="px-4 py-3">日期</th><th class="px-4 py-3">充值金额</th><th class="px-4 py-3">赠送金额</th><th class="px-4 py-3">实付</th><th class="px-4 py-3">支付方式</th><th class="px-4 py-3">类型</th><th class="px-4 py-3">经办人</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("/table", response_class=HTMLResponse)
def recharge_table(member_id: str = "", db: Session = Depends(get_db)):
    query = db.query(Recharge)
    if member_id:
        query = query.filter(Recharge.member_id == member_id)
    return _build_table(query.order_by(Recharge.recharge_date.desc()).limit(100).all())


# ═══════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════

class RechargeCreate(BaseModel):
    member_id: str
    member_name: str
    recharge_date: str  # ISO date
    amount: float = 0
    bonus: float = 0
    actual_amount: float = 0
    payment_method: str = ""
    recharge_type: str = "普通充值"
    operator_id: str = ""
    remark: str = ""


class RechargeOut(BaseModel):
    id: int
    recharge_id: str
    member_id: str
    member_name: str
    recharge_date: date
    amount: float
    bonus: float
    actual_amount: float
    payment_method: str
    recharge_type: str
    operator_id: str
    remark: str

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════

@router.get("", response_model=List[RechargeOut])
def list_recharges(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    member_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Recharge)
    if member_id:
        query = query.filter(Recharge.member_id == member_id)
    return query.order_by(Recharge.recharge_date.desc()).offset(skip).limit(limit).all()


@router.get("/{recharge_id}", response_model=RechargeOut)
def get_recharge(recharge_id: str, db: Session = Depends(get_db)):
    r = db.query(Recharge).filter(Recharge.recharge_id == recharge_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="充值记录不存在")
    return r


@router.post("", response_model=RechargeOut)
def create_recharge(data: RechargeCreate, db: Session = Depends(get_db)):
    recharge_id = generate_id("RC", db, Recharge.recharge_id)
    try:
        d = date.fromisoformat(data.recharge_date) if data.recharge_date else date.today()
    except ValueError:
        d = date.today()

    r = Recharge(
        recharge_id=recharge_id, recharge_date=d,
        member_id=data.member_id, member_name=data.member_name,
        amount=data.amount or 0, bonus=data.bonus or 0,
        actual_amount=data.actual_amount or 0,
        payment_method=data.payment_method or "",
        recharge_type=data.recharge_type or "普通充值",
        operator_id=data.operator_id or "",
        remark=data.remark or "",
    )
    db.add(r)

    # 更新会员余额
    member = db.query(Member).filter(Member.member_id == data.member_id).first()
    if member:
        member.balance = (member.balance or 0) + (data.amount or 0) + (data.bonus or 0)
        member.recharge_total = (member.recharge_total or 0) + (data.amount or 0) + (data.bonus or 0)

    db.commit()
    db.refresh(r)
    return r


@router.delete("/{recharge_id}")
def delete_recharge(recharge_id: str, request: Request, db: Session = Depends(get_db)):
    r = db.query(Recharge).filter(Recharge.recharge_id == recharge_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="充值记录不存在")
    # 反向扣减会员余额
    member = db.query(Member).filter(Member.member_id == r.member_id).first()
    if member:
        total = (r.amount or 0) + (r.bonus or 0)
        member.balance = max(0, (member.balance or 0) - total)
        member.recharge_total = max(0, (member.recharge_total or 0) - total)
    db.delete(r)
    db.commit()

    return {"success": True, "message": f"充值记录 {recharge_id} 已删除"}
