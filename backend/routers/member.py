"""
会员管理 API 路由
V3.5.3 — 增强：统计卡片、多维筛选、排序分页、详情页
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timedelta

from backend.database import get_db
from backend.models.models import Member, MembershipCard, Checkin, ClassRecord, BodyMeasurement, Recharge, Sale, Staff, LessonPackage
from backend.services.id_gen import generate_id
from sqlalchemy import or_

router = APIRouter(prefix="/api/members", tags=["会员管理"])
TODAY = date.today()
PAGE_SIZE = 20


# ═══════════════════════════════════════════
# HTMX HTML 片段端点（必须在 {member_id} 之前注册）
# ═══════════════════════════════════════════

SORT_WHITELIST = {
    "member_id": Member.member_id, "name": Member.name, "gender": Member.gender,
    "phone": Member.phone, "level": Member.level, "status": Member.status,
    "remaining_lessons": Member.remaining_lessons, "balance": Member.balance,
    "last_checkin_date": Member.last_checkin_date, "source": Member.source,
    "staff_name": Member.staff_name, "created_at": Member.created_at,
    "total_checkin_days": Member.total_checkin_days,
}


def _build_table(rows: list, sort_by: str = "created_at", sort_dir: str = "desc") -> str:
    """生成会员表格 HTML（含可排序表头）"""
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无会员数据</div>'

    def _th(col_id, label):
        arrow = ""
        if sort_by == col_id:
            arrow = " ▲" if sort_dir == "asc" else " ▼"
        return f'<th class="px-3 py-2 cursor-pointer hover:bg-gray-200 select-none" onclick="sortTable(\'{col_id}\')">{label}{arrow}</th>'

    trs = ""
    for m in rows:
        status_class = "bg-green-100 text-green-700" if m.status in ("正常", "有效") else "bg-red-100 text-red-700"
        lcd = str(m.last_checkin_date) if m.last_checkin_date else "-"
        name_escaped = m.name.replace("'", "\\'")
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-3 py-2 text-sm text-gray-500">{m.member_id}</td>
            <td class="px-3 py-2"><a href="/members/{m.member_id}" class="text-blue-600 hover:text-blue-800 hover:underline">{m.name}</a></td>
            <td class="px-3 py-2 text-sm">{m.gender or ''}</td>
            <td class="px-3 py-2 text-sm">{m.phone or ''}</td>
            <td class="px-3 py-2 text-sm"><span class="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{m.level}</span></td>
            <td class="px-3 py-2 text-sm">{m.remaining_lessons}</td>
            <td class="px-3 py-2 text-sm">{'%.2f' % m.balance}</td>
            <td class="px-3 py-2 text-sm text-gray-500">{lcd}</td>
            <td class="px-3 py-2 text-sm">{m.source or ''}</td>
            <td class="px-3 py-2 text-sm">{m.staff_name or ''}</td>
            <td class="px-3 py-2 text-sm"><span class="px-1.5 py-0.5 {status_class} rounded text-xs">{m.status or '正常'}</span></td>
            <td class="px-3 py-2 text-sm whitespace-nowrap">
                <a href="/members/{m.member_id}" class="text-blue-600 hover:text-blue-800 mr-2">详情</a>
                <button class="text-blue-600 hover:text-blue-800 mr-2" onclick="openEditModal('{m.member_id}')">编辑</button>
                <button class="text-green-600 hover:text-green-800 mr-2" onclick="openSellCardModal('{m.member_id}', '{name_escaped}')">售卡</button>
                <button class="text-red-500 hover:text-red-700" hx-delete="/api/members/{m.member_id}" hx-target="#memberTable" hx-confirm="确认删除会员 {m.name}？">删除</button>
            </td>
        </tr>"""

    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr>
                {_th('member_id', '编号')}
                {_th('name', '姓名')}
                {_th('gender', '性别')}
                {_th('phone', '手机号')}
                {_th('level', '等级')}
                {_th('remaining_lessons', '剩余课时')}
                {_th('balance', '储值余额')}
                {_th('last_checkin_date', '最近签到')}
                {_th('source', '来源')}
                {_th('staff_name', '跟进')}
                {_th('status', '状态')}
                <th class="px-3 py-2">操作</th>
            </tr>
        </thead>
        <tbody>
            {trs}
        </tbody>
    </table>"""


def _build_pagination(page: int, total: int, total_pages: int) -> str:
    """生成分页控件 HTML"""
    if total_pages <= 1:
        return ""
    pages_html = ""
    for p in range(1, total_pages + 1):
        if p == page:
            pages_html += f'<span class="px-3 py-1.5 bg-blue-600 text-white rounded text-sm font-medium">{p}</span>'
        else:
            pages_html += f'<button class="px-3 py-1.5 border rounded text-sm hover:bg-gray-100" onclick="goPage({p})">{p}</button>'

    prev_disabled = "opacity-50 cursor-not-allowed" if page <= 1 else "hover:bg-gray-100"
    next_disabled = "opacity-50 cursor-not-allowed" if page >= total_pages else "hover:bg-gray-100"
    prev_onclick = "" if page <= 1 else f'onclick="goPage({page-1})"'
    next_onclick = "" if page >= total_pages else f'onclick="goPage({page+1})"'

    return f"""<div class="flex items-center justify-between mt-3 pt-2 border-t">
        <span class="text-sm text-gray-500">共 {total} 条记录</span>
        <div class="flex items-center gap-1">
            <button class="px-3 py-1.5 border rounded text-sm {prev_disabled}" {prev_onclick}>上一页</button>
            {pages_html}
            <button class="px-3 py-1.5 border rounded text-sm {next_disabled}" {next_onclick}>下一页</button>
        </div>
    </div>"""


@router.get("/table", response_class=HTMLResponse)
def member_table(
    q: str = "",
    level: str = "",
    status: str = "",
    source: str = "",
    staff_id: str = "",
    reg_from: str = "",
    reg_to: str = "",
    checkin_from: str = "",
    checkin_to: str = "",
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = 1,
    db: Session = Depends(get_db),
):
    """会员表格 HTML 片段（含筛选/排序/分页）"""
    query = db.query(Member)

    # 关键词搜索
    kw = q.strip()
    if kw:
        query = query.filter(
            Member.name.contains(kw)
            | Member.phone.contains(kw)
            | Member.member_id.contains(kw)
        )

    # 筛选
    if level:
        query = query.filter(Member.level == level)
    if status:
        query = query.filter(Member.status == status)
    if source:
        query = query.filter(Member.source == source)
    if staff_id:
        query = query.filter(Member.staff_id == staff_id)
    if reg_from:
        try:
            query = query.filter(func.date(Member.created_at) >= date.fromisoformat(reg_from))
        except ValueError:
            pass
    if reg_to:
        try:
            query = query.filter(func.date(Member.created_at) <= date.fromisoformat(reg_to))
        except ValueError:
            pass
    if checkin_from:
        try:
            query = query.filter(Member.last_checkin_date >= date.fromisoformat(checkin_from))
        except ValueError:
            pass
    if checkin_to:
        try:
            query = query.filter(Member.last_checkin_date <= date.fromisoformat(checkin_to))
        except ValueError:
            pass

    # 排序（白名单校验）
    sort_col = SORT_WHITELIST.get(sort_by, Member.created_at)
    if sort_dir == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    # 总数
    total = query.count()

    # 分页
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    rows = query.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()

    table_html = _build_table(rows, sort_by, sort_dir)
    pagination_html = _build_pagination(page, total, total_pages)
    return f"{table_html}{pagination_html}"


# ═══════════════════════════════════════════
# 统计卡片
# ═══════════════════════════════════════════

@router.get("/stats", response_class=HTMLResponse)
def member_stats(db: Session = Depends(get_db)):
    """会员统计卡片 HTML"""
    first_of_month = TODAY.replace(day=1)
    last_of_month = (first_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    total = db.query(Member).count()
    new_month = db.query(Member).filter(
        func.date(Member.created_at) >= first_of_month
    ).count()
    expiring = db.query(Member).filter(
        Member.end_date.isnot(None),
        Member.end_date >= TODAY,
        Member.end_date <= last_of_month
    ).count()
    active_count = db.query(Member).filter(
        Member.status.in_(["正常", "有效"])
    ).count()
    active_rate = round(active_count / total * 100, 1) if total > 0 else 0

    cards = [
        ("总会员数", str(total), "人", "bg-gray-50", "text-gray-700"),
        ("本月新增", str(new_month), "人", "bg-blue-50", "text-blue-700"),
        ("本月到期", str(expiring), "人", "bg-orange-50" if expiring > 0 else "bg-gray-50",
         "text-orange-700" if expiring > 0 else "text-gray-700"),
        ("活跃率", f"{active_rate}%", f"({active_count}人)", "bg-green-50", "text-green-700"),
    ]
    html = ""
    for label, value, unit, bg, fg in cards:
        html += f"""<div class="{bg} rounded-lg p-2.5 text-center">
            <div class="text-xs text-gray-500">{label}</div>
            <div class="text-xl font-bold {fg} mt-0">{value}</div>
            <div class="text-xs text-gray-400">{unit}</div>
        </div>"""
    return f'<div class="grid grid-cols-4 gap-2 mb-3">{html}</div>'


# ═══════════════════════════════════════════
# 筛选选项 JSON
# ═══════════════════════════════════════════

@router.get("/filter-options")
def filter_options(db: Session = Depends(get_db)):
    """返回筛选下拉可选项"""
    levels = [r[0] for r in db.query(Member.level).distinct().filter(Member.level != "").all()]
    statuses = [r[0] for r in db.query(Member.status).distinct().filter(Member.status != "").all()]
    sources = [r[0] for r in db.query(Member.source).distinct().filter(Member.source != "").all()]
    staff_list = db.query(Staff).filter(or_(Staff.status == "在职", Staff.status == "")).order_by(Staff.name).all()
    return {
        "levels": levels,
        "statuses": statuses,
        "sources": sources,
        "staff": [{"staff_id": s.staff_id, "name": s.name} for s in staff_list],
    }


# ═══════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════

from pydantic import BaseModel


class MemberCreate(BaseModel):
    name: str
    gender: Optional[str] = ""
    phone: Optional[str] = ""
    birth_date: Optional[date] = None
    height: Optional[float] = 0
    weight: Optional[float] = 0
    body_fat: Optional[float] = 0
    level: Optional[str] = "普通"
    source: Optional[str] = ""
    remark: Optional[str] = ""
    store_id: Optional[str] = ""
    wristband_id: Optional[str] = ""
    staff_id: Optional[str] = ""
    staff_name: Optional[str] = ""


class MemberOut(BaseModel):
    id: int
    member_id: str
    name: str
    gender: str
    phone: str
    level: str
    status: str
    balance: float
    remaining_lessons: int
    total_checkin_days: int
    height: Optional[float] = 0
    weight: Optional[float] = 0
    body_fat: Optional[float] = 0
    birth_date: Optional[date] = None
    source: Optional[str] = ""
    remark: Optional[str] = ""
    staff_id: Optional[str] = ""
    staff_name: Optional[str] = ""

    class Config:
        from_attributes = True
        # Pydantic v2: 序列化 date 对象为 ISO 字符串
        # json_encoders 在 v2 中已移除，改用任意类型注解或手动处理
        pass


# ═══════════════════════════════════════════
# REST API 端点
# ═══════════════════════════════════════════

import os
from pathlib import Path
from fastapi import UploadFile, File
from PIL import Image as PILImage
import io

# 照片存储目录
PHOTO_DIR = Path(__file__).parent.parent.parent / "data" / "member_photos"
PHOTO_DIR.mkdir(parents=True, exist_ok=True)
PHOTO_SIZE = (360, 480)  # 3:4 比例


def _save_member_photo(member_id: str, image_data: bytes) -> str:
    """保存会员照片，返回相对路径"""
    try:
        img = PILImage.open(io.BytesIO(image_data))
        # 转换为 RGB
        if img.mode != "RGB":
            img = img.convert("RGB")
        # 缩放到标准尺寸（保持比例）
        img.thumbnail(PHOTO_SIZE, PILImage.LANCZOS)
        # 居中裁剪
        w, h = img.size
        target_w, target_h = PHOTO_SIZE
        left = (w - target_w) / 2
        top = (h - target_h) / 2
        right = (w + target_w) / 2
        bottom = (h + target_h) / 2
        img = img.crop((left, top, right, bottom))
        # 保存
        filename = f"{member_id}.jpg"
        filepath = PHOTO_DIR / filename
        img.save(filepath, "JPEG", quality=85)
        return str(filepath)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图片处理失败: {str(e)}")


@router.post("/{member_id}/photo", response_model=dict)
def upload_member_photo(member_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传会员照片"""
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")

    # 验证文件类型
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="仅支持 JPEG/PNG/WebP 格式")

    # 读取并处理图片
    image_data = file.file.read()
    filepath = _save_member_photo(member_id, image_data)

    # 更新数据库记录
    member.photo_path = str(filepath)
    db.commit()

    return {"success": True, "photo_path": str(filepath)}


@router.get("/{member_id}/photo")
def get_member_photo(member_id: str, db: Session = Depends(get_db)):
    """获取会员照片（返回图片文件）"""
    from fastapi.responses import FileResponse

    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")

    if not member.photo_path:
        raise HTTPException(status_code=404, detail="会员暂无照片")

    filepath = Path(member.photo_path)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="照片文件不存在")

    return FileResponse(str(filepath), media_type="image/jpeg")


@router.delete("/{member_id}/photo")
def delete_member_photo(member_id: str, db: Session = Depends(get_db)):
    """删除会员照片"""
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")

    if member.photo_path:
        filepath = Path(member.photo_path)
        if filepath.exists():
            filepath.unlink()
        member.photo_path = ""
        db.commit()

    return {"success": True, "message": "照片已删除"}


@router.get("", response_model=List[MemberOut])
def list_members(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取会员列表"""
    query = db.query(Member)
    if keyword:
        query = query.filter(
            Member.name.contains(keyword)
            | Member.phone.contains(keyword)
            | Member.member_id.contains(keyword)
        )
    members = query.order_by(Member.id.desc()).offset(skip).limit(limit).all()
    return members


@router.get("/search-json")
def member_search_json(q: str = Query(""), db: Session = Depends(get_db)):
    """搜索会员返回 JSON（供进场核销搜索框使用）"""
    query = db.query(Member)
    kw = q.strip()
    if kw:
        query = query.filter(
            Member.name.contains(kw)
            | Member.phone.contains(kw)
            | Member.member_id.contains(kw)
        )
    members = query.order_by(Member.id.desc()).limit(50).all()
    result = []
    for m in members:
        card_type = ""
        card = db.query(MembershipCard).filter(
            MembershipCard.member_id == m.member_id,
            MembershipCard.status == "正常"
        ).first()
        if card:
            card_type = card.card_type or ""
        result.append({
            "member_id": m.member_id,
            "name": m.name,
            "phone": m.phone or "",
            "level": m.level or "普通",
            "status": m.status or "正常",
            "remaining_lessons": m.remaining_lessons or 0,
            "balance": float(m.balance or 0),
            "card_type": card_type,
            "start_date": str(m.start_date) if m.start_date else "",
            "end_date": str(m.end_date) if m.end_date else "",
        })
    return result


@router.get("/{member_id}/with-cards")
def get_member_with_cards(member_id: str, db: Session = Depends(get_db)):
    """获取会员详情 + 会籍卡列表（供进场核销使用）"""
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")
    cards = db.query(MembershipCard).filter(
        MembershipCard.member_id == member_id
    ).order_by(MembershipCard.id.desc()).all()
    card_list = []
    for c in cards:
        card_list.append({
            "card_id": c.card_id,
            "card_type": c.card_type or "",
            "duration_days": c.duration_days or 0,
            "price": float(c.price or 0),
            "consumed_amount": float(c.consumed_amount or 0),
            "start_date": str(c.start_date) if c.start_date else "",
            "end_date": str(c.end_date) if c.end_date else "",
            "status": c.status or "",
        })
    return {
        "member": {
            "member_id": member.member_id,
            "name": member.name,
            "phone": member.phone or "",
            "level": member.level or "普通",
            "status": member.status or "正常",
            "remaining_lessons": member.remaining_lessons or 0,
            "balance": float(member.balance or 0),
            "start_date": str(member.start_date) if member.start_date else "",
            "end_date": str(member.end_date) if member.end_date else "",
            "staff_id": member.staff_id or "",
            "staff_name": member.staff_name or "",
        },
        "cards": card_list,
    }


@router.get("/{member_id}", response_model=MemberOut)
def get_member(member_id: str, db: Session = Depends(get_db)):
    """获取单个会员"""
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")
    return member


@router.post("", response_model=MemberOut)
def create_member(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    gender: str = Form("男"),
    phone: str = Form(...),
    level: str = Form("普通"),
    height: Optional[float] = Form(None),
    weight: Optional[float] = Form(None),
    body_fat: Optional[float] = Form(None),
    source: str = Form(""),
    remark: str = Form(""),
    birth_date: Optional[str] = Form(None),
    staff_id: str = Form(""),
    staff_name: str = Form(""),
    store_id: str = Form(""),
    wristband_id: str = Form(""),
):
    """创建会员"""
    member_id = generate_id("M", db, Member.member_id)

    member = Member(
        member_id=member_id,
        name=name,
        gender=gender,
        phone=phone,
        level=level or "普通",
        status="正常",
        source=source or "",
        remark=remark or "",
        store_id=store_id or "",
        wristband_id=wristband_id or "",
        staff_id=staff_id or "",
        staff_name=staff_name or "",
    )
    if height:
        try:
            member.height = float(height)
        except (ValueError, TypeError):
            pass
    if weight:
        try:
            member.weight = float(weight)
        except (ValueError, TypeError):
            pass
    if body_fat:
        try:
            member.body_fat = float(body_fat)
        except (ValueError, TypeError):
            pass
    if birth_date:
        try:
            member.birth_date = date.fromisoformat(str(birth_date))
        except ValueError:
            pass

    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.put("/{member_id}", response_model=MemberOut)
def update_member(
    member_id: str,
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(None),
    gender: str = Form(None),
    phone: str = Form(None),
    level: str = Form(None),
    height: Optional[float] = Form(None),
    weight: Optional[float] = Form(None),
    body_fat: Optional[float] = Form(None),
    source: str = Form(""),
    remark: str = Form(""),
    birth_date: Optional[str] = Form(None),
    staff_id: str = Form(""),
    staff_name: str = Form(""),
    store_id: str = Form(""),
    wristband_id: str = Form(""),
):
    """更新会员"""
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")

    # 如果指定了 staff_id 但 staff_name 为空，自动从员工表获取
    if staff_id and not staff_name:
        from backend.models.models import Staff
        staff = db.query(Staff).filter(Staff.staff_id == staff_id).first()
        if staff:
            staff_name = staff.name

    update_data = {
        "name": name, "gender": gender, "phone": phone, "level": level,
        "height": height, "weight": weight, "body_fat": body_fat,
        "source": source, "remark": remark,
        "staff_id": staff_id, "staff_name": staff_name,
        "store_id": store_id, "wristband_id": wristband_id,
    }
    for key, val in update_data.items():
        if val is not None and val != "":
            if key in ("height", "weight", "body_fat"):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    continue
            setattr(member, key, val)

    # 单独处理出生日期（Date 类型需要转换）
    if birth_date:
        try:
            member.birth_date = date.fromisoformat(str(birth_date))
        except ValueError:
            pass

    db.commit()
    db.refresh(member)
    return member


# ═══════════════════════════════════════════
# 详情页 Tab HTML 片段端点
# ═══════════════════════════════════════════

@router.get("/{member_id}/cards-html", response_class=HTMLResponse)
def member_cards_html(member_id: str, db: Session = Depends(get_db)):
    """会籍卡列表 HTML 片段"""
    cards = db.query(MembershipCard).filter(
        MembershipCard.member_id == member_id,
        MembershipCard.is_product == 0,
    ).order_by(MembershipCard.id.desc()).all()

    if not cards:
        return '<div class="text-center py-8 text-gray-400">暂无会籍卡</div>'

    trs = ""
    for c in cards:
        type_cls = {"次卡": "bg-blue-100 text-blue-700", "期限卡": "bg-green-100 text-green-700",
                     "现金卡": "bg-yellow-100 text-yellow-700"}
        badge = type_cls.get(c.card_type, "bg-gray-100 text-gray-700")
        remaining = ""
        if c.card_type == "次卡":
            total = c.total_classes or 0
            bonus = c.bonus_classes or 0
            total_with = total + bonus
            if total_with > 0:
                unit_val = float(c.price or 0) / total_with if total_with > 0 else 0
                used = round(float(c.consumed_amount or 0) / unit_val) if unit_val > 0 else 0
                r = max(total_with - used, 0)
                remaining = f"{r}/{total_with}次"
        elif c.card_type == "现金卡":
            bal = max(float(c.price or 0) - float(c.consumed_amount or 0), 0)
            remaining = f"¥{bal:.0f}"
        else:
            d = (c.end_date - TODAY).days if c.end_date else None
            remaining = f"{d}天" if d is not None else "-"

        st_cls = "bg-green-100 text-green-700" if c.status == "正常" else "bg-red-100 text-red-700"
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{c.card_id}</td>
            <td class="px-4 py-3 text-sm"><span class="px-2 py-0.5 {badge} rounded text-xs">{c.card_type}</span></td>
            <td class="px-4 py-3 text-sm">{c.start_date} ~ {c.end_date or '-'}</td>
            <td class="px-4 py-3 text-sm">{remaining}</td>
            <td class="px-4 py-3 text-sm">¥{float(c.price or 0):.0f}</td>
            <td class="px-4 py-3 text-sm"><span class="px-2 py-0.5 {st_cls} rounded text-xs">{c.status or ''}</span></td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">卡号</th><th class="px-4 py-3">类型</th><th class="px-4 py-3">有效期</th><th class="px-4 py-3">剩余</th><th class="px-4 py-3">售价</th><th class="px-4 py-3">状态</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("/{member_id}/checkins-html", response_class=HTMLResponse)
def member_checkins_html(member_id: str, db: Session = Depends(get_db)):
    """进场记录 HTML 片段"""
    rows = db.query(Checkin).filter(Checkin.member_id == member_id).order_by(Checkin.id.desc()).limit(30).all()
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无进场记录</div>'

    total_30 = db.query(Checkin).filter(
        Checkin.member_id == member_id,
        Checkin.checkin_date >= TODAY - timedelta(days=30)
    ).count()

    trs = ""
    for r in rows:
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm">{r.checkin_date}</td>
            <td class="px-4 py-3 text-sm">{r.checkin_time or ''}</td>
            <td class="px-4 py-3 text-sm">{r.checkin_type or ''}</td>
            <td class="px-4 py-3 text-sm">{r.consume_type or ''}</td>
            <td class="px-4 py-3 text-sm">{r.card_type or ''}</td>
            <td class="px-4 py-3 text-sm">{r.operator or ''}</td>
        </tr>"""
    return f"""<div class="text-sm text-gray-500 mb-3">近30天进场 <span class="font-bold text-blue-600">{total_30}</span> 次</div>
    <table class="w-full bg-white rounded-lg">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">日期</th><th class="px-4 py-3">时间</th><th class="px-4 py-3">类型</th><th class="px-4 py-3">核销方式</th><th class="px-4 py-3">卡类型</th><th class="px-4 py-3">操作员</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("/{member_id}/class-records-html", response_class=HTMLResponse)
def member_class_records_html(member_id: str, db: Session = Depends(get_db)):
    """上课记录 HTML 片段"""
    rows = db.query(ClassRecord).filter(ClassRecord.member_id == member_id).order_by(ClassRecord.id.desc()).limit(30).all()
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无上课记录</div>'

    trs = ""
    for r in rows:
        st_cls = "bg-green-100 text-green-700" if r.status == "已完成" else "bg-yellow-100 text-yellow-700"
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm">{r.class_date}</td>
            <td class="px-4 py-3 text-sm">{r.course_name or ''}</td>
            <td class="px-4 py-3 text-sm">{r.coach_name or ''}</td>
            <td class="px-4 py-3 text-sm">{r.consumed_hours or 0}</td>
            <td class="px-4 py-3 text-sm"><span class="px-2 py-0.5 {st_cls} rounded text-xs">{r.status or ''}</span></td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">日期</th><th class="px-4 py-3">课程</th><th class="px-4 py-3">教练</th><th class="px-4 py-3">消耗课时</th><th class="px-4 py-3">状态</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("/{member_id}/body-measurements-html", response_class=HTMLResponse)
def member_measurements_html(member_id: str, db: Session = Depends(get_db)):
    """体测记录 HTML 片段（含趋势）"""
    rows = db.query(BodyMeasurement).filter(
        BodyMeasurement.member_id == member_id
    ).order_by(BodyMeasurement.measure_date.desc()).all()
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无体测记录</div>'

    trend_html = ""
    if len(rows) >= 2:
        latest = rows[0]
        prev = rows[1]
        def _trend(label, curr, prev_val, unit=""):
            if prev_val and prev_val > 0:
                diff = float(curr or 0) - float(prev_val or 0)
                arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
                color = "text-red-500" if (label == "体重" and diff > 0) or (label == "体脂率" and diff > 0) else "text-green-500" if diff != 0 else "text-gray-400"
                return f'<span class="{color} text-xs ml-1">{arrow} {abs(diff):.1f}{unit}</span>'
            return ""
        trend_html = f"""<div class="flex gap-4 mb-3 text-sm">
            <span>体重趋势：{latest.weight}kg {_trend('体重', latest.weight, prev.weight, 'kg')}</span>
            <span>体脂趋势：{latest.body_fat}% {_trend('体脂率', latest.body_fat, prev.body_fat, '%')}</span>
            <span>BMI：{latest.bmi} {_trend('BMI', latest.bmi, prev.bmi)}</span>
        </div>"""

    trs = ""
    for b in rows:
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm">{b.measure_date}</td>
            <td class="px-4 py-3 text-sm">{b.height or '-'}</td>
            <td class="px-4 py-3 text-sm">{b.weight or '-'}</td>
            <td class="px-4 py-3 text-sm">{b.body_fat or '-'}%</td>
            <td class="px-4 py-3 text-sm">{b.bmi or '-'}</td>
            <td class="px-4 py-3 text-sm">{b.muscle_mass or '-'}</td>
            <td class="px-4 py-3 text-sm">{b.basal_metabolism or '-'}</td>
        </tr>"""
    return f"""{trend_html}
    <table class="w-full bg-white rounded-lg">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">日期</th><th class="px-4 py-3">身高</th><th class="px-4 py-3">体重</th><th class="px-4 py-3">体脂率</th><th class="px-4 py-3">BMI</th><th class="px-4 py-3">肌肉量</th><th class="px-4 py-3">基础代谢</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("/{member_id}/purchases-html", response_class=HTMLResponse)
def member_purchases_html(member_id: str, db: Session = Depends(get_db)):
    """消费记录 HTML 片段（充值 + 售课）"""
    recharges = db.query(Recharge).filter(Recharge.member_id == member_id).all()
    sales = db.query(Sale).filter(Sale.member_id == member_id).all()

    items = []
    for r in recharges:
        items.append(("充值", str(r.recharge_date) if r.recharge_date else "", f"¥{float(r.actual_amount or 0):.0f}", r.payment_method or "", r.recharge_type or ""))
    for s in sales:
        items.append(("售课", str(s.sale_date) if s.sale_date else "", f"¥{float(s.actual_amount or 0):.0f}", s.payment_method or "", s.course_name or ""))

    items.sort(key=lambda x: x[1], reverse=True)
    items = items[:30]

    if not items:
        return '<div class="text-center py-8 text-gray-400">暂无消费记录</div>'

    trs = ""
    for typ, dt, amt, method, detail in items:
        typ_cls = "bg-blue-100 text-blue-700" if typ == "充值" else "bg-green-100 text-green-700"
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm">{dt}</td>
            <td class="px-4 py-3 text-sm"><span class="px-2 py-0.5 {typ_cls} rounded text-xs">{typ}</span></td>
            <td class="px-4 py-3 text-sm font-medium">{amt}</td>
            <td class="px-4 py-3 text-sm">{method}</td>
            <td class="px-4 py-3 text-sm">{detail}</td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">日期</th><th class="px-4 py-3">类型</th><th class="px-4 py-3">金额</th><th class="px-4 py-3">支付方式</th><th class="px-4 py-3">明细</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.delete("/{member_id}")
def delete_member(member_id: str, request: Request, db: Session = Depends(get_db)):
    """删除会员"""
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="会员不存在")
    db.delete(member)
    db.commit()

    return {"success": True, "message": f"会员 {member_id} 已删除"}
