# -*- coding: utf-8 -*-
"""
会员充值 API 路由 + HTMX HTML 片段端点
V3.0.0
"""
from typing import Optional, List
from fastapi import Request,  APIRouter, Depends, HTTPException, Query, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import date, datetime
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
        voided = getattr(r, 'voided', 0)
        tr_class = 'hover:bg-gray-50 border-b'
        badge = ''
        actions = f"""<button class="text-red-500 hover:text-red-700" onclick="openVoidModal('{r.recharge_id}', '/api/recharges/{r.recharge_id}/void')">作废</button>"""
        if voided:
            tr_class = 'hover:bg-gray-50 border-b opacity-50'
            badge = ' <span class="inline-block bg-gray-200 text-gray-600 text-xs px-1.5 py-0.5 rounded ml-1">已作废</span>'
            actions = '<span class="text-gray-400 text-xs">已作废</span>'
        expiry = r.expiry_date.strftime('%Y-%m-%d') if r.expiry_date else ''
        order_balance = (r.amount or 0) + (r.bonus or 0)
        trs += f"""<tr class="{tr_class}">
            <td class="px-4 py-3 text-sm text-gray-500">{r.recharge_id}</td>
            <td class="px-4 py-3">{r.member_name or ''}{badge}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{r.member_id}</td>
            <td class="px-4 py-3 text-sm">{r.recharge_date}</td>
            <td class="px-4 py-3 text-sm font-medium text-green-600">+{r.amount or 0}</td>
            <td class="px-4 py-3 text-sm text-green-500">+{r.bonus or 0}</td>
            <td class="px-4 py-3 text-sm">{'%.2f' % (r.actual_amount or 0)}</td>
            <td class="px-4 py-3 text-sm">{r.payment_method or ''}</td>
            <td class="px-4 py-3 text-sm">{r.recharge_type or ''}</td>
            <td class="px-4 py-3 text-sm">{r.operator_id or ''}</td>
            <td class="px-4 py-3 text-sm">{expiry}</td>
            <td class="px-4 py-3 text-sm font-medium">¥{'%.2f' % order_balance}</td>
            <td class="px-4 py-3 text-sm">
                {actions}
            </td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">会员</th><th class="px-4 py-3">会员编号</th><th class="px-4 py-3">日期</th><th class="px-4 py-3">充值金额</th><th class="px-4 py-3">赠送金额</th><th class="px-4 py-3">实付</th><th class="px-4 py-3">支付方式</th><th class="px-4 py-3">类型</th><th class="px-4 py-3">经办人</th><th class="px-4 py-3">到期时间</th><th class="px-4 py-3">剩余余额(含赠金)</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("/table", response_class=HTMLResponse)
def recharge_table(member_id: str = "", db: Session = Depends(get_db)):
    query = db.query(Recharge).filter(Recharge.voided == 0)
    if member_id:
        query = query.filter(Recharge.member_id == member_id)
    return _build_table(query.order_by(Recharge.recharge_date.desc()).limit(100).all())


@router.get("/voided/table", response_class=HTMLResponse)
def voided_recharge_table(member_id: str = "", db: Session = Depends(get_db)):
    """已作废充值记录表格"""
    query = db.query(Recharge).filter(Recharge.voided == 1)
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
    expiry_date: str = ""
    remark: str = ""


class VoidRequest(BaseModel):
    reason: str = ""


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
    expiry_date: Optional[date] = None
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
def create_recharge(
    member_id: str = Form(...),
    member_name: str = Form(...),
    recharge_date: str = Form(""),
    amount: float = Form(0),
    bonus: float = Form(0),
    actual_amount: float = Form(0),
    payment_method: str = Form(""),
    recharge_type: str = Form("普通充值"),
    operator_id: str = Form(""),
    remark: str = Form(""),
    expiry_date: str = Form(""),
    db: Session = Depends(get_db),
):
    recharge_id = generate_id("RC", db, Recharge.recharge_id)
    try:
        d = date.fromisoformat(recharge_date) if recharge_date else date.today()
    except ValueError:
        d = date.today()

    r = Recharge(
        recharge_id=recharge_id, recharge_date=d,
        member_id=member_id, member_name=member_name,
        amount=amount or 0, bonus=bonus or 0,
        actual_amount=actual_amount or 0,
        payment_method=payment_method or "",
        recharge_type=recharge_type or "普通充值",
        operator_id=operator_id or "",
        remark=remark or "",
    )
    # 处理到期日期
    if expiry_date:
        try:
            r.expiry_date = date.fromisoformat(expiry_date)
        except ValueError:
            pass
    db.add(r)

    # 更新会员余额
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if member:
        from decimal import Decimal
        amt = Decimal(str(amount or 0)) + Decimal(str(bonus or 0))
        member.balance = (member.balance or Decimal(0)) + amt
        member.recharge_total = (member.recharge_total or Decimal(0)) + amt

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


@router.put("/{recharge_id}/void")
def void_recharge(recharge_id: str, data: VoidRequest, request: Request, db: Session = Depends(get_db)):
    """作废充值记录（标记作废 + 反向扣减会员余额）"""
    r = db.query(Recharge).filter(Recharge.recharge_id == recharge_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="充值记录不存在")
    if getattr(r, 'voided', 0):
        raise HTTPException(status_code=400, detail="该记录已作废")
    # 反向扣减会员余额
    member = db.query(Member).filter(Member.member_id == r.member_id).first()
    if member:
        total = (r.amount or 0) + (r.bonus or 0)
        member.balance = max(0, (member.balance or 0) - total)
        member.recharge_total = max(0, (member.recharge_total or 0) - total)
    # 获取操作人
    token = request.cookies.get("access_token", "")
    operator = "系统"
    if token:
        from jose import jwt
        from backend.routers.auth import SECRET_KEY, ALGORITHM
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            operator = payload.get("sub", "系统")
        except Exception:
            pass
    r.voided = 1
    r.void_reason = data.reason
    r.void_time = datetime.now()
    r.void_operator = operator
    db.commit()
    return {"success": True, "message": f"充值记录 {recharge_id} 已作废"}
