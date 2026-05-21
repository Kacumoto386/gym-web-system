# -*- coding: utf-8 -*-
"""
梯度提成 / 员工佣金 API 路由 + 页面
V3.1.3
"""
from fastapi import Request, APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from backend.database import get_db
from backend.models.models import CommissionTier, Staff, Sale, ClassRecord
from backend.services.id_gen import generate_id
from pydantic import BaseModel

router = APIRouter(prefix="/api/commission", tags=["梯度提成"])


# ═══════════════════════════════════════════
# 梯度规则 CRUD
# ═══════════════════════════════════════════

class TierCreate(BaseModel):
    type: str = "售课提成"
    min_amount: float = 0
    max_amount: float = 0
    rate: float = 0


class TierUpdate(BaseModel):
    min_amount: float = 0
    max_amount: float = 0
    rate: float = 0


def _tier_table_html(tiers: list) -> str:
    """渲染梯度规则表格"""
    if not tiers:
        return '<div class="text-center py-8 text-gray-400">暂无提成规则</div>'

    def _row(t):
        type_color = "blue" if t.type == "售课提成" else "green"
        min_s = f"¥{float(t.min_amount or 0):,.0f}" if t.min_amount else "¥0"
        max_s = f"¥{float(t.max_amount or 0):,.0f}" if t.max_amount else "无上限"
        rate_s = f"{float(t.rate or 0):.1f}%"
        return f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3"><span class="px-2 py-0.5 rounded text-xs font-medium bg-{type_color}-100 text-{type_color}-700">{t.type}</span></td>
            <td class="px-4 py-3 text-sm">{min_s}</td>
            <td class="px-4 py-3 text-sm">{max_s}</td>
            <td class="px-4 py-3 text-sm font-medium">{rate_s}</td>
            <td class="px-4 py-3 text-sm">
                <button class="text-blue-500 hover:text-blue-700 mr-2" onclick="editTier('{t.tier_id}', '{t.type}', {float(t.min_amount or 0)}, {float(t.max_amount or 0)}, {float(t.rate or 0)})">编辑</button>
                <button class="text-red-500 hover:text-red-700" hx-delete="/api/commission/tiers/{t.tier_id}" hx-target="#tierTable" hx-confirm="确认删除此规则？">删除</button>
            </td>
        </tr>"""

    trs = "\n".join(_row(t) for t in tiers)
    return f"""<div class="bg-white rounded-xl shadow-sm overflow-hidden">
    <table class="w-full">
        <thead class="bg-gray-50 border-b border-gray-200 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">类型</th><th class="px-4 py-3">下限</th><th class="px-4 py-3">上限</th><th class="px-4 py-3">提成比例</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>
</div>"""


@router.get("/tiers")
def tier_list_json(db: Session = Depends(get_db)):
    """梯度规则 JSON 列表（兼容旧接口）"""
    return tier_list(db)


@router.get("/tiers/table", response_class=HTMLResponse)
def tier_table(db: Session = Depends(get_db)):
    """梯度规则表格 HTML 片段"""
    tiers = db.query(CommissionTier).order_by(
        CommissionTier.type,
        CommissionTier.min_amount
    ).all()
    return _tier_table_html(tiers)


@router.get("/tiers/list")
def tier_list(db: Session = Depends(get_db)):
    """梯度规则 JSON 列表（供计算用）"""
    tiers = db.query(CommissionTier).order_by(
        CommissionTier.type,
        CommissionTier.min_amount
    ).all()
    return [
        {
            "tier_id": t.tier_id,
            "type": t.type,
            "min_amount": float(t.min_amount or 0),
            "max_amount": float(t.max_amount or 0),
            "rate": float(t.rate or 0),
        }
        for t in tiers
    ]


@router.post("/tiers")
def create_tier(data: TierCreate, db: Session = Depends(get_db)):
    """新增梯度规则"""
    tid = generate_id("T", db, CommissionTier.tier_id)
    t = CommissionTier(
        tier_id=tid,
        type=data.type,
        min_amount=data.min_amount,
        max_amount=data.max_amount,
        rate=data.rate,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"success": True}


@router.put("/tiers/{tier_id}")
def update_tier(tier_id: str, data: TierUpdate, db: Session = Depends(get_db)):
    """更新梯度规则"""
    t = db.query(CommissionTier).filter(CommissionTier.tier_id == tier_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="规则不存在")
    t.min_amount = data.min_amount
    t.max_amount = data.max_amount
    t.rate = data.rate
    db.commit()
    return {"success": True}


@router.delete("/tiers/{tier_id}")
def delete_tier(tier_id: str, db: Session = Depends(get_db)):
    """删除梯度规则"""
    t = db.query(CommissionTier).filter(CommissionTier.tier_id == tier_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="规则不存在")
    db.delete(t)
    db.commit()
    return {"success": True}


# ═══════════════════════════════════════════
# 佣金计算引擎
# ═══════════════════════════════════════════

def calc_tiered_commission(amount: float, tiers: list) -> dict:
    """
    分段累进提成计算
    tiers: [{"min_amount": 0, "max_amount": x, "rate": y}, ...]
    按金额分段，每段落入的区间按该段比例计算
    
    示例: 售课 120000
    [0, 30000) @5% → 1500
    [30000, 80000) @8% → 4000
    [80000, 150000) @10% → 4000
    = 9500
    """
    total = 0.0
    details = []
    remaining = amount

    for t in sorted(tiers, key=lambda x: x["min_amount"]):
        min_a = t["min_amount"]
        max_a = t["max_amount"]
        rate = t["rate"] / 100

        if remaining <= 0:
            break

        # 此段范围大小
        if max_a > 0:
            bracket = max_a - min_a
        else:
            bracket = float("inf")

        # 此段可计金额
        if remaining >= bracket:
            contrib = bracket
        else:
            contrib = remaining

        if contrib > 0 and rate > 0:
            comm = contrib * rate
        else:
            comm = 0.0

        total += comm
        remaining -= contrib
        details.append({
            "range": f"¥{min_a:,.0f}~{'¥'+f'{max_a:,.0f}' if max_a>0 else '以上'}",
            "rate": t["rate"],
            "contrib": round(contrib, 2),
            "commission": round(comm, 2),
        })

    return {
        "total": round(total, 2),
        "details": details,
        "base_amount": round(amount, 2),
    }


@router.get("/calculate")
def calculate_commission(
    staff_id: str = Query(""),
    year: int = Query(0),
    month: int = Query(0),
    db: Session = Depends(get_db),
):
    """计算指定员工指定月份的提成"""
    if not staff_id:
        raise HTTPException(status_code=400, detail="请选择员工")
    if not year or not month:
        today = date.today()
        year = year or today.year
        month = month or today.month

    # 员工信息
    staff = db.query(Staff).filter(Staff.staff_id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="员工不存在")

    # 当月售课记录（基于该员工有出售课记录）
    sales = db.query(Sale).filter(
        func.strftime("%Y", Sale.sale_date) == str(year),
        func.strftime("%m", Sale.sale_date) == f"{month:02d}",
        Sale.operator.contains(staff.name),
    ).all()

    # 当月上课记录
    class_records = db.query(ClassRecord).filter(
        func.strftime("%Y", ClassRecord.class_date) == str(year),
        func.strftime("%m", ClassRecord.class_date) == f"{month:02d}",
        ClassRecord.coach_id == staff_id,
    ).all()

    sale_total = sum(float(s.actual_amount or 0) for s in sales)
    class_count = len(class_records)

    # 获取梯度规则
    tiers = db.query(CommissionTier).order_by(
        CommissionTier.type,
        CommissionTier.min_amount
    ).all()

    sale_tiers = [{
        "min_amount": float(t.min_amount or 0),
        "max_amount": float(t.max_amount or 0),
        "rate": float(t.rate or 0),
    } for t in tiers if t.type == "售课提成"]

    # 上课按固定比例（没有梯度，用第一个上课规则的 rate 或取所有上课规则的平均）
    class_tiers_db = [t for t in tiers if t.type == "上课提成"]
    if class_tiers_db:
        # 使用最高一档上课提成比例
        class_tiers_db.sort(key=lambda t: float(t.min_amount or 0), reverse=True)
        class_rate = float(class_tiers_db[0].rate or 0)
    else:
        class_rate = 0

    sale_result = calc_tiered_commission(sale_total, sale_tiers)
    sale_commission = sale_result["total"]
    class_commission = round(class_count * class_rate / 100, 2) if class_rate > 0 else 0
    total_commission = round(sale_commission + class_commission, 2)

    return {
        "staff": {
            "staff_id": staff.staff_id,
            "name": staff.name,
            "position": staff.position or "",
        },
        "period": f"{year}年{month}月",
        "sale": {
            "count": len(sales),
            "total_amount": round(sale_total, 2),
            "commission": sale_commission,
            "details": sale_result["details"],
        },
        "class": {
            "count": class_count,
            "rate": class_rate,
            "commission": class_commission,
        },
        "total_commission": total_commission,
    }


@router.get("/staff-list")
def staff_list(db: Session = Depends(get_db)):
    """获取员工简表（下拉选择用）"""
    staffs = db.query(Staff).filter(
        (Staff.status == "在职") | (Staff.status == "")
    ).order_by(Staff.name).all()
    return [{"staff_id": s.staff_id, "name": s.name, "position": s.position or ""} for s in staffs]
