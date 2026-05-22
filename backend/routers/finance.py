# -*- coding: utf-8 -*-
"""
收入支出报表 API 路由 + HTMX HTML 片段端点
V3.6.8 — 日常办公支出记录工具
"""
from typing import Optional, List
from fastapi import Request,  APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from backend.database import get_db
from backend.models.models import FinanceIncome, FinanceExpense
from pydantic import BaseModel
import io, csv

router = APIRouter(prefix="/api/finance", tags=["财务报表"])

PAGE_SIZE = 50


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


class IncomeUpdate(BaseModel):
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


class ExpenseUpdate(BaseModel):
    expense_date: str = ""
    category: str = ""
    amount: float = 0
    payee: str = ""
    payment_method: str = ""
    remark: str = ""


# ═══════════════════════════════════════════
# HTMX HTML 片段 — 表格
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
                <button class="text-blue-600 hover:text-blue-800 mr-2" onclick="openEditIncome('{r.record_id}')">编辑</button>
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
                <button class="text-blue-600 hover:text-blue-800 mr-2" onclick="openEditExpense('{r.record_id}')">编辑</button>
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


def _build_pagination(page: int, total: int, total_pages: int) -> str:
    if total_pages <= 1:
        return ""
    pages_html = ""
    if total_pages <= 10:
        for p in range(1, total_pages + 1):
            if p == page:
                pages_html += f'<span class="px-2 py-1 bg-blue-600 text-white rounded text-xs font-medium">{p}</span>'
            else:
                pages_html += f'<button class="px-2 py-1 border rounded text-xs hover:bg-gray-100" onclick="goPage({p})">{p}</button>'
    else:
        items = [1]
        if page > 4:
            items.append("...")
        for p in range(max(2, page - 2), min(total_pages - 1, page + 2) + 1):
            items.append(p)
        if page < total_pages - 3:
            items.append("...")
        items.append(total_pages)
        for p in items:
            if p == "...":
                pages_html += '<span class="px-1 py-1 text-xs text-gray-400">…</span>'
            elif p == page:
                pages_html += f'<span class="px-2 py-1 bg-blue-600 text-white rounded text-xs font-medium">{p}</span>'
            else:
                pages_html += f'<button class="px-2 py-1 border rounded text-xs hover:bg-gray-100" onclick="goPage({p})">{p}</button>'
    prev_disabled = "opacity-50 cursor-not-allowed" if page <= 1 else "hover:bg-gray-100"
    next_disabled = "opacity-50 cursor-not-allowed" if page >= total_pages else "hover:bg-gray-100"
    prev_onclick = "" if page <= 1 else f'onclick="goPage({page-1})"'
    next_onclick = "" if page >= total_pages else f'onclick="goPage({page+1})"'
    return f"""<div class="flex items-center justify-between mt-3 pt-2 border-t">
        <span class="text-xs text-gray-500">共 {total} 条记录</span>
        <div class="flex items-center gap-1">
            <button class="px-2 py-1 border rounded text-xs {prev_disabled}" {prev_onclick}>上一页</button>
            {pages_html}
            <button class="px-2 py-1 border rounded text-xs {next_disabled}" {next_onclick}>下一页</button>
        </div>
    </div>"""


# ═══════════════════════════════════════════
# HTMX HTML 片段端点
# ═══════════════════════════════════════════

@router.get("/income/table", response_class=HTMLResponse)
def income_table(year: int = 0, month: int = 0, page: int = 1,
                 q: str = "", category: str = "", db: Session = Depends(get_db)):
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
    kw = q.strip()
    if kw:
        query = query.filter(
            FinanceIncome.source.contains(kw) |
            FinanceIncome.remark.contains(kw) |
            FinanceIncome.category.contains(kw)
        )
    if category:
        query = query.filter(FinanceIncome.category == category)
    total = query.count()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    rows = query.order_by(FinanceIncome.income_date.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    return _build_income_table(rows) + _build_pagination(page, total, total_pages)


@router.get("/expense/table", response_class=HTMLResponse)
def expense_table(year: int = 0, month: int = 0, page: int = 1,
                  q: str = "", category: str = "", db: Session = Depends(get_db)):
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
    kw = q.strip()
    if kw:
        query = query.filter(
            FinanceExpense.payee.contains(kw) |
            FinanceExpense.remark.contains(kw) |
            FinanceExpense.category.contains(kw)
        )
    if category:
        query = query.filter(FinanceExpense.category == category)
    total = query.count()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    rows = query.order_by(FinanceExpense.expense_date.desc()).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    return _build_expense_table(rows) + _build_pagination(page, total, total_pages)


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
# REST API — 列表/单条/创建/更新/删除
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


@router.get("/income/{record_id}")
def get_income(record_id: str, db: Session = Depends(get_db)):
    r = db.query(FinanceIncome).filter(FinanceIncome.record_id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="收入记录不存在")
    return r


@router.get("/expense/{record_id}")
def get_expense(record_id: str, db: Session = Depends(get_db)):
    r = db.query(FinanceExpense).filter(FinanceExpense.record_id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="支出记录不存在")
    return r


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


@router.put("/income/{record_id}")
def update_income(record_id: str, data: IncomeUpdate, db: Session = Depends(get_db)):
    r = db.query(FinanceIncome).filter(FinanceIncome.record_id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="收入记录不存在")
    for key, val in data.model_dump(exclude_unset=True).items():
        if key == "income_date" and val:
            val = date.fromisoformat(val)
        setattr(r, key, val)
    db.commit()
    db.refresh(r)
    return {"success": True, "record_id": r.record_id}


@router.put("/expense/{record_id}")
def update_expense(record_id: str, data: ExpenseUpdate, db: Session = Depends(get_db)):
    r = db.query(FinanceExpense).filter(FinanceExpense.record_id == record_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="支出记录不存在")
    for key, val in data.model_dump(exclude_unset=True).items():
        if key == "expense_date" and val:
            val = date.fromisoformat(val)
        setattr(r, key, val)
    db.commit()
    db.refresh(r)
    return {"success": True, "record_id": r.record_id}


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


# ═══════════════════════════════════════════
# CSV 导出
# ═══════════════════════════════════════════

@router.get("/export")
def export_finance_csv(type: str = Query("expense"), year: int = 0, month: int = 0,
                       q: str = "", category: str = "", db: Session = Depends(get_db)):
    if type == "income":
        model = FinanceIncome
        date_col = FinanceIncome.income_date
        headers = ["编号", "日期", "类别", "金额", "来源", "支付方式", "备注"]
        row_fn = lambda r: [r.record_id, str(r.income_date), r.category or "",
                            '%.2f' % (r.amount or 0), r.source or "",
                            r.payment_method or "", r.remark or ""]
    else:
        model = FinanceExpense
        date_col = FinanceExpense.expense_date
        headers = ["编号", "日期", "类别", "金额", "收款方", "支付方式", "备注"]
        row_fn = lambda r: [r.record_id, str(r.expense_date), r.category or "",
                            '%.2f' % (r.amount or 0), r.payee or "",
                            r.payment_method or "", r.remark or ""]

    query = db.query(model)
    if year and month:
        try:
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            query = query.filter(date_col >= start, date_col < end)
        except:
            pass
    kw = q.strip()
    if kw:
        if type == "income":
            query = query.filter(
                FinanceIncome.source.contains(kw) |
                FinanceIncome.remark.contains(kw) |
                FinanceIncome.category.contains(kw)
            )
        else:
            query = query.filter(
                FinanceExpense.payee.contains(kw) |
                FinanceExpense.remark.contains(kw) |
                FinanceExpense.category.contains(kw)
            )
    if category:
        query = query.filter(model.category == category)

    rows = query.order_by(date_col.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(row_fn(r))

    filename = f"finance_{type}_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
