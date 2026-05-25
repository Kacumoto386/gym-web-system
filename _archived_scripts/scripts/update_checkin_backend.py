#!/usr/bin/env python3
"""安全更新 checkin.py：添加 quick_lookup + 智能推荐 + 增强 create_checkin"""

import sys
sys.path.insert(0, '.')

FILE = 'backend/routers/checkin.py'

with open(FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# ─── 1. 更新文件头 ───
content = content.replace(
    'V3.0.0',
    'V3.1.7 — 扫码进场 + 自动查会员会籍卡 + 核销推荐'
)
content = content.replace(
    'from datetime import date, datetime',
    'from datetime import date, datetime, timedelta'
)
content = content.replace(
    'from backend.models.models import Checkin, Wristband, Member',
    'from backend.models.models import Checkin, Wristband, Member, MembershipCard'
)

SINGLE_ENTRY_FEE_CONST = """
# ─── 系统常量 ───
SINGLE_ENTRY_FEE = 30.0  # 单次进场费（储值扣款默认金额）


"""

content = content.replace(
    'router = APIRouter(prefix="/api", tags=["进场与手环"])',
    'router = APIRouter(prefix="/api", tags=["进场与手环"])' + SINGLE_ENTRY_FEE_CONST
)

# ─── 2. 在 class CheckinOut 前插入推荐算法 + quick_lookup ───
INSERT_BEFORE = '\n\nclass CheckinOut(BaseModel):'

NEW_CODE = '''
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

        # 期限卡：有效期内推荐签到
        if card_type in ("月卡", "季卡", "年卡", "时卡"):
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
'''

content = content.replace(INSERT_BEFORE, NEW_CODE + INSERT_BEFORE)

# ─── 3. 替换 create_checkin 为增强版 ───
OLD_CREATE = '''@router.post("/checkins")
def create_checkin(
    member_id: str = Query(...),
    member_name: str = Query(...),
    checkin_type: str = Query(""),
    operator: str = Query(""),
    staff_followup: str = Query(""),
    card_type: str = Query(""),
    card_id: str = Query(""),
    consume_type: str = Query(""),
    consume_detail: str = Query(""),
    db: Session = Depends(get_db),
):
    """进场/核销 — 支持自动扣减"""
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

    # ════════════════════════════════════════
    # 自动扣减逻辑
    # ════════════════════════════════════════
    member = db.query(Member).filter(Member.member_id == member_id).first()
    consume_note = ""

    if member and consume_type:
        if consume_type == "次卡扣次":
            # 扣除 1 课时
            if member.remaining_lessons and member.remaining_lessons > 0:
                member.remaining_lessons -= 1
                member.used_lessons = (member.used_lessons or 0) + 1
                consume_note = f"扣除 1 课时，剩余{member.remaining_lessons} 课时"

        elif consume_type == "储值扣款":
            # 扣除单次进场费（默认 30 元，或少于30时扣全部额）
            fee = min(float(member.balance or 0), 30.0)
            if fee > 0:
                member.balance = round(float(member.balance or 0) - fee, 2)
                consume_note = f"扣除进场费¥{fee:.2f}，余¥{member.balance:.2f}"

        elif consume_type == "期限卡签到":
            # 期限卡只签到不扣钱扣款
            consume_note = "期限卡签到，无需扣减"

    if consume_note:
        checkin.consume_detail = consume_note

    db.add(checkin)
    db.commit()
    return {"success": True, "checkin_id": checkin_id, "message": f"{member_name} 进场成功", "consume_note": consume_note}'''

NEW_CREATE = '''@router.post("/checkins")
def create_checkin(
    member_id: str = Query(...),
    member_name: str = Query(...),
    checkin_type: str = Query(""),
    operator: str = Query(""),
    staff_followup: str = Query(""),
    card_type: str = Query(""),
    card_id: str = Query(""),
    consume_type: str = Query(""),
    consume_detail: str = Query(""),
    quantity: int = Query(1, ge=1, le=10, description="扣减数量（次卡扣多次）"),
    custom_fee: float = Query(SINGLE_ENTRY_FEE, ge=0, description="自定义扣款金额"),
    db: Session = Depends(get_db),
):
    """进场/核销 — 支持自动扣减（增强版：支持扣多次/自定义金额）"""
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

    # ════════════════════════════════════════
    # 自动扣减逻辑（增强版）
    # ════════════════════════════════════════
    member = db.query(Member).filter(Member.member_id == member_id).first()
    consume_note = ""

    if member and consume_type:
        if consume_type == "次卡扣次":
            actual = min(quantity, member.remaining_lessons or 0)
            if actual > 0:
                member.remaining_lessons = (member.remaining_lessons or 0) - actual
                member.used_lessons = (member.used_lessons or 0) + actual
                consume_note = f"扣除 {actual} 课时，剩余{member.remaining_lessons} 课时"

        elif consume_type == "储值扣款":
            fee = min(float(custom_fee), float(member.balance or 0))
            if fee > 0:
                member.balance = round(float(member.balance or 0) - fee, 2)
                consume_note = f"扣除进场费¥{fee:.2f}，余¥{member.balance:.2f}"

        elif consume_type == "期限卡签到":
            consume_note = "期限卡签到，无需扣减"

    # 更新累计签到天数 + 最后签到日期
    if member:
        member.total_checkin_days = (member.total_checkin_days or 0) + 1
        member.last_checkin_date = now.date()
        if not consume_note:
            consume_note = f"签到成功，累计{member.total_checkin_days}天"
        checkin.consume_detail = consume_note

    db.add(checkin)
    db.commit()
    return {"success": True, "checkin_id": checkin_id, "message": f"{member_name} 进场成功", "consume_note": consume_note}'''

content = content.replace(OLD_CREATE, NEW_CREATE)

# ─── 写入 ───
with open(FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✅ checkin.py 更新完成，总字符数: {len(content)}")
