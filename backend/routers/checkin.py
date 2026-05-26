# -*- coding: utf-8 -*-
"""
进场核销 + 手环管理 API 路由 + HTMX HTML 片段端点
V3.1.7 — 扫码进场 + 自动查会员会籍卡 + 核销推荐
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta, timedelta
from backend.database import get_db
from backend.routers.operation_log import record_log
from backend.utils.response import success, fail as api_fail
from backend.models.models import Checkin, Wristband, Member, MembershipCard, MembershipCard
from backend.services.id_gen import generate_id
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["进场与手环"])
# ─── 系统常量 ───
SINGLE_ENTRY_FEE = 30.0  # 单次进场费（现金卡/储值扣款默认金额）
SINGLE_CASH_CARD_FEE = 30.0  # 现金卡单次进场扣费（兜底，前端自定义输入优先）


# ─── 系统常量 ───


# ═══════════════════════════════════════════
# HTMX HTML 片段
# ═══════════════════════════════════════════

def _build_band_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无手环</div>'
    trs = ""
    for b in rows:
        status_cls = "bg-green-100 text-green-700" if b.status == "已绑定" else "bg-gray-100 text-gray-700"
        bind_btn = f'<button class="text-green-600 hover:text-green-800 mr-2" onclick="openBindModal(\'{b.band_id}\')">绑定</button>' if b.status != "已绑定" else ""
        unbind_path = f'/api/wristbands/{b.band_id}/unbind'
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{b.band_id}</td>
            <td class="px-4 py-3 text-sm">{b.reader_value}</td>
            <td class="px-4 py-3 text-sm">{b.custom_id or ''}</td>
            <td class="px-4 py-3 text-sm"><span class="px-2 py-0.5 {status_cls} rounded text-xs">{b.status or '未绑定'}</span></td>
            <td class="px-4 py-3 text-sm">{b.bound_member_name or ''}</td>
            <td class="px-4 py-3 text-sm">{b.bound_member_id or ''}</td>
            <td class="px-4 py-3 text-sm">
                {bind_btn}
                <button class="text-orange-500 hover:text-orange-700 mr-2" hx-put="{unbind_path}" hx-target="#wristbandTable" hx-confirm="确认解绑此手环？">解绑</button>
                <button class="text-red-500 hover:text-red-700" hx-delete="/api/wristbands/{b.band_id}" hx-target="#wristbandTable" hx-confirm="确认删除此手环？">删除</button>
            </td>
        </tr>"""
    return f"""<div class="overflow-x-auto"><table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">读卡器值</th><th class="px-4 py-3">自定义编号</th><th class="px-4 py-3">状态</th><th class="px-4 py-3">绑定会员</th><th class="px-4 py-3">会员编号</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table></div>"""


@router.get("/wristbands/table", response_class=HTMLResponse)
def wristband_table(db: Session = Depends(get_db)):
    return _build_band_table(db.query(Wristband).order_by(Wristband.id.desc()).limit(100).all())

def _build_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无进场记录</div>'
    trs = ""
    for c in rows:
        type_cls = {"核销": "bg-blue-100 text-blue-700", "临时": "bg-yellow-100 text-yellow-700",
                     "体验": "bg-green-100 text-green-700"}.get(c.checkin_type, "bg-gray-100 text-gray-700")
        consume_badge = ""
        if c.consume_type == "次卡扣次":
            consume_badge = '<span class="px-1.5 py-0.5 rounded text-xs bg-purple-100 text-purple-700">扣次</span>'
        elif c.consume_type == "储值扣款":
            consume_badge = '<span class="px-1.5 py-0.5 rounded text-xs bg-orange-100 text-orange-700">扣款</span>'
        elif c.consume_type == "期限卡签到":
            consume_badge = '<span class="px-1.5 py-0.5 rounded text-xs bg-green-100 text-green-700">签到</span>'
        elif c.consume_type == "现金卡扣费":
            consume_badge = '<span class="px-1.5 py-0.5 rounded text-xs bg-red-100 text-red-700">现金扣</span>'
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{c.checkin_id}</td>
            <td class="px-4 py-3">{c.member_name or ''}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{c.member_id}</td>
            <td class="px-4 py-3 text-sm">{c.checkin_date}</td>
            <td class="px-4 py-3 text-sm">{c.checkin_time or ''}</td>
            <td class="px-4 py-3"><span class="px-2 py-0.5 {type_cls} rounded text-xs">{c.checkin_type or ''}</span></td>
            <td class="px-4 py-3 text-sm">{c.card_type or ''} {consume_badge}</td>
            <td class="px-4 py-3 text-sm text-gray-500 max-w-[120px] truncate" title="{c.consume_detail or ''}">{c.consume_detail or ''}</td>
            <td class="px-4 py-3 text-sm">{c.staff_followup or ''}</td>
            <td class="px-4 py-3 text-sm text-gray-500">{c.operator or ''}</td>
        </tr>"""
    return f"""<div class="overflow-x-auto bg-white rounded-lg shadow-sm">
    <table class="w-full">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">编号</th><th class="px-4 py-3">会员</th><th class="px-4 py-3">编号</th><th class="px-4 py-3">日期</th><th class="px-4 py-3">时间</th><th class="px-4 py-3">类型</th><th class="px-4 py-3">卡类型</th><th class="px-4 py-3">核销方式</th><th class="px-4 py-3">跟进</th><th class="px-4 py-3">操作人</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>
</div>"""


@router.get("/checkins/table", response_class=HTMLResponse)
def checkin_table(checkin_date: str = "", db: Session = Depends(get_db)):
    query = db.query(Checkin)
    if checkin_date:
        try:
            d = date.fromisoformat(checkin_date)
            query = query.filter(Checkin.checkin_date == d)
        except ValueError:
            pass
    return _build_table(query.order_by(Checkin.id.desc()).limit(100).all())


# ═══════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════
# ══════════════════════════════════════════
# 智能推荐算法
# ══════════════════════════════════════════
def _recommend_consume(member, active_cards):
    """
    智能推荐最优核销方式
    返回排序后的推荐列表，第一条为最优
    """
    today = date.today()
    recommendations = []

    for card in active_cards:
        card_type = card.card_type or ""
        remaining_amount = float(card.price or 0) - float(card.consumed_amount or 0)

        # 现金卡：独立推荐 — 按次扣费
        if card_type == "现金卡":
            if card.end_date and card.end_date >= today and remaining_amount >= SINGLE_CASH_CARD_FEE:
                days_left = (card.end_date - today).days
                recommendations.append({
                    "card_id": card.card_id,
                    "card_type": "现金卡",
                    "consume_type": "现金卡扣费",
                    "label": f"现金卡剩余¥{remaining_amount:.0f}，每次扣¥{SINGLE_CASH_CARD_FEE:.0f}，有效期剩{days_left}天",
                    "score": 100,
                    "fee": SINGLE_CASH_CARD_FEE,
                    "quantity": 1,
                })

        # 期限卡（不含现金卡）：有效期内推荐签到
        elif card_type in ("月卡", "季卡", "年卡", "时卡"):
            if card.end_date and card.end_date >= today:
                days_left = (card.end_date - today).days
                recommendations.append({
                    "card_id": card.card_id,
                    "card_type": card_type,
                    "consume_type": "期限卡签到",
                    "label": f"{card_type}有效，剩余{days_left}天",
                    "score": 100,
                    "fee": 0,
                    "quantity": 1,
                })

        # 次卡：有剩余课时推荐扣次
        if "次" in card_type:
            remaining = member.remaining_lessons or 0
            if remaining > 0:
                recommendations.append({
                    "card_id": card.card_id,
                    "card_type": card_type,
                    "consume_type": "次卡扣次",
                    "label": f"次卡，剩余{remaining}课时",
                    "score": 80,
                    "fee": 0,
                    "quantity": 1,
                })

    # 储值扣款作为最后兜底
    balance = float(member.balance or 0)
    if balance > 0:
        fee = min(balance, SINGLE_ENTRY_FEE)
        recommendations.append({
            "card_id": "",
            "card_type": "储值",
            "consume_type": "储值扣款",
            "label": f"余额¥{balance:.0f}，扣¥{fee:.0f}",
            "score": 60,
            "fee": fee,
            "quantity": 1,
        })

    recommendations.sort(key=lambda r: r["score"], reverse=True)
    return recommendations


def _identify_query(query: str):
    """
    识别查询类型：
    - member_id: M开头
    - phone: 11位纯数字
    - wristband: 10位纯数字
    - custom: 其他
    """
    q = query.strip()
    if q.startswith("M") or q.startswith("m"):
        return "member_id", q.upper()
    if q.isdigit():
        if len(q) == 11:
            return "phone", q
        if len(q) == 10:
            return "wristband", q
    return "custom", q


# ══════════════════════════════════════════
# 快速进场查询（扫码/输入 → 自动查会员会籍卡）
# ══════════════════════════════════════════

@router.get("/checkin/quick-lookup")
def quick_lookup(q: str = Query(..., description="会员编号/手机号/手环值/自定义"), db: Session = Depends(get_db)):
    """
    扫码/输入快速查询：
    1. 识别输入类型（会员编号/手机号/手环值）
    2. 查会员 + 有效会籍卡
    3. 智能推荐最优核销方式
    """
    kind, value = _identify_query(q)
    member = None

    if kind == "member_id":
        member = db.query(Member).filter(Member.member_id == value).first()
    elif kind == "phone":
        member = db.query(Member).filter(Member.phone == value).first()
    elif kind == "wristband":
        wb = db.query(Wristband).filter(Wristband.reader_value == value).first()
        if wb and wb.bound_member_id:
            member = db.query(Member).filter(Member.member_id == wb.bound_member_id).first()
    else:
        # 尝试模糊匹配：先按编号，再按姓名
        member = db.query(Member).filter(Member.member_id == value).first()
        if not member:
            member = db.query(Member).filter(Member.name.contains(value)).first()

    if not member:
        return {"found": False, "message": "未识别此码，请手动搜索会员"}

    # 查询有效会籍卡（status=正常 且 end_date >= 今天）
    today = date.today()
    active_cards = db.query(MembershipCard).filter(
        MembershipCard.member_id == member.member_id,
        MembershipCard.status == "正常",
        MembershipCard.end_date >= today,
    ).order_by(MembershipCard.id.desc()).all()

    # 查询全部会籍卡（含已过期，用于展示）
    all_cards = db.query(MembershipCard).filter(
        MembershipCard.member_id == member.member_id
    ).order_by(MembershipCard.id.desc()).all()

    # 智能推荐
    recommendations = _recommend_consume(member, active_cards)

    return {
        "found": True,
        "method": kind,
        "member": {
            "member_id": member.member_id,
            "name": member.name,
            "phone": member.phone or "",
            "gender": member.gender or "",
            "level": member.level or "普通",
            "status": member.status or "正常",
            "remaining_lessons": member.remaining_lessons or 0,
            "balance": float(member.balance or 0),
            "start_date": str(member.start_date) if member.start_date else "",
            "end_date": str(member.end_date) if member.end_date else "",
            "total_checkin_days": member.total_checkin_days or 0,
            "last_checkin_date": str(member.last_checkin_date) if member.last_checkin_date else "",
        },
        "active_cards": [
            {
                "card_id": c.card_id,
                "card_type": c.card_type or "",
                "duration_days": c.duration_days or 0,
                "start_date": str(c.start_date) if c.start_date else "",
                "end_date": str(c.end_date) if c.end_date else "",
                "days_remaining": (c.end_date - today).days if c.end_date else 0,
                "price": float(c.price or 0),
                "consumed_amount": float(c.consumed_amount or 0),
                "status": c.status or "",
            }
            for c in active_cards
        ],
        "all_cards": [
            {
                "card_id": c.card_id,
                "card_type": c.card_type or "",
                "duration_days": c.duration_days or 0,
                "start_date": str(c.start_date) if c.start_date else "",
                "end_date": str(c.end_date) if c.end_date else "",
                "price": float(c.price or 0),
                "consumed_amount": float(c.consumed_amount or 0),
                "status": c.status or "",
            }
            for c in all_cards
        ],
        "recommended": recommendations[0] if recommendations else None,
        "all_recommendations": recommendations,
    }


@router.get("/checkin/today-count")
def today_checkin_count(member_id: str = Query(...), db: Session = Depends(get_db)):
    """查询会员今日进场次数"""
    today = date.today()
    count = db.query(Checkin).filter(
        Checkin.member_id == member_id,
        Checkin.checkin_date == today,
    ).count()
    return {"count": count, "today": str(today)}


class CheckinOut(BaseModel):
    id: int
    checkin_id: str
    member_id: str
    member_name: str
    checkin_date: date
    checkin_type: str
    operator: str

    class Config:
        from_attributes = True


class WristbandCreate(BaseModel):
    reader_value: str
    custom_id: Optional[str] = ""
    remark: Optional[str] = ""


class WristbandOut(BaseModel):
    id: int
    band_id: str
    reader_value: str
    custom_id: str
    status: str
    bound_member_id: str
    bound_member_name: str

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════

@router.get("/checkins", response_model=List[CheckinOut])
def list_checkins(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    checkin_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Checkin)
    if checkin_date:
        try:
            d = date.fromisoformat(checkin_date)
            query = query.filter(Checkin.checkin_date == d)
        except ValueError:
            pass
    return query.order_by(Checkin.id.desc()).offset(skip).limit(limit).all()


@router.post("/checkins")
def create_checkin(
    request: Request,
    member_id: str = Form(...),
    member_name: str = Form(...),
    checkin_type: str = Form(""),
    operator: str = Form(""),
    staff_followup: str = Form(""),
    card_type: str = Form(""),
    card_id: str = Form(""),
    consume_type: str = Form(""),
    consume_detail: str = Form(""),
    consume_quantity: int = Form(1, ge=1, le=999),  # 自定义扣次（次卡）
    consume_amount: float = Form(0, ge=0),          # 自定义扣款金额（储值卡）
    db: Session = Depends(get_db),
):
    """进场/核销 — 支持自定义扣次/扣费"""
    checkin_id = generate_id("CI", db, Checkin.checkin_id)
    now = datetime.now()

    checkin = Checkin(
        checkin_id=checkin_id,
        member_id=member_id,
        member_name=member_name,
        checkin_date=now.date(),
        checkin_time=now.strftime("%H:%M"),
        checkin_type=checkin_type or "核销",
        card_type=card_type or "",
        card_id=card_id or "",
        consume_type=consume_type or "",
        consume_detail=consume_detail or "",
        operator=operator or "",
        staff_followup=staff_followup or "",
    )

    # ═══ 自动扣减逻辑 ═══
    member = db.query(Member).filter(Member.member_id == member_id).first()
    consume_note = ""

    if member and consume_type:
        if consume_type == "次卡扣次":
            # 自定义扣 N 次（前端传 consume_quantity）
            n = max(1, consume_quantity)
            if member.remaining_lessons and member.remaining_lessons >= n:
                member.remaining_lessons -= n
                member.used_lessons = (member.used_lessons or 0) + n
                consume_note = f"扣除 {n} 课时，剩余 {member.remaining_lessons} 课时"
            else:
                # 不够扣 → 全部用完
                actual = member.remaining_lessons or 0
                if actual > 0:
                    member.used_lessons = (member.used_lessons or 0) + actual
                    member.remaining_lessons = 0
                    consume_note = f"剩余课时不足，实际扣除 {actual} 课时，剩余 0 课时"

        elif consume_type == "储值扣款":
            # 自定义扣费金额（前端传 consume_amount）
            fee = min(consume_amount, float(member.balance or 0)) if consume_amount > 0 else 0
            if fee <= 0:
                # 没传金额时用默认30
                fee = min(float(member.balance or 0), 30.0)
            if fee > 0:
                member.balance = round(float(member.balance or 0) - fee, 2)
                consume_note = f"扣除进场费 ¥{fee:.2f}，余额 ¥{member.balance:.2f}"

        elif consume_type == "期限卡签到":
            consume_note = "期限卡签到，无需扣减"

        elif consume_type == "现金卡扣费":
            # 现金卡扣费：必须传入自定义金额，无默认值
            cash_card = db.query(MembershipCard).filter(MembershipCard.card_id == card_id).first() if card_id else None
            if cash_card and cash_card.card_type == "现金卡":
                if consume_amount <= 0:
                    return {"success": False, "detail": "现金卡扣费必须输入扣费金额"}
                consumed = float(cash_card.consumed_amount or 0)
                remaining_in_card = float(cash_card.price or 0) - consumed
                if consume_amount > remaining_in_card:
                    return {"success": False, "detail": f"现金卡余额不足（剩余 ¥{remaining_in_card:.2f}，需扣 ¥{consume_amount:.2f}）"}
                cash_card.consumed_amount = consumed + consume_amount
                consume_note = f"现金卡扣费 ¥{consume_amount:.2f}，卡内剩余 ¥{remaining_in_card - consume_amount:.2f}，有效期至 {cash_card.end_date}"
            else:
                consume_note = "现金卡扣费，无需扣减（未指定卡ID）"

        elif consume_type == "无卡体验":
            consume_note = "无卡体验，无需扣减"
            checkin.checkin_type = "体验"

    if consume_note:
        checkin.consume_detail = consume_note

    db.add(checkin)
    db.commit()
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
    record_log(db, op, "create", "进场记录", checkin_id, f"会员进场：{member_name}（{checkin_type}）")
    return success(data={"checkin_id": checkin_id, "consume_note": consume_note}, message=f"{member_name} 进场成功")


# ═══ 刷卡查询 ═══

@router.get("/wristbands/search")
def search_wristband_by_reader(
    reader_value: str = Query(..., description="读卡器10位数字"),
    db: Session = Depends(get_db),
):
    wb = db.query(Wristband).filter(Wristband.reader_value == reader_value).first()
    if not wb:
        return {"found": False, "message": "未识别的手环"}
    result = {"found": True, "band_id": wb.band_id, "custom_id": wb.custom_id, "status": wb.status}
    if wb.bound_member_id:
        member = db.query(Member).filter(Member.member_id == wb.bound_member_id).first()
        if member:
            result["member"] = {
                "member_id": member.member_id, "name": member.name,
                "phone": member.phone, "level": member.level,
                "status": member.status, "remaining_lessons": member.remaining_lessons or 0,
                "balance": float(member.balance or 0),
            }
    return result


# ═══ Wristband CRUD ═══

@router.get("/wristbands", response_model=List[WristbandOut])
def list_wristbands(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return db.query(Wristband).order_by(Wristband.id.desc()).offset(skip).limit(limit).all()


@router.post("/wristbands", response_model=WristbandOut)
def create_wristband(request: Request, data: WristbandCreate, db: Session = Depends(get_db)):
    if not data.reader_value or len(data.reader_value) != 10 or not data.reader_value.isdigit():
        raise HTTPException(status_code=400, detail="读卡器写入值必须为10位数字")
    exist = db.query(Wristband).filter(Wristband.reader_value == data.reader_value).first()
    if exist:
        raise HTTPException(status_code=400, detail=f"读卡器值 {data.reader_value} 已存在")
    band_id = generate_id("WB", db, Wristband.band_id)
    wb = Wristband(band_id=band_id, reader_value=data.reader_value,
                   custom_id=data.custom_id or "", status="未绑定",
                   register_time=date.today(), remark=data.remark or "")
    db.add(wb)
    db.commit()
    db.refresh(wb)
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
    record_log(db, op, "create", "手环", band_id, f"创建手环：{wb.reader_value}")
    return wb


@router.put("/wristbands/{band_id}/bind")
def bind_wristband(band_id: str, member_id: str, request: Request, db: Session = Depends(get_db)):
    wb = db.query(Wristband).filter(Wristband.band_id == band_id).first()
    if not wb:
        raise HTTPException(status_code=404, detail="手环不存在")
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")
    wb.bound_member_id = member_id
    wb.bound_member_name = member.name
    wb.bound_time = date.today()
    wb.status = "已绑定"
    member.wristband_id = band_id
    db.commit()
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
    record_log(db, op, "bind", "手环", band_id, f"绑定手环：{band_id} -> {member.name}({member_id})")
    return success(message=f"手环 {band_id} 已绑定给 {member.name}")


@router.put("/wristbands/{band_id}/unbind")
def unbind_wristband(band_id: str, request: Request, db: Session = Depends(get_db)):
    wb = db.query(Wristband).filter(Wristband.band_id == band_id).first()
    if not wb:
        raise HTTPException(status_code=404, detail="手环不存在")
    if wb.bound_member_id:
        member = db.query(Member).filter(Member.member_id == wb.bound_member_id).first()
        if member:
            member.wristband_id = ""
    wb.bound_member_id = ""
    wb.bound_member_name = ""
    wb.bound_time = None
    wb.status = "未绑定"
    db.commit()
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
    record_log(db, op, "unbind", "手环", band_id, f"解绑手环：{band_id}")
    return success(message=f"手环 {band_id} 已解绑")


@router.delete("/wristbands/{band_id}")
def delete_wristband(band_id: str, request: Request, db: Session = Depends(get_db)):
    wb = db.query(Wristband).filter(Wristband.band_id == band_id).first()
    if not wb:
        raise HTTPException(status_code=404, detail="手环不存在")
    if wb.bound_member_id:
        member = db.query(Member).filter(Member.member_id == wb.bound_member_id).first()
        if member:
            member.wristband_id = ""
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
    record_log(db, op, "delete", "手环", band_id, f"删除手环：{band_id}")
    db.delete(wb)
    db.commit()
    return success(message=f"手环 {band_id} 已删除")
