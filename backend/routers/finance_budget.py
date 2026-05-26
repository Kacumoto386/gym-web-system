# -*- coding: utf-8 -*-
"""
预算管理 API 路由 + HTMX HTML 片段端点
V3.9.0
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend.models.models import Budget, FinanceIncome, FinanceExpense
from backend.services.id_gen import generate_id
from pydantic import BaseModel

router = APIRouter(prefix="/api/finance-budget", tags=["预算管理"])


class BudgetCreate(BaseModel):
    month: str = ""
    category: str = ""
    type: str = "expense"
    planned_amount: float = 0
    note: str = ""


class BudgetUpdate(BaseModel):
    planned_amount: float = 0
    note: str = ""


# ═══════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════

def _get_actual_by_category(month: str, type: str, db: Session) -> dict:
    """按类别聚合实际收入/支出金额"""
    result = {}
    year_str, month_str = month.split("-")
    y, m = int(year_str), int(month_str)
    start = __import__('datetime').date(y, m, 1)
    end = __import__('datetime').date(y + 1, 1, 1) if m == 12 else __import__('datetime').date(y, m + 1, 1)

    if type == "income":
        rows = db.query(
            FinanceIncome.category,
            func.coalesce(func.sum(FinanceIncome.amount), 0)
        ).filter(
            FinanceIncome.income_date >= start,
            FinanceIncome.income_date < end,
            FinanceIncome.voided == 0
        ).group_by(FinanceIncome.category).all()
    else:
        rows = db.query(
            FinanceExpense.category,
            func.coalesce(func.sum(FinanceExpense.amount), 0)
        ).filter(
            FinanceExpense.expense_date >= start,
            FinanceExpense.expense_date < end,
            FinanceExpense.voided == 0
        ).group_by(FinanceExpense.category).all()

    for cat, amt in rows:
        result[cat] = float(amt)
    return result


def _build_progress_bar(actual: float, planned: float) -> str:
    if planned <= 0:
        return '<div class="text-xs text-gray-400">未设置预算</div>'
    pct = min(actual / planned * 100, 200)
    color = "bg-green-500" if pct <= 100 else "bg-red-500"
    text_color = "text-green-600" if pct <= 100 else "text-red-600"
    return f"""
    <div class="flex items-center gap-2">
        <div class="flex-1 bg-gray-200 rounded-full h-2">
            <div class="{color} h-2 rounded-full" style="width:{'%.1f' % min(pct, 100)}%"></div>
        </div>
        <span class="text-xs {text_color} font-medium">{'%.1f' % pct}%</span>
    </div>"""


# ═══════════════════════════════════════════
# HTMX HTML 片段
# ═══════════════════════════════════════════

def _build_overview(total_planned: float, total_actual: float, count: int) -> str:
    diff = total_planned - total_actual
    diff_cls = "text-green-600" if diff >= 0 else "text-red-600"
    pct = (total_actual / total_planned * 100) if total_planned else 0
    return f"""
    <div class="grid grid-cols-4 gap-3 mb-4">
        <div class="bg-blue-50 rounded-lg p-3 border border-blue-100">
            <div class="text-xs text-blue-600">预算总计</div>
            <div class="text-lg font-bold text-blue-700">{'%.2f' % total_planned}</div>
        </div>
        <div class="bg-green-50 rounded-lg p-3 border border-green-100">
            <div class="text-xs text-green-600">实际总计</div>
            <div class="text-lg font-bold text-green-700">{'%.2f' % total_actual}</div>
        </div>
        <div class="{'bg-green-50' if diff >= 0 else 'bg-red-50'} rounded-lg p-3 border {'border-green-100' if diff >= 0 else 'border-red-100'}">
            <div class="text-xs {diff_cls}">预算偏差</div>
            <div class="text-lg font-bold {diff_cls}">{'+' if diff >= 0 else ''}{'%.2f' % diff}</div>
        </div>
        <div class="bg-purple-50 rounded-lg p-3 border border-purple-100">
            <div class="text-xs text-purple-600">执行率</div>
            <div class="text-lg font-bold text-purple-700">{'%.1f' % pct}%</div>
        </div>
    </div>"""


def _build_budget_table(rows: list, actual_map: dict) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无预算条目</div>'
    trs = ""
    for r in rows:
        actual = actual_map.get(r.category, 0)
        bar = _build_progress_bar(actual, r.planned_amount or 0)
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{r.budget_id}</td>
            <td class="px-4 py-3 text-sm">{r.category}</td>
            <td class="px-4 py-3 text-sm font-medium text-blue-600">{'%.2f' % (r.planned_amount or 0)}</td>
            <td class="px-4 py-3 text-sm font-medium text-green-600">{'%.2f' % actual}</td>
            <td class="px-4 py-3 text-sm">{bar}</td>
            <td class="px-4 py-3 text-xs text-gray-400">{r.note or ''}</td>
            <td class="px-4 py-3 text-sm">
                <button class="text-blue-600 hover:text-blue-800 mr-2" onclick="editBudget('{r.budget_id}')">编辑</button>
                <button class="text-red-500 hover:text-red-700" onclick="deleteBudget('{r.budget_id}')">删除</button>
            </td>
        </tr>"""
    return f"""<div class="overflow-x-auto"><table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">类别</th><th class="px-4 py-3">预算金额</th><th class="px-4 py-3">实际金额</th><th class="px-4 py-3">执行率</th><th class="px-4 py-3">备注</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table></div>"""


# ═══════════════════════════════════════════
# HTMX 端点
# ═══════════════════════════════════════════

@router.get("/overview", response_class=HTMLResponse)
def budget_overview(month: str = "", db: Session = Depends(get_db)):
    if not month:
        from datetime import date
        month = date.today().strftime("%Y-%m")
    budgets = db.query(Budget).filter(Budget.month == month).all()
    total_planned = sum(float(b.planned_amount or 0) for b in budgets)
    # 聚合实际金额（收入+支出）
    actual_map = {}
    actual_map.update(_get_actual_by_category(month, "income", db))
    actual_map.update(_get_actual_by_category(month, "expense", db))
    total_actual = sum(actual_map.get(b.category, 0) for b in budgets)
    return _build_overview(total_planned, total_actual, len(budgets))


@router.get("/table", response_class=HTMLResponse)
def budget_table(month: str = "", type: str = "expense", db: Session = Depends(get_db)):
    if not month:
        from datetime import date
        month = date.today().strftime("%Y-%m")
    rows = db.query(Budget).filter(
        Budget.month == month, Budget.type == type
    ).order_by(Budget.category).all()
    actual_map = _get_actual_by_category(month, type, db)
    return _build_budget_table(rows, actual_map)


# ═══════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════

@router.post("/create")
def create_budget(data: BudgetCreate, db: Session = Depends(get_db)):
    budget_id = generate_id("BG", db, Budget.budget_id)
    b = Budget(
        budget_id=budget_id,
        month=data.month,
        category=data.category,
        type=data.type,
        planned_amount=data.planned_amount or 0,
        note=data.note or "",
    )
    db.add(b)
    db.commit()
    return {"success": True, "budget_id": budget_id}


@router.put("/{budget_id}")
def update_budget(budget_id: str, data: BudgetUpdate, db: Session = Depends(get_db)):
    b = db.query(Budget).filter(Budget.budget_id == budget_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="预算条目不存在")
    b.planned_amount = data.planned_amount or 0
    b.note = data.note or ""
    db.commit()
    return {"success": True}


@router.delete("/{budget_id}")
def delete_budget(budget_id: str, db: Session = Depends(get_db)):
    b = db.query(Budget).filter(Budget.budget_id == budget_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="预算条目不存在")
    db.delete(b)
    db.commit()
    return {"success": True}
