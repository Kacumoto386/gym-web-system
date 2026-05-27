# -*- coding: utf-8 -*-
"""
数据分析看板 API 路由
提供 8 个 Chart.js JSON 端点
V3.9.0
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from backend.database import get_db
from backend.models.models import (
    Sale, MembershipCard, Recharge, ProductSale,
    FinanceIncome, FinanceExpense, Member, Checkin
)

router = APIRouter(prefix="/api/analytics", tags=["数据分析"])

TODAY = date.today()

_CHART_COLORS = {
    "blue": {"border": "#3B82F6", "bg": "rgba(59,130,246,0.2)"},
    "green": {"border": "#10B981", "bg": "rgba(16,185,129,0.2)"},
    "purple": {"border": "#8B5CF6", "bg": "rgba(139,92,246,0.2)"},
    "orange": {"border": "#F59E0B", "bg": "rgba(245,158,11,0.2)"},
    "red": {"border": "#EF4444", "bg": "rgba(239,68,68,0.2)"},
    "teal": {"border": "#14B8A6", "bg": "rgba(20,184,166,0.2)"},
    "pink": {"border": "#EC4899", "bg": "rgba(236,72,153,0.2)"},
    "indigo": {"border": "#6366F1", "bg": "rgba(99,102,241,0.2)"},
}

_DOUGHNUT_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899", "#14B8A6", "#6366F1"]


def _month_range_list(months: int):
    """生成最近 N 个月的 (year, month) 列表"""
    result = []
    for i in range(months - 1, -1, -1):
        m = TODAY.month - i
        y = TODAY.year
        while m < 1:
            m += 12
            y -= 1
        result.append((y, m))
    return result


def _month_start_end(year: int, month: int):
    """返回月的起始日期和结束日期"""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


# ═══════════════════════════════════════════
# 1. 营收趋势 (Line)
# ═══════════════════════════════════════════

@router.get("/revenue-trend")
def revenue_trend(months: int = Query(12, ge=1, le=36), db: Session = Depends(get_db)):
    labels = []
    data = []
    for y, m in _month_range_list(months):
        start, end = _month_start_end(y, m)
        total = 0
        for model, field, date_col in [
            (Sale, Sale.actual_amount, Sale.sale_date),
            (MembershipCard, MembershipCard.actual_amount, MembershipCard.start_date),
            (Recharge, Recharge.actual_amount, Recharge.recharge_date),
            (ProductSale, ProductSale.total_price, ProductSale.sale_date),
            (FinanceIncome, FinanceIncome.amount, FinanceIncome.income_date),
        ]:
            amt = db.query(func.coalesce(func.sum(field), 0)).filter(
                date_col >= start, date_col < end
            ).scalar() or 0
            total += float(amt)
        labels.append(f"{y}-{m:02d}")
        data.append(round(total, 2))
    return {
        "labels": labels,
        "datasets": [{
            "label": "月营收(元)", "data": data,
            "borderColor": _CHART_COLORS["blue"]["border"],
            "backgroundColor": _CHART_COLORS["blue"]["bg"],
            "fill": True, "tension": 0.3,
        }]
    }


# ═══════════════════════════════════════════
# 2. 营收构成 (Doughnut)
# ═══════════════════════════════════════════

@router.get("/revenue-composition")
def revenue_composition(year: int = 0, month: int = 0, db: Session = Depends(get_db)):
    y = year or TODAY.year
    m = month or TODAY.month
    start, end = _month_start_end(y, m)

    sources = []
    for model, field, date_col, label in [
        (Sale, Sale.actual_amount, Sale.sale_date, "售课收入"),
        (MembershipCard, MembershipCard.actual_amount, MembershipCard.start_date, "会籍卡"),
        (Recharge, Recharge.actual_amount, Recharge.recharge_date, "会员充值"),
        (ProductSale, ProductSale.total_price, ProductSale.sale_date, "商品零售"),
        (FinanceIncome, FinanceIncome.amount, FinanceIncome.income_date, "其他收入"),
    ]:
        amt = db.query(func.coalesce(func.sum(field), 0)).filter(
            date_col >= start, date_col < end
        ).scalar() or 0
        val = float(amt)
        if val > 0:
            sources.append({"label": label, "value": val})

    return {
        "labels": [s["label"] for s in sources],
        "datasets": [{
            "data": [s["value"] for s in sources],
            "backgroundColor": _DOUGHNUT_COLORS[:len(sources)],
        }]
    }


# ═══════════════════════════════════════════
# 3. 支出趋势 (Line)
# ═══════════════════════════════════════════

@router.get("/expense-trend")
def expense_trend(months: int = Query(12, ge=1, le=36), db: Session = Depends(get_db)):
    labels = []
    data = []
    for y, m in _month_range_list(months):
        start, end = _month_start_end(y, m)
        total = db.query(func.coalesce(func.sum(FinanceExpense.amount), 0)).filter(
            FinanceExpense.expense_date >= start,
            FinanceExpense.expense_date < end,
            FinanceExpense.voided == 0,
        ).scalar() or 0
        labels.append(f"{y}-{m:02d}")
        data.append(round(float(total), 2))
    return {
        "labels": labels,
        "datasets": [{
            "label": "月支出(元)", "data": data,
            "borderColor": _CHART_COLORS["red"]["border"],
            "backgroundColor": _CHART_COLORS["red"]["bg"],
            "fill": True, "tension": 0.3,
        }]
    }


# ═══════════════════════════════════════════
# 4. 收支对比 (Grouped Bar)
# ═══════════════════════════════════════════

@router.get("/income-vs-expense")
def income_vs_expense(months: int = Query(12, ge=1, le=36), db: Session = Depends(get_db)):
    labels = []
    income_data = []
    expense_data = []
    for y, m in _month_range_list(months):
        start, end = _month_start_end(y, m)
        # 收入
        inc = 0
        for model, field, date_col in [
            (Sale, Sale.actual_amount, Sale.sale_date),
            (MembershipCard, MembershipCard.actual_amount, MembershipCard.start_date),
            (Recharge, Recharge.actual_amount, Recharge.recharge_date),
            (ProductSale, ProductSale.total_price, ProductSale.sale_date),
            (FinanceIncome, FinanceIncome.amount, FinanceIncome.income_date),
        ]:
            amt = db.query(func.coalesce(func.sum(field), 0)).filter(
                date_col >= start, date_col < end
            ).scalar() or 0
            inc += float(amt)
        # 支出
        exp = db.query(func.coalesce(func.sum(FinanceExpense.amount), 0)).filter(
            FinanceExpense.expense_date >= start,
            FinanceExpense.expense_date < end,
            FinanceExpense.voided == 0,
        ).scalar() or 0
        labels.append(f"{y}-{m:02d}")
        income_data.append(round(inc, 2))
        expense_data.append(round(float(exp), 2))
    return {
        "labels": labels,
        "datasets": [
            {"label": "收入", "data": income_data,
             "backgroundColor": "rgba(16,185,129,0.6)", "borderColor": "#10B981"},
            {"label": "支出", "data": expense_data,
             "backgroundColor": "rgba(239,68,68,0.6)", "borderColor": "#EF4444"},
        ]
    }


# ═══════════════════════════════════════════
# 5. 会员增长 (Bar)
# ═══════════════════════════════════════════

@router.get("/member-growth")
def member_growth(months: int = Query(12, ge=1, le=36), db: Session = Depends(get_db)):
    labels = []
    data = []
    for y, m in _month_range_list(months):
        start, end = _month_start_end(y, m)
        cnt = db.query(Member).filter(
            Member.created_at >= start, Member.created_at < end
        ).count()
        labels.append(f"{y}-{m:02d}")
        data.append(cnt)
    return {
        "labels": labels,
        "datasets": [{
            "label": "新增会员", "data": data,
            "backgroundColor": "rgba(139,92,246,0.5)", "borderColor": "#8B5CF6",
        }]
    }


# ═══════════════════════════════════════════
# 6. 进场高峰时段 (Bar)
# ═══════════════════════════════════════════

@router.get("/peak-hours")
def peak_hours(year: int = 0, month: int = 0, db: Session = Depends(get_db)):
    y = year or TODAY.year
    m = month or TODAY.month
    start, end = _month_start_end(y, m)

    from sqlalchemy import cast, Integer

    rows = db.query(
        cast(func.substr(Checkin.checkin_time, 1, 2), Integer).label("hour"),
        func.count(Checkin.id).label("cnt"),
    ).filter(
        Checkin.checkin_date >= start,
        Checkin.checkin_date < end,
    ).group_by("hour").order_by("hour").all()

    hour_map = {r.hour: r.cnt for r in rows}
    labels = [f"{h:02d}:00" for h in range(6, 23)]  # 6:00 ~ 22:00
    data = [hour_map.get(h, 0) for h in range(6, 23)]

    return {
        "labels": labels,
        "datasets": [{
            "label": "进场人次",
            "data": data,
            "backgroundColor": "rgba(245,158,11,0.5)",
            "borderColor": "#F59E0B",
        }]
    }


# ═══════════════════════════════════════════
# 7. Top 10 课程 (Horizontal Bar)
# ═══════════════════════════════════════════

@router.get("/top-courses")
def top_courses(year: int = 0, month: int = 0, limit: int = Query(10, ge=5, le=20),
                db: Session = Depends(get_db)):
    y = year or TODAY.year
    m = month or TODAY.month
    start, end = _month_start_end(y, m)

    rows = db.query(
        Sale.course_name,
        func.coalesce(func.sum(Sale.actual_amount), 0).label("total"),
        func.count(Sale.id).label("cnt"),
    ).filter(
        Sale.sale_date >= start, Sale.sale_date < end, Sale.voided == 0,
        Sale.course_name != "",
    ).group_by(Sale.course_name).order_by(
        func.coalesce(func.sum(Sale.actual_amount), 0).desc()
    ).limit(limit).all()

    labels = [r.course_name for r in rows]
    data = [float(r.total) for r in rows]

    return {
        "labels": labels,
        "datasets": [{
            "label": "销售额(元)", "data": data,
            "backgroundColor": "rgba(16,185,129,0.5)", "borderColor": "#10B981",
        }]
    }


# ═══════════════════════════════════════════
# 8. 支付方式分布 (Doughnut)
# ═══════════════════════════════════════════

@router.get("/payment-methods")
def payment_methods(year: int = 0, month: int = 0, db: Session = Depends(get_db)):
    y = year or TODAY.year
    m = month or TODAY.month
    start, end = _month_start_end(y, m)

    rows = db.query(
        Sale.payment_method,
        func.coalesce(func.sum(Sale.actual_amount), 0).label("total"),
    ).filter(
        Sale.sale_date >= start, Sale.sale_date < end, Sale.voided == 0,
        Sale.payment_method != "",
    ).group_by(Sale.payment_method).order_by(
        func.coalesce(func.sum(Sale.actual_amount), 0).desc()
    ).all()

    labels = [r.payment_method for r in rows]
    data = [float(r.total) for r in rows]

    return {
        "labels": labels,
        "datasets": [{
            "data": data,
            "backgroundColor": _DOUGHNUT_COLORS[:len(labels)],
        }]
    }
