# -*- coding: utf-8 -*-
"""
利润表 API 路由 + HTMX HTML 片段端点
跨模块营收/支出聚合 + 环比/同比
V3.9.0
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime
import io, csv
from backend.database import get_db
from backend.models.models import (
    Sale, MembershipCard, Recharge, ProductSale,
    FinanceIncome, FinanceExpense
)

router = APIRouter(prefix="/api/finance-profit", tags=["利润表"])

TODAY = date.today()


# ═══════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════

def _month_range(year: int, month: int):
    """返回 (month_start, month_end) 日期范围"""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def _get_month_revenue(year: int, month: int, db: Session) -> dict:
    """聚合指定月份的营收数据（跨5张表）"""
    start, end = _month_range(year, month)

    # Sale 售课收入
    sale_amt = db.query(func.coalesce(func.sum(Sale.actual_amount), 0)).filter(
        Sale.sale_date >= start, Sale.sale_date < end, Sale.voided == 0).scalar() or 0
    # MembershipCard 会籍卡收入
    card_amt = db.query(func.coalesce(func.sum(MembershipCard.actual_amount), 0)).filter(
        MembershipCard.start_date >= start, MembershipCard.start_date < end,
        MembershipCard.voided == 0).scalar() or 0
    # 如果 actual_amount 全为0（旧数据），回退到 price
    if float(card_amt) == 0:
        card_amt = db.query(func.coalesce(func.sum(MembershipCard.price), 0)).filter(
            MembershipCard.start_date >= start, MembershipCard.start_date < end,
            MembershipCard.voided == 0).scalar() or 0
    # Recharge 充值
    recharge_amt = db.query(func.coalesce(func.sum(Recharge.actual_amount), 0)).filter(
        Recharge.recharge_date >= start, Recharge.recharge_date < end,
        Recharge.voided == 0).scalar() or 0
    # ProductSale 商品零售
    product_amt = db.query(func.coalesce(func.sum(ProductSale.total_price), 0)).filter(
        ProductSale.sale_date >= start, ProductSale.sale_date < end,
        ProductSale.voided == 0).scalar() or 0
    # FinanceIncome 手动记账收入
    manual_amt = db.query(func.coalesce(func.sum(FinanceIncome.amount), 0)).filter(
        FinanceIncome.income_date >= start, FinanceIncome.income_date < end,
        FinanceIncome.voided == 0).scalar() or 0

    return {
        "售课收入": float(sale_amt),
        "会籍卡收入": float(card_amt),
        "会员充值": float(recharge_amt),
        "商品零售": float(product_amt),
        "其他收入": float(manual_amt),
    }


def _get_month_expense(year: int, month: int, db: Session) -> dict:
    """聚合指定月份的支出数据（跨2张表）"""
    start, end = _month_range(year, month)

    # FinanceExpense 手动记账支出
    manual_exp = db.query(func.coalesce(func.sum(FinanceExpense.amount), 0)).filter(
        FinanceExpense.expense_date >= start, FinanceExpense.expense_date < end,
        FinanceExpense.voided == 0).scalar() or 0
    # ProductSale 商品成本
    product_cost = db.query(func.coalesce(func.sum(ProductSale.cost_price), 0)).filter(
        ProductSale.sale_date >= start, ProductSale.sale_date < end,
        ProductSale.voided == 0).scalar() or 0

    return {
        "日常支出": float(manual_exp),
        "商品成本": float(product_cost),
    }


def _build_summary_cards(total_revenue: float, total_expense: float) -> str:
    net = total_revenue - total_expense
    net_cls = "text-green-600" if net >= 0 else "text-red-600"
    margin = (net / total_revenue * 100) if total_revenue else 0
    return f"""
    <div class="grid grid-cols-4 gap-3 mb-4">
        <div class="bg-green-50 rounded-lg p-3 border border-green-100">
            <div class="text-xs text-green-600">总收入</div>
            <div class="text-lg font-bold text-green-700">{'%.2f' % total_revenue}</div>
        </div>
        <div class="bg-red-50 rounded-lg p-3 border border-red-100">
            <div class="text-xs text-red-600">总支出</div>
            <div class="text-lg font-bold text-red-700">{'%.2f' % total_expense}</div>
        </div>
        <div class="{'bg-green-50' if net >= 0 else 'bg-red-50'} rounded-lg p-3 border {'border-green-100' if net >= 0 else 'border-red-100'}">
            <div class="text-xs {net_cls}">净利润</div>
            <div class="text-lg font-bold {net_cls}">{'%.2f' % net}</div>
        </div>
        <div class="bg-blue-50 rounded-lg p-3 border border-blue-100">
            <div class="text-xs text-blue-600">利润率</div>
            <div class="text-lg font-bold text-blue-700">{'%.1f' % margin}%</div>
        </div>
    </div>"""


def _build_breakdown_table(items: dict, title: str, fmt: str = "%.2f") -> str:
    if not items:
        return f'<div class="text-center py-4 text-gray-400">{title}暂无数据</div>'
    total = sum(items.values())
    trs = ""
    for name, amt in items.items():
        pct = (amt / total * 100) if total else 0
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm">{name}</td>
            <td class="px-4 py-3 text-sm font-medium">{fmt % amt}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{'%.1f' % pct}%</td>
        </tr>"""
    trs += f"""<tr class="bg-gray-50 font-medium">
        <td class="px-4 py-3 text-sm">合计</td>
        <td class="px-4 py-3 text-sm">{fmt % total}</td>
        <td class="px-4 py-3 text-sm">100%</td>
    </tr>"""
    return f"""<div class="overflow-x-auto"><table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">项目</th><th class="px-4 py-3">金额</th><th class="px-4 py-3">占比</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table></div>"""


def _build_comparison(current: float, previous: float, label: str) -> str:
    diff = current - previous
    pct = (diff / previous * 100) if previous else 0
    diff_cls = "text-green-600" if diff >= 0 else "text-red-600"
    return f"""<div class="bg-white rounded-lg p-3 border border-gray-100 text-center">
        <div class="text-xs text-gray-500 mb-1">{label}</div>
        <div class="text-sm">本期: <span class="font-medium">{'%.2f' % current}</span></div>
        <div class="text-sm">上期: <span class="font-medium">{'%.2f' % previous}</span></div>
        <div class="text-sm {diff_cls} font-medium">{'+' if diff >= 0 else ''}{'%.2f' % diff} ({'+' if pct >= 0 else ''}{'%.1f' % pct}%)</div>
    </div>"""


# ═══════════════════════════════════════════
# HTMX 端点
# ═══════════════════════════════════════════

@router.get("/summary", response_class=HTMLResponse)
def profit_summary(year: int = 0, month: int = 0, db: Session = Depends(get_db)):
    y = year or TODAY.year
    m = month or TODAY.month
    revenue_dict = _get_month_revenue(y, m, db)
    expense_dict = _get_month_expense(y, m, db)
    total_rev = sum(revenue_dict.values())
    total_exp = sum(expense_dict.values())
    return _build_summary_cards(total_rev, total_exp)


@router.get("/revenue-breakdown", response_class=HTMLResponse)
def revenue_breakdown(year: int = 0, month: int = 0, db: Session = Depends(get_db)):
    y = year or TODAY.year
    m = month or TODAY.month
    rev = _get_month_revenue(y, m, db)
    return _build_breakdown_table(rev, "营收")


@router.get("/expense-breakdown", response_class=HTMLResponse)
def expense_breakdown(year: int = 0, month: int = 0, db: Session = Depends(get_db)):
    y = year or TODAY.year
    m = month or TODAY.month
    exp = _get_month_expense(y, m, db)
    return _build_breakdown_table(exp, "支出")


@router.get("/mom-comparison", response_class=HTMLResponse)
def mom_comparison(year: int = 0, month: int = 0, db: Session = Depends(get_db)):
    y = year or TODAY.year
    m = month or TODAY.month
    # 当前月
    rev_cur = sum(_get_month_revenue(y, m, db).values())
    exp_cur = sum(_get_month_expense(y, m, db).values())
    net_cur = rev_cur - exp_cur
    # 上个月
    py, pm = (y - 1, 12) if m == 1 else (y, m - 1)
    rev_prev = sum(_get_month_revenue(py, pm, db).values())
    exp_prev = sum(_get_month_expense(py, pm, db).values())
    net_prev = rev_prev - exp_prev

    html = '<div class="grid grid-cols-3 gap-3">'
    html += _build_comparison(rev_cur, rev_prev, "营收环比")
    html += _build_comparison(exp_cur, exp_prev, "支出环比")
    html += _build_comparison(net_cur, net_prev, "净利润环比")
    html += '</div>'
    return html


@router.get("/yoy-comparison", response_class=HTMLResponse)
def yoy_comparison(year: int = 0, month: int = 0, db: Session = Depends(get_db)):
    y = year or TODAY.year
    m = month or TODAY.month
    # 今年本月
    rev_cur = sum(_get_month_revenue(y, m, db).values())
    exp_cur = sum(_get_month_expense(y, m, db).values())
    net_cur = rev_cur - exp_cur
    # 去年同月
    rev_prev = sum(_get_month_revenue(y - 1, m, db).values())
    exp_prev = sum(_get_month_expense(y - 1, m, db).values())
    net_prev = rev_prev - exp_prev

    html = '<div class="grid grid-cols-3 gap-3">'
    html += _build_comparison(rev_cur, rev_prev, "营收同比")
    html += _build_comparison(exp_cur, exp_prev, "支出同比")
    html += _build_comparison(net_cur, net_prev, "净利润同比")
    html += '</div>'
    return html


@router.get("/export")
def export_profit(year: int = 0, month: int = 0):
    """CSV 导出利润表（同步函数，返回 StreamingResponse）"""
    from backend.database import SessionLocal
    y = year or TODAY.year
    m = month or TODAY.month

    db = SessionLocal()
    try:
        rev = _get_month_revenue(y, m, db)
        exp = _get_month_expense(y, m, db)
        total_rev = sum(rev.values())
        total_exp = sum(exp.values())
        net = total_rev - total_exp

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["利润表", f"{y}年{m}月"])
        w.writerow([])
        w.writerow(["项目", "金额", "占比"])
        for name, amt in rev.items():
            pct = (amt / total_rev * 100) if total_rev else 0
            w.writerow([f"营收-{name}", f"{amt:.2f}", f"{pct:.1f}%"])
        w.writerow(["营收合计", f"{total_rev:.2f}", "100%"])
        w.writerow([])
        for name, amt in exp.items():
            pct = (amt / total_exp * 100) if total_exp else 0
            w.writerow([f"支出-{name}", f"{amt:.2f}", f"{pct:.1f}%"])
        w.writerow(["支出合计", f"{total_exp:.2f}", "100%"])
        w.writerow([])
        w.writerow(["净利润", f"{net:.2f}", ""])
        margin = (net / total_rev * 100) if total_rev else 0
        w.writerow(["利润率", f"{margin:.1f}%", ""])

        csv_content = buf.getvalue()
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=profit_{y}{m:02d}.csv",
                "Content-Type": "text/csv; charset=utf-8-sig",
            },
        )
    finally:
        db.close()
