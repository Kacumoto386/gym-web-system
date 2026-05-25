# -*- coding: utf-8 -*-
"""
数据导入模块 — 标准模板导入 + 进度跟踪
V3.8.2
"""
from typing import Optional, List, Tuple
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from sqlalchemy.orm import Session
from backend.database import get_db, SessionLocal
from backend.models.models import ImportTask, Member, Staff, Course
from backend.services.id_gen import generate_id
from backend.routers.export_data import CN_NAMES
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment
import io, json, os, threading
from datetime import date, datetime
from decimal import Decimal

router = APIRouter(prefix="/api/import", tags=["数据导入"])

# ═══════════════════════════════════════════
# 导入类型配置
# ═══════════════════════════════════════════

# (field, chinese_header, required)
IMPORT_FIELDS = {
    "member": [
        ("name", "姓名*", True),
        ("phone", "手机号*", True),
        ("gender", "性别", False),
        ("birth_date", "出生日期", False),
        ("height", "身高(cm)", False),
        ("weight", "体重(kg)", False),
        ("body_fat", "体脂率(%)", False),
        ("level", "会员等级", False),
        ("status", "状态", False),
        ("start_date", "开卡日期", False),
        ("end_date", "到期日期", False),
        ("source", "客户来源", False),
        ("staff_id", "跟进员工编号", False),
        ("remark", "备注", False),
        ("id_card", "身份证号", False),
    ],
    "staff": [
        ("name", "姓名*", True),
        ("phone", "手机号*", True),
        ("gender", "性别", False),
        ("birth_date", "出生日期", False),
        ("position", "岗位", False),
        ("hire_date", "入职日期", False),
        ("base_salary", "底薪", False),
        ("status", "状态", False),
        ("id_card", "身份证号", False),
        ("bank_card", "银行卡号", False),
        ("sale_commission_rate", "售课提成比例(%)", False),
        ("class_commission_rate", "上课提成比例(%)", False),
    ],
    "course": [
        ("name", "课程名称*", True),
        ("sport_type", "运动项目", False),
        ("course_type", "课程类型", False),
        ("standard_hours", "标准课时", False),
        ("standard_price", "标准售价", False),
        ("discount_price", "优惠售价", False),
        ("valid_days", "有效期(天)", False),
        ("status", "状态", False),
        ("coach", "教练", False),
    ],
}

# Chinese header → field mapping per type
def _build_header_map(import_type: str) -> dict:
    """构建中文表头 → 字段名映射"""
    return {hdr: fld for fld, hdr, _ in IMPORT_FIELDS[import_type]}

# Type config
TYPE_CONFIG = {
    "member": {
        "model": Member,
        "id_prefix": "M",
        "key_field": "phone",
        "name": "会员",
    },
    "staff": {
        "model": Staff,
        "id_prefix": "S",
        "key_field": "phone",
        "name": "员工",
    },
    "course": {
        "model": Course,
        "id_prefix": "C",
        "key_field": "name",
        "name": "课程",
    },
}

# Date fields per type (these need date parsing)
DATE_FIELDS = {
    "member": {"birth_date", "start_date", "end_date"},
    "staff": {"birth_date", "hire_date"},
    "course": set(),
}

# Decimal fields per type
DECIMAL_FIELDS = {
    "member": {"height", "weight", "body_fat"},
    "staff": {"base_salary", "sale_commission_rate", "class_commission_rate"},
    "course": {"standard_price", "discount_price"},
}

# Protected fields per type (never overwritten during upsert)
PROTECTED_FIELDS = {
    "member": {"member_id", "balance", "recharge_total", "consumed_amount",
               "total_lessons", "used_lessons", "remaining_lessons",
               "total_checkin_days", "last_checkin_date", "photo_path",
               "created_at", "updated_at"},
    "staff": {"staff_id", "sale_commission_amount", "class_commission_amount",
              "total_commission", "month_sale_amount", "month_class_count",
              "month_sale_commission", "month_class_commission", "month_total_commission",
              "today_class_count", "created_at", "updated_at"},
    "course": {"course_id", "max_bookings", "location", "description",
               "remark", "store_id", "wristband_id", "created_at"},
}


# ═══════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════

def _parse_cell_value(val, field: str, import_type: str):
    """将 openpyxl 单元格值转换为合适的 Python 类型"""
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return None
    if field in DATE_FIELDS.get(import_type, set()):
        # Handle both datetime objects and strings
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        if isinstance(val, str):
            try:
                return date.fromisoformat(val.strip())
            except ValueError:
                return None
        return val
    if field in DECIMAL_FIELDS.get(import_type, set()):
        try:
            return Decimal(str(val))
        except (ValueError, TypeError):
            return Decimal(0)
    # String fields
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, (int, float)):
        return val
    return str(val)


def _type_name_cn(import_type: str) -> str:
    names = {"member": "会员", "staff": "员工", "course": "课程"}
    return names.get(import_type, import_type)


# ═══════════════════════════════════════════
# 模板下载 — GET /api/import/template/{type}
# ═══════════════════════════════════════════

@router.get("/template/{import_type}")
def download_template(import_type: str):
    """下载导入模板 XLSX"""
    if import_type not in IMPORT_FIELDS:
        raise HTTPException(404, f"不支持的导入类型: {import_type}")

    fields = IMPORT_FIELDS[import_type]
    wb = Workbook()
    ws = wb.active
    ws.title = f"{_type_name_cn(import_type)}导入模板"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center")
    hint_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

    # Row 1: Chinese headers
    headers = [hdr for _, hdr, _ in fields]
    for ci, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # Row 2: example / hint row
    hints = _get_hint_row(import_type)
    for ci, h in enumerate(hints, 1):
        cell = ws.cell(row=2, column=ci, value=h)
        cell.fill = hint_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Column widths
    for ci, h in enumerate(headers, 1):
        ws.column_dimensions[chr(64 + ci) if ci <= 26 else 'A'].width = max(14, min(len(h) * 2 + 4, 36))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    ascii_name = f"{import_type}_template.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{ascii_name}"',
        },
    )


def _get_hint_row(import_type: str) -> list:
    """获取模板的示例行"""
    hints = {
        "member": [
            "张三", "13800138000", "男", "1990-01-01",
            "170", "65", "15", "普通", "正常",
            "2025-01-01", "2025-12-31", "门店推广", "S20250101001", "无", "",
        ],
        "staff": [
            "李四", "13900139000", "男", "1995-06-15",
            "教练", "2025-03-01", "5000", "在职", "", "", "30", "50",
        ],
        "course": [
            "减脂塑形课", "健身", "私教课", "24", "3000", "2500", "90", "上架", "王教练",
        ],
    }
    return hints.get(import_type, [])


# ═══════════════════════════════════════════
# 上传解析 — POST /api/import/upload
# ═══════════════════════════════════════════

@router.post("/upload")
def upload_import_file(
    file: UploadFile = File(...),
    import_type: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """上传并解析导入文件，返回预览数据"""
    if import_type not in IMPORT_FIELDS:
        raise HTTPException(400, f"不支持的导入类型: {import_type}")

    if not file.filename or not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "请上传 .xlsx 格式的文件")

    # Read file
    content = file.file.read()
    try:
        wb = load_workbook(io.BytesIO(content))
        ws = wb.active
    except Exception as e:
        raise HTTPException(400, f"文件解析失败: {str(e)}")

    if ws.max_row < 2:
        raise HTTPException(400, "文件中没有数据（至少需要表头行 + 1行数据）")

    # Parse headers
    header_map = _build_header_map(import_type)
    raw_headers = [str(ws.cell(row=1, column=c).value or "").strip() for c in range(1, ws.max_column + 1)]

    # Map Chinese headers to field names
    col_mapping = {}  # column index (0-based) → field name
    for ci, h in enumerate(raw_headers):
        if h in header_map:
            col_mapping[ci] = header_map[h]

    if not col_mapping:
        raise HTTPException(400, "未能识别表头，请使用下载的模板填写")

    required_fields = {fld for fld, _, req in IMPORT_FIELDS[import_type] if req}
    mapped_fields = set(col_mapping.values())
    missing = required_fields - mapped_fields
    if missing:
        missing_names = [hdr for fld, hdr, _ in IMPORT_FIELDS[import_type] if fld in missing]
        raise HTTPException(400, f"缺少必填列: {', '.join(missing_names)}")

    # Parse data rows
    all_rows = []
    errors = []
    for ri in range(2, ws.max_row + 1):
        row_data = {}
        has_data = False
        for ci, field in col_mapping.items():
            raw_val = ws.cell(row=ri, column=ci + 1).value
            val = _parse_cell_value(raw_val, field, import_type)
            if val is not None:
                has_data = True
            row_data[field] = val
        if not has_data:
            continue  # skip empty rows

        # Validate required
        row_valid = True
        for fld in required_fields:
            val = row_data.get(fld)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                errors.append({"row": ri, "field": fld, "message": f"「{dict(IMPORT_FIELDS[import_type])[fld]}」不能为空"})
                row_valid = False
        if row_valid:
            all_rows.append(row_data)

    if not all_rows:
        raise HTTPException(400, "没有有效的数据行")

    # Create ImportTask
    operator = "系统"
    if request:
        token = request.cookies.get("access_token", "")
        if token:
            from jose import jwt
            from backend.routers.auth import SECRET_KEY, ALGORITHM
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                operator = payload.get("sub", "系统")
            except Exception:
                pass

    task_id = generate_id("IT", db, ImportTask.task_id)
    preview = all_rows[:20]

    # 存储全部数据用于后台执行（JSON 序列化）
    task = ImportTask(
        task_id=task_id,
        import_type=import_type,
        status="confirming",
        total_rows=len(all_rows),
        preview_data=json.dumps(all_rows, ensure_ascii=False, default=str),
        filename=file.filename or "",
        operator=operator,
    )
    db.add(task)
    db.commit()

    # 构建字段名→中文名映射
    field_to_cn = {fld: hdr for fld, hdr, _ in IMPORT_FIELDS[import_type]}

    return {
        "task_id": task_id,
        "import_type": import_type,
        "total_rows": len(all_rows),
        "error_count": len(errors),
        "errors": errors,
        "preview": preview,
        "header_fields": list(col_mapping.values()),
        "header_names": [field_to_cn.get(f, f) for f in col_mapping.values()],
    }


# ═══════════════════════════════════════════
# 确认执行 — POST /api/import/{task_id}/execute
# ═══════════════════════════════════════════

@router.post("/{task_id}/execute")
def execute_import(task_id: str, db: Session = Depends(get_db)):
    """确认并开始执行导入（后台线程执行）"""
    task = db.query(ImportTask).filter(ImportTask.task_id == task_id).first()
    if not task:
        raise HTTPException(404, "导入任务不存在")
    if task.status not in ("confirming", "pending"):
        raise HTTPException(400, f"任务状态不正确（当前: {task.status}），无法执行")

    task.status = "pending"
    db.commit()

    # 使用 threading.Thread 确保后台可靠执行
    thread = threading.Thread(target=_run_import, args=(task_id, task.import_type), daemon=True)
    thread.start()

    return {"success": True, "message": "导入任务已启动", "task_id": task_id}


def _run_import(task_id: str, import_type: str):
    """后台线程执行导入（逐行 upsert）"""
    db = SessionLocal()
    try:
        task = db.query(ImportTask).filter(ImportTask.task_id == task_id).first()
        if not task:
            return

        task.status = "processing"
        db.commit()

        # 读取全部行数据
        rows_data = json.loads(task.preview_data or "[]")

        # 修复类型：JSON 反序列化后 date/Decimal 变成字符串
        date_fields = DATE_FIELDS.get(import_type, set())
        decimal_fields = DECIMAL_FIELDS.get(import_type, set())
        for row in rows_data:
            for fld in date_fields:
                v = row.get(fld)
                if isinstance(v, str) and v.strip():
                    try:
                        row[fld] = date.fromisoformat(v.strip())
                    except ValueError:
                        row[fld] = None
            for fld in decimal_fields:
                v = row.get(fld)
                if v is not None and v != '':
                    try:
                        row[fld] = Decimal(str(v))
                    except (ValueError, TypeError):
                        row[fld] = Decimal(0)

        config = TYPE_CONFIG.get(import_type)
        if not config:
            task.status = "failed"
            task.errors = json.dumps([{"row": 0, "message": f"未知导入类型: {import_type}"}])
            db.commit()
            return

        key_field = config["key_field"]
        protected = PROTECTED_FIELDS.get(import_type, set())

        total = len(rows_data)
        success = 0
        error_list = []
        created = 0
        updated = 0
        skipped = 0

        for i, row in enumerate(rows_data):
            try:
                key_val = row.get(key_field)
                if not key_val or (isinstance(key_val, str) and key_val.strip() == ""):
                    error_list.append({"row": i + 2, "field": key_field, "message": "匹配字段为空"})
                    skipped += 1
                    continue

                key_val = str(key_val).strip()
                existing = _find_existing(db, import_type, key_field, key_val)

                if existing:
                    _update_record(existing, row, key_field, protected)
                    updated += 1
                else:
                    _create_record(db, import_type, row)
                    created += 1

                success += 1

            except Exception as e:
                error_list.append({"row": i + 2, "message": str(e)})

            # 每 10 行更新进度
            if (i + 1) % 10 == 0 or i == total - 1:
                task.success_count = success
                task.error_count = len(error_list)
                task.created_count = created
                task.updated_count = updated
                task.skipped_count = skipped
                task.errors = json.dumps(error_list, ensure_ascii=False)
                db.commit()

        task.status = "completed"
        task.completed_at = datetime.now()
        task.success_count = success
        task.error_count = len(error_list)
        task.created_count = created
        task.updated_count = updated
        task.skipped_count = skipped
        task.errors = json.dumps(error_list, ensure_ascii=False)
        db.commit()

    except Exception as e:
        try:
            task = db.query(ImportTask).filter(ImportTask.task_id == task_id).first()
            if task:
                task.status = "failed"
                task.errors = json.dumps([{"row": 0, "message": str(e)}], ensure_ascii=False)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _find_existing(db: Session, import_type: str, key_field: str, key_val: str):
    """查找已有记录（用于 upsert）"""
    if import_type == "member":
        return db.query(Member).filter(Member.phone == key_val).first()
    elif import_type == "staff":
        return db.query(Staff).filter(Staff.phone == key_val).first()
    elif import_type == "course":
        return db.query(Course).filter(Course.name == key_val).first()
    return None


def _update_record(record, row: dict, key_field: str, protected: set):
    """更新已有记录的字段"""
    for field, val in row.items():
        if field == key_field or field in protected:
            continue
        if val is not None:
            setattr(record, field, val)


def _create_record(db: Session, import_type: str, row: dict):
    """创建新记录"""
    if import_type == "member":
        new_id = generate_id("M", db, Member.member_id)
        obj = Member(member_id=new_id)
    elif import_type == "staff":
        new_id = generate_id("S", db, Staff.staff_id)
        obj = Staff(staff_id=new_id)
    elif import_type == "course":
        new_id = generate_id("C", db, Course.course_id)
        obj = Course(course_id=new_id)
    else:
        return

    for field, val in row.items():
        if val is not None:
            setattr(obj, field, val)
    db.add(obj)


# ═══════════════════════════════════════════
# 进度查询 — GET /api/import/{task_id}/progress
# ═══════════════════════════════════════════

@router.get("/{task_id}/progress")
def get_import_progress(task_id: str, db: Session = Depends(get_db)):
    """查询导入进度"""
    task = db.query(ImportTask).filter(ImportTask.task_id == task_id).first()
    if not task:
        raise HTTPException(404, "导入任务不存在")

    return {
        "task_id": task.task_id,
        "import_type": task.import_type,
        "status": task.status,
        "total_rows": task.total_rows,
        "success_count": task.success_count,
        "error_count": task.error_count,
        "created_count": task.created_count,
        "updated_count": task.updated_count,
        "skipped_count": task.skipped_count,
        "errors": json.loads(task.errors or "[]"),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


# ═══════════════════════════════════════════
# 导入历史 — HTMX 表格
# ═══════════════════════════════════════════

TYPE_CN = {"member": "会员", "staff": "员工", "course": "课程"}
STATUS_CN = {
    "pending": "等待中", "parsing": "解析中", "confirming": "待确认",
    "processing": "导入中", "completed": "已完成", "failed": "失败",
}
STATUS_CLS = {
    "completed": "text-green-600", "failed": "text-red-600",
    "processing": "text-blue-600", "pending": "text-gray-500",
    "confirming": "text-yellow-600",
}


@router.get("/history/table", response_class=HTMLResponse)
def import_history_table(db: Session = Depends(get_db)):
    """导入历史 HTML 表格"""
    tasks = db.query(ImportTask).order_by(ImportTask.created_at.desc()).limit(50).all()
    if not tasks:
        return '<div class="text-center py-8 text-gray-400">暂无导入记录</div>'

    rows = ""
    for t in tasks:
        status_cn = STATUS_CN.get(t.status, t.status)
        status_cls = STATUS_CLS.get(t.status, "text-gray-500")
        type_cn = TYPE_CN.get(t.import_type, t.import_type)
        completed = t.completed_at.strftime('%Y-%m-%d %H:%M') if t.completed_at else '-'

        # 操作按钮：待确认 → 可执行
        if t.status == "confirming":
            action_btn = f"""<button class="text-blue-600 hover:text-blue-800 text-xs"
                hx-post="/api/import/{t.task_id}/execute"
                hx-swap="none"
                hx-on::after-request="if(event.detail.successful){{ htmx.ajax('GET','/api/import/history/table',{{target:'#historyTable',swap:'innerHTML'}}); alert('导入任务已启动'); }}">
                执行导入</button>"""
        else:
            action_btn = '<span class="text-gray-400 text-xs">-</span>'

        rows += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm">{t.task_id}</td>
            <td class="px-4 py-3 text-sm">{type_cn}</td>
            <td class="px-4 py-3 text-sm">{t.filename}</td>
            <td class="px-4 py-3 text-sm">{t.total_rows}</td>
            <td class="px-4 py-3 text-sm text-green-600">{t.success_count}</td>
            <td class="px-4 py-3 text-sm text-red-600">{t.error_count}</td>
            <td class="px-4 py-3 text-sm text-blue-600">{t.created_count}</td>
            <td class="px-4 py-3 text-sm text-orange-600">{t.updated_count}</td>
            <td class="px-4 py-3 text-sm {status_cls} font-medium">{status_cn}</td>
            <td class="px-4 py-3 text-sm">{completed}</td>
            <td class="px-4 py-3 text-sm">{t.operator}</td>
            <td class="px-4 py-3 text-sm">{action_btn}</td>
        </tr>"""

    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">任务编号</th><th class="px-4 py-3">类型</th><th class="px-4 py-3">文件</th>
                <th class="px-4 py-3">总行数</th><th class="px-4 py-3">成功</th><th class="px-4 py-3">失败</th>
                <th class="px-4 py-3">新建</th><th class="px-4 py-3">更新</th><th class="px-4 py-3">状态</th>
                <th class="px-4 py-3">完成时间</th><th class="px-4 py-3">操作人</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>"""


@router.get("/history")
def import_history_list(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """导入历史 JSON 列表"""
    tasks = db.query(ImportTask).order_by(ImportTask.created_at.desc()).offset(skip).limit(limit).all()
    return [
        {
            "task_id": t.task_id,
            "import_type": t.import_type,
            "status": t.status,
            "total_rows": t.total_rows,
            "success_count": t.success_count,
            "error_count": t.error_count,
            "created_count": t.created_count,
            "updated_count": t.updated_count,
            "filename": t.filename,
            "operator": t.operator,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in tasks
    ]
