# -*- coding: utf-8 -*-
"""
收入支出报表 API 路由 + HTMX HTML 片段端点
V3.0.0
"""
from typing import Optional, List
from fastapi import Request,  APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from backend.database import get_db
from backend.models.models import FinanceIncome, FinanceExpense
from pydantic import BaseModel

router = APIRouter(prefix="/api/finance", tags=["财务报表"])


# ═══════════════════════════════════════════
# HTMX HTML 片段
# ═══════════════════════════════════════════

def _build_income_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无收入记录</div>'
    trs = ""
    for r in rows:
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{r.record_id}</td>
            <td class="px-4 py-3 text-sm">{r.income_date}</td>
            <td class="px-4 py-3 text-sm">{r.category or ''}</td>
            <td class="px-4 py-3 text-sm font-medium text-green-600">+{'%.2f' % (r.amount or 0)}</td>
            <td class="px-4 py-3 text-sm">{r.source or ''}</td>
            <td class="px-4 py-3 text-sm">{r.payment_method or ''}</td>
            <td class="px-4 py-3 text-sm">{r.remark or ''}</td>
            <td class="px-4 py-3 text-sm">
                <button class="text-red-500 hover:text-red-700" hx-delete="/api/finance/income/{r.record_id}" hx-target="#incomeTable" hx-confirm="确认删除？">删除</button>
            </td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">日期</th><th class="px-4 py-3">类别</th><th class="px-4 py-3">金额</th><th class="px-4 py-3">来源</th><th class="px-4 py-3">支付方式</th><th class="px-4 py-3">备注</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


def _build_expense_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无支出记录</div>'
    trs = ""
    for r in rows:
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{r.record_id}</td>
            <td class="px-4 py-3 text-sm">{r.expense_date}</td>
            <td class="px-4 py-3 text-sm">{r.category or ''}</td>
            <td class="px-4 py-3 text-sm font-medium text-red-600">-{'%.2f' % (r.amount or 0)}</td>
            <td class="px-4 py-3 text-sm">{r.payee or ''}</td>
            <td class="px-4 py-3 text-sm">{r.payment_method or ''}</td>
            <td class="px-4 py-3 text-sm">{r.remark or ''}</td>
            <td class="px-4 py-3 text-sm">
                <button class="text-red-500 hover:text-red-700" hx-delete="/api/finance/expense/{r.record_id}" hx-target="#expenseTable" hx-confirm="确认删除？">删除</button>
            </td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">日期</th><th class="px-4 py-3">类别</th><th class="px-4 py-3">金额</th><th class="px-4 py-3">收款方</th><th class="px-4 py-3">支付方式</th><th class="px-4 py-3">备注</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


def _build_summary(month_summary: tuple, income_count: int, expense_count: int) -> str:
    total_income, total_expense = month_summary
    net = total_income - total_expense
    net_cls = "text-green-600" if net >= 0 else "text-red-600"
    return f"""
    <div class="grid grid-cols-4 gap-3 mb-4">
        <div class="bg-green-50 rounded-lg p-3 border border-green-100">
            <div class="text-xs text-green-600">本月收入</div>
            <div class="text-lg font-bold text-green-700">+{total_income:,.0f}</div>
            <div class="text-xs text-green-500">{income_count} 笔</div>
        </div>
        <div class="bg-red-50 rounded-lg p-3 border border-red-100">
            <div class="text-xs text-red-600">本月支出</div>
            <div class="text-lg font-bold text-red-700">-{total_expense:,.0f}</div>
            <div class="text-xs text-red-500">{expense_count} 笔</div>
        </div>
        <div class="bg-blue-50 rounded-lg p-3 border border-blue-100">
            <div class="text-xs text-blue-600">本月净利</div>
            <div class="text-lg font-bold {net_cls}">{net:,.0f}</div>
        </div>
        <div class="bg-purple-50 rounded-lg p-3 border border-purple-100">
            <div class="text-xs text-purple-600">本月支出占比</div>
            <div class="text-lg font-bold text-purple-700">{'%.1f' % ((total_expense/total_income*100) if total_income else 0)}%</div>
        </div>
    </div>"""


@router.get("/income/table", response_class=HTMLResponse)
def income_table(year: int = 0, month: int = 0, db: Session = Depends(get_db)):
    query = db.query(FinanceIncome)
    if year and month:
        try:
            start = date(year, month, 1)
            if month == 12:
                end = date(year + 1, 1, 1)
            else:
                end = date(year, month + 1, 1)
            query = query.filter(FinanceIncome.income_date >= start, FinanceIncome.income_date < end)
        except:
            pass
    return _build_income_table(query.order_by(FinanceIncome.income_date.desc()).limit(200).all())


@router.get("/expense/table", response_class=HTMLResponse)
def expense_table(year: int = 0, month: int = 0, db: Session = Depends(get_db)):
    query = db.query(FinanceExpense)
    if year and month:
        try:
            start = date(year, month, 1)
            if month == 12:
                end = date(year + 1, 1, 1)
            else:
                end = date(year, month + 1, 1)
            query = query.filter(FinanceExpense.expense_date >= start, FinanceExpense.expense_date < end)
        except:
            pass
    return _build_expense_table(query.order_by(FinanceExpense.expense_date.desc()).limit(200).all())


@router.get("/summary", response_class=HTMLResponse)
def finance_summary(year: int = 0, month: int = 0, db: Session = Depends(get_db)):
    y = year or date.today().year
    m = month or date.today().month
    start = date(y, m, 1)
    end = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)

    total_income = db.query(func.coalesce(func.sum(FinanceIncome.amount), 0)).filter(
        FinanceIncome.income_date >= start, FinanceIncome.income_date < end).scalar()
    total_income = float(total_income)

    total_expense = db.query(func.coalesce(func.sum(FinanceExpense.amount), 0)).filter(
        FinanceExpense.expense_date >= start, FinanceExpense.expense_date < end).scalar()
    total_expense = float(total_expense)

    income_count = db.query(FinanceIncome).filter(
        FinanceIncome.income_date >= start, FinanceIncome.income_date < end).count()
    expense_count = db.query(FinanceExpense).filter(
        FinanceExpense.expense_date >= start, FinanceExpense.expense_date < end).count()

    return _build_summary((total_income, total_expense), income_count, expense_count)


# ═══════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════

class IncomeCreate(BaseModel):
    income_date: str = ""
    category: str = ""
    amount: float = 0
    source: str = ""
    payment_method: str = ""
    remark: str = ""


class ExpenseCreate(BaseModel):
    expense_date: str = ""
    category: str = ""
    amount: float = 0
    payee: str = ""
    payment_method: str = ""
    remark: str = ""


# ═══════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════

@router.get("/income")
def list_income(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
                year: Optional[int] = None, month: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(FinanceIncome)
    if year and month:
        try:
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            query = query.filter(FinanceIncome.income_date >= start, FinanceIncome.income_date < end)
        except:
            pass
    return query.order_by(FinanceIncome.income_date.desc()).offset(skip).limit(limit).all()


@router.get("/expense")
def list_expense(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
                 year: Optional[int] = None, month: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(FinanceExpense)
    if year and month:
        try:
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            query = query.filter(FinanceExpense.expense_date >= start, FinanceExpense.expense_date < end)
        except:
            pass
    return query.order_by(FinanceExpense.expense_date.desc()).offset(skip).limit(limit).all()


@router.post("/income")
def create_income(data: IncomeCreate, request: Request, db: Session = Depends(get_db)):
    from backend.services.id_gen import generate_id
    rid = generate_id("FI", db, FinanceIncome.record_id)
    d = date.fromisoformat(data.income_date) if data.income_date else date.today()
    r = FinanceIncome(record_id=rid, income_date=d, category=data.category or "",
                      amount=data.amount or 0, source=data.source or "",
                      payment_method=data.payment_method or "", remark=data.remark or "")
    db.add(r)
    db.commit()
    db.refresh(r)

    return {"success": True, "record_id": rid}


@router.post("/expense")
def create_expense(data: ExpenseCreate, request: Request, db: Session = Depends(get_db)):
    from backend.services.id_gen import generate_id
    rid = generate_id("FE", db, FinanceExpense.record_id)
    d = date.fromisoformat(data.expense_date) if data.expense_date else date.today()
    r = FinanceExpense(record_id=rid, expense_date=d, category=data.category or "",
                       amount=data.amount or 0, payee=data.payee or "",
                       payment_method=data.payment_method or "", remark=data.remark or "")
    db.add(r)
    db.commit()
    db.refresh(r)

    return {"success": True, "record_id": rid}


@router.delete("/income/{record_id}")
def delete_income(record_id: str, request: Request, db: Session = Depends(get_db)):
    r = db.query(FinanceIncome).filter(FinanceIncome.record_id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="收入记录不存在")
    db.delete(r)
    db.commit()

    return {"success": True}


@router.delete("/expense/{record_id}")
def delete_expense(record_id: str, request: Request, db: Session = Depends(get_db)):
    r = db.query(FinanceExpense).filter(FinanceExpense.record_id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="支出记录不存在")
    db.delete(r)
    db.commit()

    return {"success": True}
