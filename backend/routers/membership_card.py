# -*- coding: utf-8 -*-
"""
会籍卡管理 API 路由 + HTMX HTML 片段端点
V3.3.4 -- 细化数据展示：剩余次数/余额 + 到期提示
"""
from typing import Optional, List
from fastapi import Request, APIRouter, Depends, HTTPException, Query, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from backend.database import get_db
from backend.routers.operation_log import record_log
from backend.models.models import MembershipCard
from backend.services.id_gen import generate_id
from pydantic import BaseModel

TODAY = date.today()


class VoidRequest(BaseModel):
    reason: str = ""

router = APIRouter(prefix="/api/membership-cards", tags=["会籍卡管理"])


# ═══════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════

def _card_type_label(t):
    m = {"次卡": "bg-blue-100 text-blue-700", "期限卡": "bg-green-100 text-green-700", "现金卡": "bg-yellow-100 text-yellow-700"}
    cls = m.get(t, "bg-gray-100 text-gray-700")
    return '<span class="px-2 py-0.5 {} rounded text-xs">{}</span>'.format(cls, t)


def _prod_content(c):
    """卡产品「内容」列"""
    if c.card_type == "次卡":
        parts = [str(c.total_classes or 0) + "次"]
        if c.bonus_classes:
            parts.append("+赠" + str(c.bonus_classes))
        return ''.join(parts)
    elif c.card_type == "现金卡":
        if c.face_value:
            return '面值 \xa5{:.0f} / 储值 \xa5{:.0f}'.format(c.face_value, c.price)
        else:
            return '储值 \xa5{:.0f}'.format(c.price)
    else:
        return str(c.duration_days) + '天'


def _calc_remaining_days(end_date_val):
    """计算剩余天数"""
    if not end_date_val:
        return None
    if isinstance(end_date_val, str):
        try:
            end = date.fromisoformat(end_date_val)
        except ValueError:
            return None
    else:
        end = end_date_val
    return (end - TODAY).days


def _remaining_tag(days):
    """生成剩余天数标签 HTML"""
    if days is None:
        return '<span class="text-gray-400">-</span>'
    if days < 0:
        return '<span class="text-red-500 font-medium">已过期</span>'
    elif days == 0:
        return '<span class="text-orange-500 font-medium">今日到期</span>'
    elif days <= 7:
        return '<span class="text-orange-500 font-medium">剩 {} 天</span>'.format(days)
    elif days <= 30:
        return '<span class="text-yellow-600">剩 {} 天</span>'.format(days)
    else:
        return '<span class="text-gray-400">{} 天</span>'.format(days)


def _card_sold_summary(c):
    """生成已售会籍的剩余信息: (剩余HTML, 剩余数值)"""
    ct = (c.card_type or "").strip()
    price = float(c.price or 0)
    consumed = float(c.consumed_amount or 0)

    if "次卡" in ct or (c.total_classes and c.total_classes > 0):
        total = c.total_classes or 0
        bonus = c.bonus_classes or 0
        total_with = total + bonus
        if total_with > 0:
            unit_val = price / total_with if total_with > 0 else 0
            used_count = round(consumed / unit_val) if unit_val > 0 else 0
            remaining = max(total_with - used_count, 0)
            if bonus:
                desc = '<span class="font-medium">{}/{}+{}</span> 次'.format(remaining, total, bonus)
            else:
                desc = '<span class="font-medium">{}/{}</span> 次'.format(remaining, total)
            return desc, remaining
        return '<span class="text-gray-400">{} 次</span>'.format(total), 0

    if "现金" in ct or float(c.face_value or 0) > 0:
        remaining_bal = max(price - consumed, 0)
        face_val = float(c.face_value or 0)
        if face_val > 0:
            desc = '余额 <span class="font-medium text-green-600">\xa5{:.0f}</span> / 面值 \xa5{:.0f}'.format(remaining_bal, face_val)
        else:
            desc = '余额 <span class="font-medium text-green-600">\xa5{:.0f}</span>'.format(remaining_bal)
        return desc, remaining_bal

    # 期限卡 / 默认
    days_remain = _calc_remaining_days(c.end_date)
    if days_remain is not None and days_remain >= 0:
        desc = '剩余 <span class="font-medium">{}</span> 天 / {} 天'.format(days_remain, c.duration_days or 0)
        return desc, days_remain
    return '<span class="text-gray-400">-</span>', 0


def _sold_content(c):
    """售卡内容/面值（简版）"""
    if c.card_type == "次卡":
        parts = [str(c.total_classes or 0) + "次"]
        if c.bonus_classes:
            parts.append("(赠" + str(c.bonus_classes) + ")")
        return ''.join(parts)
    elif c.card_type == "现金":
        if c.face_value:
            return '面值 \xa5{:.0f} / 售价 \xa5{:.0f}'.format(c.face_value, c.price)
        else:
            return '售价 \xa5{:.0f}'.format(c.price)
    else:
        return str(c.duration_days) + '天'


# ═══════════════════════════════════════════
# HTMX HTML 片段
# ═══════════════════════════════════════════

def _build_products_table(rows: list) -> str:
    """卡产品表格"""
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无卡产品，请添加</div>'
    trs = ""
    for c in rows:
        content = _prod_content(c)
        trs += (
            '<tr class="hover:bg-gray-50 border-b">'
            '<td class="px-4 py-3">{}</td>'
            '<td class="px-4 py-3">{}</td>'
            '<td class="px-4 py-3">{}</td>'
            '<td class="px-4 py-3 text-sm">{}</td>'
            '<td class="px-4 py-3 text-sm">{}天</td>'
            '<td class="px-4 py-3 text-sm">\xa5{:.2f}</td>'
            '<td class="px-4 py-3 text-sm">'
            '<button class="text-red-500 hover:text-red-700" '
            'hx-delete="/api/membership-cards/products/{}" '
            'hx-target="#cardProductTable" hx-confirm="确认删除此卡产品？">删除</button>'
            '</td>'
            '</tr>'
        ).format(c.card_id, c.card_name or c.remark or '', _card_type_label(c.card_type),
                 content, c.duration_days or 0, c.price, c.card_id)
    return (
        '<table class="w-full bg-white rounded-lg shadow-sm">'
        '<thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">'
        '<tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">名称</th>'
        '<th class="px-4 py-3">类型</th><th class="px-4 py-3">内容</th>'
        '<th class="px-4 py-3">有效期</th><th class="px-4 py-3">售价</th>'
        '<th class="px-4 py-3">操作</th></tr>'
        '</thead>'
        '<tbody>{}</tbody>'
        '</table>'
    ).format(trs)


def _build_sold_table(rows: list) -> str:
    """售卡表格 — 细化展示：剩余次数/余额 + 到期提示"""
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无已售会籍卡</div>'
    trs = ""
    for c in rows:
        status_cls = "bg-green-100 text-green-700" if c.status == "有效" else "bg-red-100 text-red-700"
        content = _sold_content(c)
        summary_desc, summary_val = _card_sold_summary(c)
        remaining_days = _calc_remaining_days(c.end_date)
        remaining_tag = _remaining_tag(remaining_days)

        # 截止列：日期 + 到期标签
        if remaining_days is not None:
            end_col = str(c.end_date) + '<br>' + remaining_tag
        else:
            end_col = str(c.end_date or "-")

        # 状态细化
        ct = (c.card_type or "").strip()
        is_exhausted = False
        if "次卡" in ct or (c.total_classes and c.total_classes > 0):
            total = c.total_classes or 0
            if total > 0 and summary_val <= 0:
                is_exhausted = True
        if "现金" in ct or float(c.face_value or 0) > 0:
            if summary_val <= 0:
                is_exhausted = True

        is_voided = getattr(c, 'voided', 0)
        if is_voided:
            display_status = "已作废"
            st_cls = "bg-gray-200 text-gray-500"
            row_cls = "hover:bg-gray-50 border-b opacity-50"
            action_col = '<span class="text-gray-400 text-xs">已作废</span>'
        else:
            if is_exhausted and c.status == "有效":
                display_status = "已用完"
                st_cls = "bg-gray-100 text-gray-500"
            else:
                display_status = c.status or ''
                st_cls = status_cls
            row_cls = "hover:bg-gray-50 border-b"
            action_col = (
                '<button class="text-red-500 hover:text-red-700" '
                'onclick="openVoidModal(\'{cid}\', \'/api/membership-cards/sold/{cid}/void\')">作废</button>'
            )

        row = (
            '<tr class="{row_cls}">'
            '<td class="px-4 py-3 text-sm text-gray-500">{card_id}</td>'
            '<td class="px-4 py-3">{member_name}</td>'
            '<td class="px-4 py-3 text-sm text-gray-500">{member_id}</td>'
            '<td class="px-4 py-3">{card_type_label}</td>'
            '<td class="px-4 py-3 text-sm">{card_content}</td>'
            '<td class="px-4 py-3 text-sm">{remaining_col}</td>'
            '<td class="px-4 py-3 text-sm">{duration}d</td>'
            '<td class="px-4 py-3 text-sm">{price_str}</td>'
            '<td class="px-4 py-3 text-sm">{start}</td>'
            '<td class="px-4 py-3 text-sm">{end_col}</td>'
            '<td class="px-4 py-3 text-sm"><span class="px-2 py-0.5 {st_cls} rounded text-xs">{status_display}</span></td>'
            '<td class="px-4 py-3 text-sm">{action_col}</td>'
            '</tr>'
        ).format(
            card_id=c.card_id,
            member_name=c.member_name or '',
            member_id=c.member_id,
            card_type_label=_card_type_label(c.card_type),
            card_content=content,
            remaining_col=summary_desc,
            duration=c.duration_days or 0,
            price_str='\xa5{:.2f}'.format(c.price),
            start=c.start_date,
            end_col=end_col,
            st_cls=st_cls,
            status_display=display_status,
            row_cls=row_cls,
            action_col=action_col,
        )
        trs += row

    return (
        '<table class="w-full bg-white rounded-lg shadow-sm">'
        '<thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">'
        '<tr>'
        '<th class="px-4 py-3">编号</th><th class="px-4 py-3">会员</th>'
        '<th class="px-4 py-3">会员号</th><th class="px-4 py-3">类型</th>'
        '<th class="px-4 py-3">内容/面值</th><th class="px-4 py-3">剩余</th>'
        '<th class="px-4 py-3">有效期</th><th class="px-4 py-3">售价</th>'
        '<th class="px-4 py-3">开始</th><th class="px-4 py-3">截止</th>'
        '<th class="px-4 py-3">状态</th><th class="px-4 py-3">操作</th>'
        '</tr>'
        '</thead>'
        '<tbody>{}</tbody>'
        '</table>'
    ).format(trs)


# ═══════════════════════════════════════════
# 卡产品 - HTMX 片段端点
# ═══════════════════════════════════════════

@router.get("/products/table", response_class=HTMLResponse)
def product_table(db: Session = Depends(get_db)):
    q = db.query(MembershipCard).filter(MembershipCard.is_product == 1).order_by(MembershipCard.id.desc()).all()
    return _build_products_table(q)


@router.get("/sold/table", response_class=HTMLResponse)
def sold_table(member_id: str = "", db: Session = Depends(get_db)):
    q = db.query(MembershipCard).filter(MembershipCard.is_product == 0, MembershipCard.voided == 0)
    if member_id:
        q = q.filter(MembershipCard.member_id == member_id)
    return _build_sold_table(q.order_by(MembershipCard.id.desc()).limit(100).all())


# ═══════════════════════════════════════════
# 卡产品 API
# ═══════════════════════════════════════════

@router.get("/products/list")
def list_products(db: Session = Depends(get_db)):
    """返回所有卡产品（用于售卡下拉选择）"""
    q = db.query(MembershipCard).filter(MembershipCard.is_product == 1).order_by(MembershipCard.id.desc()).all()
    return [{
        "card_id": c.card_id,
        "name": c.card_name or c.remark or "",
        "card_type": c.card_type,
        "duration_days": c.duration_days or 0,
        "price": float(c.price or 0),
        "total_classes": c.total_classes or 0,
        "bonus_classes": c.bonus_classes or 0,
        "face_value": float(c.face_value or 0),
    } for c in q]


@router.post("/products")
def create_product(
    card_type: str = Form(...),
    name: str = Form(""),
    duration_days: int = Form(30),
    total_classes: int = Form(0),
    bonus_classes: int = Form(0),
    face_value: float = Form(0.0),
    price: float = Form(0.0),
    db: Session = Depends(get_db),
):
    """创建卡产品（新增现金卡面值 + 次卡赠送次数）"""
    card_id = generate_id("CP", db, MembershipCard.card_id)
    c = MembershipCard(
        card_id=card_id, member_id="-", member_name="",
        card_type=card_type,
        duration_days=duration_days or 0,
        total_classes=total_classes or 0,
        bonus_classes=bonus_classes or 0,
        face_value=face_value or 0,
        price=price or 0,
        start_date=date.today(), end_date=None,
        status="正常", remark=name or "",
        is_product=1,
        card_name=name or "",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"success": True, "card_id": card_id}


@router.delete("/products/{card_id}")
def delete_product(card_id: str, db: Session = Depends(get_db)):
    c = db.query(MembershipCard).filter(MembershipCard.card_id == card_id, MembershipCard.is_product == 1).first()
    if not c:
        raise HTTPException(404, "卡产品不存在")
    db.delete(c)
    db.commit()
    return {"success": True}


# ═══════════════════════════════════════════
# 售卡（给会员创建实例）
# ═══════════════════════════════════════════

@router.post("/sell")
def sell_card(
    member_id: str = Form(...),
    member_name: str = Form(...),
    product_id: str = Form(...),
    price: float = Form(0.0),
    start_date: str = Form(""),
    db: Session = Depends(get_db),
):
    """基于卡产品向会员售卡（携带 face_value 和 bonus_classes）"""
    prod = db.query(MembershipCard).filter(MembershipCard.card_id == product_id, MembershipCard.is_product == 1).first()
    if not prod:
        raise HTTPException(404, "卡产品不存在")

    card_id = generate_id("MC", db, MembershipCard.card_id)
    start = date.fromisoformat(start_date) if start_date else date.today()
    end = None
    if prod.duration_days and prod.duration_days > 0:
        end = start + timedelta(days=prod.duration_days)

    c = MembershipCard(
        card_id=card_id, member_id=member_id, member_name=member_name,
        card_type=prod.card_type,
        duration_days=prod.duration_days or 0,
        total_classes=prod.total_classes or 0,
        bonus_classes=prod.bonus_classes or 0,
        face_value=prod.face_value or 0,
        price=price or prod.price or 0,
        start_date=start, end_date=end,
        status="正常", remark="来自产品: {}".format(prod.remark or prod.card_id),
        is_product=0,
        card_name=prod.card_name or prod.remark or "",
    )
    db.add(c)
    # 更新会员剩余课时（次卡）
    if prod.card_type == "次卡":
        add_classes = (prod.total_classes or 0) + (prod.bonus_classes or 0)
        if add_classes:
            from backend.models.models import Member
            member = db.query(Member).filter(Member.member_id == member_id).first()
            if member:
                member.remaining_lessons = (member.remaining_lessons or 0) + add_classes
    db.commit()
    db.refresh(c)
    return {"success": True, "card_id": card_id, "member_name": member_name}


# ═══════════════════════════════════════════
# 已售卡 CRUD（兼容旧版列表+删除）
# ═══════════════════════════════════════════

@router.delete("/sold/{card_id}")
def delete_sold(card_id: str, request: Request, db: Session = Depends(get_db)):
    c = db.query(MembershipCard).filter(MembershipCard.card_id == card_id, MembershipCard.is_product == 0).first()
    if not c:
        raise HTTPException(404, "售卡记录不存在")
    # 记录操作日志
    token = request.cookies.get("access_token", "")
    op = "系统"
    if token:
        from jose import jwt
        from backend.routers.auth import SECRET_KEY, ALGORITHM
        try:
            op = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub", "系统")
        except Exception:
            pass
    record_log(db, op, "delete", "会籍卡", card_id, f"删除售卡记录：{card_id}")
    db.delete(c)
    db.commit()
    return {"success": True}


@router.put("/sold/{card_id}/void")
def void_sold_card(card_id: str, data: VoidRequest, request: Request, db: Session = Depends(get_db)):
    """作废售卡记录（标记作废，不删除）"""
    c = db.query(MembershipCard).filter(MembershipCard.card_id == card_id, MembershipCard.is_product == 0).first()
    if not c:
        raise HTTPException(404, "售卡记录不存在")
    if getattr(c, 'voided', 0):
        raise HTTPException(400, "该记录已作废")
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
    c.voided = 1
    c.void_reason = data.reason
    c.void_time = datetime.now()
    c.void_operator = operator
    record_log(db, operator, "void", "会籍卡", card_id, f"作废会籍卡：{card_id}")
    db.commit()
    return {"success": True, "message": f"售卡记录 {card_id} 已作废"}


@router.get("")
def list_cards(
    skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
    member_id: Optional[str] = None, db: Session = Depends(get_db),
):
    """兼容旧版 — 返回所有非产品记录"""
    query = db.query(MembershipCard).filter(MembershipCard.is_product == 0)
    if member_id:
        query = query.filter(MembershipCard.member_id == member_id)
    return query.order_by(MembershipCard.id.desc()).offset(skip).limit(limit).all()
