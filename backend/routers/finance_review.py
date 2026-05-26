# -*- coding: utf-8 -*-
"""
支出审核 API 路由 + HTMX HTML 片段端点
V3.9.0
"""
from typing import Optional
from fastapi import Request, APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime
from backend.database import get_db
from backend.routers.operation_log import record_log
from backend.models.models import FinanceExpense
from backend.utils.pagination import paginate_query, build_pagination_html
from pydantic import BaseModel

router = APIRouter(prefix="/api/finance-review", tags=["支出审核"])

PAGE_SIZE = 50


class ReviewAction(BaseModel):
    reason: str = ""


# ═══════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════

def _get_operator(request: Request) -> str:
    token = request.cookies.get("access_token", "")
    if token:
        from jose import jwt
        from backend.routers.auth import SECRET_KEY, ALGORITHM
        try:
            return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub", "系统")
        except Exception:
            pass
    return "系统"


# ═══════════════════════════════════════════
# HTMX HTML 片段
# ═══════════════════════════════════════════

def _build_review_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无支出记录</div>'
    trs = ""
    for r in rows:
        status_cls = {
            "待审核": "bg-yellow-100 text-yellow-700",
            "已通过": "bg-green-100 text-green-700",
            "已驳回": "bg-red-100 text-red-700",
        }.get(r.approval_status or "已通过", "bg-gray-100 text-gray-700")

        if r.approval_status == "待审核":
            actions = (
                '<button class="text-green-600 hover:text-green-800 mr-2" '
                f'onclick="approveExpense(\'{r.record_id}\')">通过</button>'
                '<button class="text-red-500 hover:text-red-700" '
                f'onclick="rejectExpense(\'{r.record_id}\')">驳回</button>'
            )
        else:
            actions = f'<span class="text-gray-400 text-xs">{r.approval_status}</span>'

        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{r.record_id}</td>
            <td class="px-4 py-3 text-sm">{r.expense_date}</td>
            <td class="px-4 py-3 text-sm">{r.category or ''}</td>
            <td class="px-4 py-3 text-sm font-medium text-red-600">{'%.2f' % (r.amount or 0)}</td>
            <td class="px-4 py-3 text-sm">{r.payee or ''}</td>
            <td class="px-4 py-3 text-sm">{r.payment_method or ''}</td>
            <td class="px-4 py-3 text-sm">{r.remark or ''}</td>
            <td class="px-4 py-3 text-sm"><span class="px-2 py-0.5 {status_cls} rounded text-xs">{r.approval_status or '已通过'}</span></td>
            <td class="px-4 py-3 text-sm">{actions}</td>
        </tr>"""
    return f"""<div class="overflow-x-auto"><table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">日期</th><th class="px-4 py-3">类别</th><th class="px-4 py-3">金额</th><th class="px-4 py-3">收款方</th><th class="px-4 py-3">支付方式</th><th class="px-4 py-3">备注</th><th class="px-4 py-3">状态</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table></div>"""


def _build_stats(pending: int, approved: int, rejected: int) -> str:
    return f"""
    <div class="grid grid-cols-4 gap-3 mb-4">
        <div class="bg-yellow-50 rounded-lg p-3 border border-yellow-100">
            <div class="text-xs text-yellow-600">待审核</div>
            <div class="text-lg font-bold text-yellow-700">{pending}</div>
        </div>
        <div class="bg-green-50 rounded-lg p-3 border border-green-100">
            <div class="text-xs text-green-600">已通过</div>
            <div class="text-lg font-bold text-green-700">{approved}</div>
        </div>
        <div class="bg-red-50 rounded-lg p-3 border border-red-100">
            <div class="text-xs text-red-600">已驳回</div>
            <div class="text-lg font-bold text-red-700">{rejected}</div>
        </div>
        <div class="bg-blue-50 rounded-lg p-3 border border-blue-100">
            <div class="text-xs text-blue-600">总计</div>
            <div class="text-lg font-bold text-blue-700">{pending + approved + rejected}</div>
        </div>
    </div>"""


# ═══════════════════════════════════════════
# HTMX 端点
# ═══════════════════════════════════════════

@router.get("/table", response_class=HTMLResponse)
def review_table(
    status: str = "待审核",
    page: int = 1,
    q: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(FinanceExpense)
    if status:
        query = query.filter(FinanceExpense.approval_status == status)
    kw = q.strip()
    if kw:
        query = query.filter(
            FinanceExpense.payee.contains(kw) |
            FinanceExpense.remark.contains(kw) |
            FinanceExpense.category.contains(kw)
        )
    query = query.filter(FinanceExpense.voided == 0)
    rows, total, total_pages = paginate_query(
        query.order_by(FinanceExpense.expense_date.desc()), page, PAGE_SIZE
    )
    return _build_review_table(rows) + build_pagination_html(page, total, total_pages)


@router.get("/stats", response_class=HTMLResponse)
def review_stats(db: Session = Depends(get_db)):
    base = db.query(FinanceExpense).filter(FinanceExpense.voided == 0)
    pending = base.filter(FinanceExpense.approval_status == "待审核").count()
    approved = base.filter(FinanceExpense.approval_status == "已通过").count()
    rejected = base.filter(FinanceExpense.approval_status == "已驳回").count()
    return _build_stats(pending, approved, rejected)


# ═══════════════════════════════════════════
# REST API — 审核操作
# ═══════════════════════════════════════════

@router.put("/{record_id}/approve")
def approve_expense(record_id: str, request: Request, db: Session = Depends(get_db)):
    expense = db.query(FinanceExpense).filter(FinanceExpense.record_id == record_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="支出记录不存在")
    operator = _get_operator(request)
    expense.approval_status = "已通过"
    expense.approver = operator
    expense.approve_time = datetime.now()
    record_log(db, operator, "approve", "支出审核", record_id,
               f"审核通过支出：{expense.category} ¥{expense.amount}")
    db.commit()
    return {"success": True, "message": "已通过"}


@router.put("/{record_id}/reject")
def reject_expense(record_id: str, data: ReviewAction, request: Request, db: Session = Depends(get_db)):
    expense = db.query(FinanceExpense).filter(FinanceExpense.record_id == record_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="支出记录不存在")
    operator = _get_operator(request)
    expense.approval_status = "已驳回"
    expense.approver = operator
    expense.approve_time = datetime.now()
    record_log(db, operator, "reject", "支出审核", record_id,
               f"驳回支出：{expense.category} ¥{expense.amount} 原因：{data.reason}")
    db.commit()
    return {"success": True, "message": "已驳回"}
