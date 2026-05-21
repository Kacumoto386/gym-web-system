# -*- coding: utf-8 -*-
"""
课程包管理 API 路由 + HTMX HTML 片段端点
V3.3.4 -- 细化展示：课时进度条 + 到期提示 + 剩余课时着色
"""
from typing import Optional, List
from fastapi import Request, APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime
from backend.database import get_db
from backend.models.models import GroupPackage, LessonPackage, MonthlyPass, Course
from backend.services.id_gen import generate_id
from pydantic import BaseModel

TODAY = date.today()

router = APIRouter(prefix="/api/packages", tags=["课程包管理"])


# ═══════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════

def _remaining_days_tag(days):
    if days is None:
        return '<span class="text-gray-400">-</span>'
    if days < 0:
        return '<span class="text-red-500 font-medium">已过期</span>'
    elif days == 0:
        return '<span class="text-orange-500 font-medium">今日到期</span>'
    elif days <= 3:
        return '<span class="text-red-500 font-medium">剩{}天</span>'.format(days)
    elif days <= 7:
        return '<span class="text-orange-500 font-medium">剩{}天</span>'.format(days)
    elif days <= 30:
        return '<span class="text-yellow-600">剩{}天</span>'.format(days)
    else:
        return '<span class="text-gray-500">{}</span>'.format(days)


def _progress_bar(used, total):
    """生成进度条 HTML"""
    if total is None or total <= 0:
        return ''
    pct = min(used / total * 100, 100)
    pct_int = int(pct)
    color = "bg-green-500" if pct < 70 else ("bg-yellow-500" if pct < 90 else "bg-red-500")
    return (
        '<div class="w-full bg-gray-200 rounded-full h-2 mt-1">'
        '<div class="{} rounded-full h-2" style="width:{}%"></div>'
        '</div>'
    ).format(color, pct_int)


def _remaining_hours_style(remaining):
    """剩余课时着色"""
    if remaining is None:
        return '<span class="text-gray-400">-</span>'
    if remaining <= 0:
        return '<span class="text-gray-400">已用完</span>'
    elif remaining <= 3:
        return '<span class="text-red-500 font-medium">{}</span>'.format(remaining)
    elif remaining <= 7:
        return '<span class="text-orange-500 font-medium">{}</span>'.format(remaining)
    else:
        return '<span class="font-medium">{}</span>'.format(remaining)


# ═══════════════════════════════════════════
# Helper: 课程多选项
# ═══════════════════════════════════════════

@router.get("/courses-options", response_class=HTMLResponse)
def get_courses_options(db: Session = Depends(get_db)):
    courses = db.query(Course).filter(Course.status == "上架").all()
    opts = ""
    for c in courses:
        opts += '<option value="{}" data-name="{}">{}</option>'.format(c.course_id, c.name, c.name)
    return (
        '<select id="package_courses" name="included_courses" multiple '
        'class="w-full px-3 py-2 border rounded-lg text-sm min-h-[120px]">'
        '{}</select>'
        '<p class="text-xs text-gray-400 mt-1">按住 Ctrl 多选</p>'
    ).format(opts)


# ═══════════════════════════════════════════
# Tab 1: 产品管理 (GroupPackage)
# ═══════════════════════════════════════════

def _build_product_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-16 text-gray-400"><p class="text-3xl mb-2">📦</p><p>暂无课程包产品</p><p class="text-xs mt-1">点击右上角「新建课程包」开始</p></div>'

    cards = ""
    for r in rows:
        type_badge_cls = {"计时打包": ("📊", "bg-amber-50 text-amber-700 border-amber-200"),
                          "不限次数": ("♾️", "bg-purple-50 text-purple-700 border-purple-200")}.get(
            r.package_type, ("📋", "bg-gray-50 text-gray-600 border-gray-200"))

        up_cls = ("bg-green-100 text-green-700 border-green-200" if r.status == "上架"
                  else "bg-gray-100 text-gray-500 border-gray-200")
        up_text = r.status or "-"

        # 课程列表
        cids = [c.strip() for c in (r.included_courses or "").split(",") if c.strip()]
        cnames = [c.strip() for c in (r.course_names or "").split("/") if c.strip()]
        course_items = ""
        for i, cid in enumerate(cids):
            cname = cnames[i] if i < len(cnames) else cid
            if not cname:
                cname = cid
            course_items += (
                '<div class="flex items-center justify-between px-2.5 py-1.5 bg-white rounded-md border border-gray-100 shadow-sm hover:shadow transition-shadow">'
                '<div class="flex items-center gap-2 min-w-0">'
                '<span class="text-xs text-gray-400 font-mono shrink-0" style="font-size:10px">{}</span>'
                '<span class="text-sm font-medium truncate">{}</span>'
                '</div>'
                '<button class="text-xs text-red-400 hover:text-red-600 ml-2 shrink-0" '
                'hx-delete="/api/packages/products/{}/courses/{}" '
                'hx-target="#productTableArea" '
                'hx-confirm="从「{}」移除 {}？" title="移除此课程">✕</button>'
                '</div>'
            ).format(cid, cname, r.package_id, cid, r.package_name or '', cname)

        detail_items = []
        if r.package_type == "计时打包" and r.total_count:
            detail_items.append(("总次数", "{} 次".format(r.total_count)))
        detail_items += [
            ("售价",
             '<span class="text-lg font-bold text-red-500">\xa5{}</span>'.format(r.discount_price or 0)
             + (' <span class="line-through text-gray-400 text-xs">\xa5{}</span>'.format(r.standard_price)
                if r.standard_price and r.standard_price > (r.discount_price or 0) else '')),
            ("有效期", "{} 天".format(r.valid_days or 0)),
        ]

        details_html = "".join(
            '<div><span class="text-xs text-gray-400">{}</span><p class="text-sm font-medium">{}</p></div>'.format(k, v)
            for k, v in detail_items
        )

        cards += (
            '<div class="bg-white rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow p-5">'
            '<!-- 头部 -->'
            '<div class="flex items-start justify-between mb-3">'
            '<div class="flex-1 min-w-0">'
            '<div class="flex items-center gap-2">'
            '<h4 class="text-base font-semibold text-gray-800 truncate">{}</h4>'
            '<span class="shrink-0 text-xs px-2 py-0.5 rounded-full border {}">{}</span>'
            '</div>'
            '</div>'
            '<div class="flex items-center gap-2 shrink-0 ml-3">'
            '<span class="shrink-0 text-xs px-2 py-0.5 rounded-full border {}">{}</span>'
            '</div>'
            '</div>'
            '<!-- 课程列表 -->'
            '<div class="mb-3">'
            '<div class="flex items-center justify-between mb-1.5">'
            '<span class="text-xs font-medium text-gray-500">📚 包含课程</span>'
            '<span class="text-xs text-gray-400">{} 门</span>'
            '</div>'
            '<div class="space-y-1">{}</div>'
            '</div>'
            '<!-- 售价 & 有效期 -->'
            '<div class="grid grid-cols-2 gap-3 mb-4 p-3 bg-gray-50/70 rounded-lg">{}</div>'
            '<!-- 操作 -->'
            '<div class="flex items-center gap-2 pt-3 border-t border-gray-100">'
            '<button onclick="toggleProductStatus(\'{}\')" '
            'class="text-xs px-3 py-1.5 rounded-md {} border {}">{}</button>'
            '<button onclick="openEditProduct(\'{}\')" '
            'class="text-xs px-3 py-1.5 rounded-md bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100">编辑</button>'
            '<button onclick="openAddCourse(\'{}\',\'{}\')" '
            'class="text-xs px-3 py-1.5 rounded-md bg-indigo-50 text-indigo-600 border border-indigo-200 hover:bg-indigo-100">+ 课程</button>'
            '<button hx-delete="/api/packages/products/{}" '
            'hx-target="#productTableArea" '
            'hx-confirm="确认删除「{}」？" '
            'class="text-xs px-3 py-1.5 rounded-md bg-red-50 text-red-500 border border-red-200 hover:bg-red-100">删除</button>'
            '<div class="ml-auto text-xs text-gray-400">{}次 · {}天</div>'
            '</div>'
            '</div>'
        ).format(
            r.package_name or '',
            type_badge_cls[1], type_badge_cls[0] + ' ' + (r.package_type or ''),
            up_cls, up_text,
            len(cids),
            course_items,
            details_html,
            r.package_id,
            ('bg-green-50 text-green-600 border-green-200 hover:bg-green-100' if r.status == '上架'
             else 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'),
            ('border-green-200' if r.status == '上架' else 'border-gray-200'),
            ('下架' if r.status == '上架' else '上架'),
            r.package_id,
            r.package_id, r.package_name or '',
            r.package_id, r.package_name or '',
            r.total_count or 0, r.valid_days or 0,
        )

    return '<div class="grid gap-4 md:grid-cols-2">{}</div>'.format(cards)


@router.get("/products/table", response_class=HTMLResponse)
def product_table(db: Session = Depends(get_db)):
    rows = db.query(GroupPackage).order_by(GroupPackage.id.desc()).all()
    return NoCacheResponse(_build_product_table(rows))


# Helper for no-cache responses
from fastapi.responses import HTMLResponse as BaseHTMLResponse

class NoCacheResponse(BaseHTMLResponse):
    def __init__(self, content, *args, **kwargs):
        super().__init__(content, *args, **kwargs)
        self.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        self.headers["Pragma"] = "no-cache"
        self.headers["Expires"] = "0"


from fastapi import Form as FastForm

@router.post("/products", response_class=HTMLResponse)
def create_product_form(
    package_name: str = FastForm(...),
    package_type: str = FastForm("计时打包"),
    included_courses: str = FastForm(""),
    total_count: int = FastForm(0),
    standard_price: float = FastForm(0),
    discount_price: float = FastForm(0),
    valid_days: int = FastForm(0),
    remark: str = FastForm(""),
    db: Session = Depends(get_db),
):
    course_ids = [c.strip() for c in included_courses.split(",") if c.strip()]
    pid = generate_id("GP", db, GroupPackage.package_id)
    course_names = ""
    if course_ids:
        courses = db.query(Course).filter(Course.course_id.in_(course_ids)).all()
        name_map = {c.course_id: c.name for c in courses}
        course_names = " / ".join(name_map.get(cid, cid) for cid in course_ids)

    p = GroupPackage(
        package_id=pid,
        package_name=package_name,
        package_type=package_type,
        included_courses=",".join(course_ids),
        course_names=course_names,
        total_count=total_count,
        standard_price=standard_price,
        discount_price=discount_price,
        valid_days=valid_days,
        status="上架",
        created_date=date.today(),
        remark=remark,
    )
    db.add(p)
    db.commit()
    html = _build_product_table(db.query(GroupPackage).order_by(GroupPackage.id.desc()).all())
    return html


@router.put("/products/{package_id}", response_class=HTMLResponse)
def update_product(
    package_id: str,
    package_name: str = FastForm(""),
    package_type: str = FastForm("计时打包"),
    included_courses: str = FastForm(""),
    total_count: int = FastForm(0),
    standard_price: float = FastForm(0),
    discount_price: float = FastForm(0),
    valid_days: int = FastForm(0),
    remark: str = FastForm(""),
    db: Session = Depends(get_db),
):
    course_ids = [c.strip() for c in included_courses.split(",") if c.strip()]
    p = db.query(GroupPackage).filter(GroupPackage.package_id == package_id).first()
    if not p:
        raise HTTPException(404, "产品不存在")
    course_names = ""
    if course_ids:
        courses = db.query(Course).filter(Course.course_id.in_(course_ids)).all()
        name_map = {c.course_id: c.name for c in courses}
        course_names = " / ".join(name_map.get(cid, cid) for cid in course_ids)

    for k, v in [("package_name", package_name), ("package_type", package_type),
                  ("included_courses", ",".join(course_ids)), ("course_names", course_names),
                  ("total_count", total_count), ("standard_price", standard_price),
                  ("discount_price", discount_price), ("valid_days", valid_days),
                  ("remark", remark)]:
        setattr(p, k, v)
    db.commit()
    return _build_product_table(db.query(GroupPackage).order_by(GroupPackage.id.desc()).all())


@router.post("/products/{package_id}/toggle-status")
def toggle_product_status(package_id: str, db: Session = Depends(get_db)):
    p = db.query(GroupPackage).filter(GroupPackage.package_id == package_id).first()
    if not p:
        raise HTTPException(404, "产品不存在")
    p.status = "下架" if p.status == "上架" else "上架"
    db.commit()
    return {"success": True, "status": p.status}


@router.delete("/products/{package_id}")
def delete_product(package_id: str, db: Session = Depends(get_db)):
    p = db.query(GroupPackage).filter(GroupPackage.package_id == package_id).first()
    if not p:
        raise HTTPException(404, "产品不存在")
    db.delete(p)
    db.commit()
    return {"success": True}


# ═══════════════════════════════════════════
# Tab 2: 已售课程包（会员维度）
# ═══════════════════════════════════════════

def _build_member_table(lesson_packages: list, monthly_passes: list) -> str:
    if not lesson_packages and not monthly_passes:
        return '<div class="text-center py-8 text-gray-400">暂无已售课程包</div>'

    trs = ""

    # LessonPackage (计时课包)
    for lp in lesson_packages:
        ptype = lp.package_type if hasattr(lp, 'package_type') and lp.package_type else "normal"
        type_tag = "📗 普通课包" if ptype == "normal" else "📒 团课计次包"
        st_cls = "bg-green-100 text-green-700" if lp.status in ("有效", "正常") else "bg-red-100 text-red-500"

        used = lp.used_hours or 0
        total = lp.total_hours or 0
        remaining = lp.remaining_hours or 0

        # 课时进度
        if total > 0:
            progress = _progress_bar(used, total)
            pct = int(used / total * 100)
            progress_col = '{}/{} ({}){}'.format(used, total, str(pct) + '%', progress)
        else:
            progress_col = '{}/{}'.format(used, total)

        # 有效期 + 到期标签
        expiry_tag = ''
        if lp.valid_until:
            days = (lp.valid_until - TODAY).days
            expiry_tag = _remaining_days_tag(days)
        valid_str = '{} ~ {}<br>{}'.format(lp.valid_from or '', lp.valid_until or '', expiry_tag)

        # 剩余课时着色
        remaining_html = _remaining_hours_style(remaining)

        # 课程标签
        courses_raw = (lp.course_name or '').split('/')
        course_labels = ''.join(
            '<span class="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-100 text-blue-800 rounded-md text-xs font-medium border border-blue-200 mr-1.5 mb-1">{}</span>'.format(c.strip())
            for c in courses_raw if c.strip()
        )

        trs += (
            '<tr class="hover:bg-gray-50 border-b">'
            '<td class="px-3 py-2.5">{}</td>'
            '<td class="px-3 py-2.5 text-sm max-w-[200px]"><div class="flex flex-wrap">{}</div></td>'
            '<td class="px-3 py-2.5 text-xs">{}</td>'
            '<td class="px-3 py-2.5 text-sm">{}</td>'
            '<td class="px-3 py-2.5 text-sm">{}</td>'
            '<td class="px-3 py-2.5"><span class="px-2 py-0.5 {} rounded text-xs">{}</span></td>'
            '<td class="px-3 py-2.5 text-sm">{}</td>'
            '</tr>'
        ).format(
            lp.member_name or '',
            course_labels,
            type_tag,
            progress_col,
            valid_str,
            st_cls,
            lp.status or '-',
            remaining_html,
        )

    # MonthlyPass (包月)
    for mp in monthly_passes:
        ptype = mp.pass_type if hasattr(mp, 'pass_type') and mp.pass_type else "group"
        type_tag = "🎫 包月团课" if ptype == "group" else "🎫 包月私教"
        st_cls = "bg-green-100 text-green-700" if mp.status == "有效" else "bg-red-100 text-red-500"

        # 课程标签
        courses_raw = (mp.course_names or mp.pass_name or '').split('/')
        course_labels = ''.join(
            '<span class="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-100 text-blue-800 rounded-md text-xs font-medium border border-blue-200 mr-1.5 mb-1">{}</span>'.format(c.strip())
            for c in courses_raw if c.strip()
        )

        # 包月不显示进度
        progress_col = '<span class="text-gray-400">不限次</span>'

        # 到期标签
        expiry_tag = ''
        if mp.valid_until:
            days = (mp.valid_until - TODAY).days
            expiry_tag = _remaining_days_tag(days)
        valid_str = '{} ~ {}<br>{}'.format(mp.valid_from or '', mp.valid_until or '', expiry_tag)

        trs += (
            '<tr class="hover:bg-gray-50 border-b bg-blue-50/30">'
            '<td class="px-3 py-2.5">{}</td>'
            '<td class="px-3 py-2.5 text-sm max-w-[200px]"><div class="flex flex-wrap">{}</div></td>'
            '<td class="px-3 py-2.5 text-xs">{}</td>'
            '<td class="px-3 py-2.5 text-sm">{}</td>'
            '<td class="px-3 py-2.5 text-sm">{}</td>'
            '<td class="px-3 py-2.5"><span class="px-2 py-0.5 {} rounded text-xs">{}</span></td>'
            '<td class="px-3 py-2.5 text-sm text-green-600">不限次</td>'
            '</tr>'
        ).format(
            mp.member_name or '',
            course_labels,
            type_tag,
            progress_col,
            valid_str,
            st_cls,
            mp.status or '-',
        )

    return (
        '<table class="w-full bg-white rounded-lg shadow-sm">'
        '<thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">'
        '<tr>'
        '<th class="px-3 py-3">会员</th><th class="px-3 py-3">课程/项目</th>'
        '<th class="px-3 py-3">类型</th><th class="px-3 py-3">使用/总数</th>'
        '<th class="px-3 py-3">有效期</th><th class="px-3 py-3">状态</th>'
        '<th class="px-3 py-3">剩余</th>'
        '</tr>'
        '</thead>'
        '<tbody>{}</tbody>'
        '</table>'
    ).format(trs)


@router.get("/member-packages", response_class=HTMLResponse)
def member_packages_table(keyword: str = "", status: str = "", db: Session = Depends(get_db)):
    # LessonPackage
    lp_q = db.query(LessonPackage)
    if keyword:
        lp_q = lp_q.filter(LessonPackage.member_name.contains(keyword))
    if status:
        lp_q = lp_q.filter(LessonPackage.status == status)
    lps = lp_q.order_by(LessonPackage.id.desc()).all()

    # MonthlyPass
    mp_q = db.query(MonthlyPass)
    if keyword:
        mp_q = mp_q.filter(MonthlyPass.member_name.contains(keyword))
    if status:
        mp_q = mp_q.filter(MonthlyPass.status == status)
    mps = mp_q.order_by(MonthlyPass.id.desc()).all()

    html = _build_member_table(lps, mps)
    return NoCacheResponse(html)


# ═══════════════════════════════════════════
# 获取产品详情（编辑用）
# ═══════════════════════════════════════════

@router.get("/products/{package_id}")
def get_product(package_id: str, db: Session = Depends(get_db)):
    p = db.query(GroupPackage).filter(GroupPackage.package_id == package_id).first()
    if not p:
        raise HTTPException(404)
    return {
        "package_id": p.package_id,
        "package_name": p.package_name,
        "package_type": p.package_type,
        "included_courses": p.included_courses or "",
        "total_count": p.total_count or 0,
        "standard_price": float(p.standard_price or 0),
        "discount_price": float(p.discount_price or 0),
        "valid_days": p.valid_days or 0,
        "status": p.status,
        "remark": p.remark or "",
    }


# ════════════════════════════════════════════════════════════════════
# 课程包产品：添加/移除课程
# ════════════════════════════════════════════════════════════════════

@router.delete("/products/{package_id}/courses/{course_id}", response_class=HTMLResponse)
def remove_course_from_product(package_id: str, course_id: str, db: Session = Depends(get_db)):
    p = db.query(GroupPackage).filter(GroupPackage.package_id == package_id).first()
    if not p:
        raise HTTPException(404, "课程包不存在")

    cids = [c.strip() for c in (p.included_courses or "").split(",") if c.strip()]
    if course_id not in cids:
        raise HTTPException(400, "该课程不在课程包中")

    cids.remove(course_id)
    p.included_courses = ",".join(cids)

    # 更新 course_names
    if cids:
        courses = db.query(Course).filter(Course.course_id.in_(cids)).all()
        name_map = {c.course_id: c.name for c in courses}
        p.course_names = " / ".join(name_map.get(cid, cid) for cid in cids)
    else:
        p.course_names = ""
    db.commit()
    return _build_product_table(db.query(GroupPackage).order_by(GroupPackage.id.desc()).all())


from fastapi import Form as CourseForm

@router.post("/products/{package_id}/courses", response_class=HTMLResponse)
def add_course_to_product(
    package_id: str,
    course_id: str = CourseForm(...),
    db: Session = Depends(get_db),
):
    p = db.query(GroupPackage).filter(GroupPackage.package_id == package_id).first()
    if not p:
        raise HTTPException(404, "课程包不存在")

    cids = [c.strip() for c in (p.included_courses or "").split(",") if c.strip()]
    if course_id in cids:
        pass  # 已存在，不重复添加
    else:
        cids.append(course_id)
        p.included_courses = ",".join(cids)
        courses = db.query(Course).filter(Course.course_id.in_(cids)).all()
        name_map = {c.course_id: c.name for c in courses}
        p.course_names = " / ".join(name_map.get(cid, cid) for cid in cids)
    db.commit()
    return _build_product_table(db.query(GroupPackage).order_by(GroupPackage.id.desc()).all())
