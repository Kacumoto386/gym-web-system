# -*- coding: utf-8 -*-
"""
数据导出模块 - CSV/Excel 导出
V3.0.0
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from backend.database import get_db
import io
import csv

# 所有可导出的表
EXPORT_TABLES = {
    "members": "会员信息",
    "staff": "员工信息",
    "courses": "课程信息",
    "sales": "售课记录",
    "class_records": "上课记录",
    "checkins": "进场记录",
    "wristbands": "手环管理",
    "body_measurements": "体测记录",
    "recharges": "充值记录",
    "membership_cards": "会籍卡管理",
    "products": "商品管理",
    "product_sales": "商品零售",
    "finance_income": "收入记录",
    "finance_expense": "支出记录",
    "operation_logs": "操作日志",
}

router = APIRouter(prefix="/api/export", tags=["数据导出"])


def model_to_dict(row, columns) -> dict:
    """ORM 行转 dict，自动提取列名"""
    d = {}
    for col in columns:
        val = getattr(row, col, "")
        if val is None:
            val = ""
        d[col] = val
    return d


@router.get("/tables")
def list_tables():
    """列出所有可导出表"""
    return [{"key": k, "name": v} for k, v in EXPORT_TABLES.items()]


@router.get("/{table_name}")
def export_csv(
    table_name: str,
    format: str = Query("csv", pattern="^(csv)$"),
    db: Session = Depends(get_db),
):
    """导出指定表为 CSV"""
    from backend.models.models import (
        Member, Staff, Course, Sale, ClassRecord, Checkin, Wristband,
        BodyMeasurement, Recharge, MembershipCard, Product, ProductSale,
        FinanceIncome, FinanceExpense,
    )
    from backend.routers.operation_log import OperationLog

    model_map = {
        "members": Member,
        "staff": Staff,
        "courses": Course,
        "sales": Sale,
        "class_records": ClassRecord,
        "checkins": Checkin,
        "wristbands": Wristband,
        "body_measurements": BodyMeasurement,
        "recharges": Recharge,
        "membership_cards": MembershipCard,
        "products": Product,
        "product_sales": ProductSale,
        "finance_income": FinanceIncome,
        "finance_expense": FinanceExpense,
        "operation_logs": OperationLog,
    }

    model = model_map.get(table_name)
    if not model:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"表 {table_name} 不存在")

    # 获取所有列名（排除 id）
    mapper = inspect(model)
    columns = [c.key for c in mapper.attrs if c.key != 'id']

    rows = db.query(model).order_by(model.id).all()

    # 生成 CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # 中文列名映射
    col_names = {c: c for c in columns}  # 默认英文名
    cn_names = {
        # 通用
        "member_id": "会员编号", "member_name": "会员姓名",
        "staff_id": "员工编号", "course_id": "课程编号", "sale_id": "售课编号",
        "record_id": "记录编号", "card_id": "卡号", "band_id": "手环编号",
        "product_id": "商品编号", "sale_id": "零售编号",
        # 会员
        "name": "姓名", "gender": "性别", "phone": "手机号",
        "member_type": "会员类型", "source": "来源",
        "status": "状态", "balance": "余额",
        # 员工
        "position": "岗位", "base_salary": "底薪", "sale_commission_rate": "售课提成",
        # 课程
        "course_name": "课程名", "course_type": "课程类型", "sport_type": "运动类型",
        "standard_hours": "标准课时", "standard_price": "标准价", "discount_price": "优惠价",
        # 售课/上课
        "sale_date": "售课日期", "class_date": "上课日期", "checkin_date": "进场日期",
        "unit_price": "单价", "total_price": "总价", "actual_amount": "实收金额",
        # 财务
        "income_date": "收入日期", "expense_date": "支出日期",
        "amount": "金额", "category": "类别",
        "payment_method": "支付方式",
        "payee": "收款方",
        # 体测
        "height": "身高", "weight": "体重", "body_fat": "体脂率",
        "muscle_mass": "肌肉量", "bmi": "BMI", "basal_metabolism": "基础代谢",
        # 充值
        "recharge_amount": "充值金额", "bonus_amount": "赠送金额",
        # 会籍卡
        "card_type": "卡类型", "duration_days": "有效期", "price": "售价",
        "start_date": "开始日期", "end_date": "截止日期",
        # 商品
        "cost_price": "进价", "selling_price": "售价",
        "stock": "库存", "unit": "单位", "supplier": "供应商",
        # 零售
        "product_name": "商品名", "quantity": "数量",
        # 操作日志
        "username": "操作人", "action": "操作", "resource": "资源",
        "resource_id": "资源ID", "detail": "详情",
        "created_at": "操作时间", "ip_address": "IP地址",
        # 通用日期
        "hire_date": "入职日期", "birth_date": "出生日期",
        "signup_date": "注册日期", "measure_date": "测量日期",
        "recharge_date": "充值日期", "remind_date": "提醒日期",
        "valid_days": "有效期", "max_bookings": "最大预约数",
        # 其他
        "coach": "教练", "location": "地点",
        "id_card": "身份证", "bank_card": "银行卡",
        "remark": "备注", "operator": "操作人",
    }

    headers = []
    for c in columns:
        headers.append(cn_names.get(c, c))
    writer.writerow(headers)

    for row in rows:
        vals = []
        for c in columns:
            val = getattr(row, c, "")
            if val is None:
                val = ""
            # 处理 date/datetime
            if hasattr(val, 'isoformat'):
                val = val.isoformat()
            vals.append(str(val))
        writer.writerow(vals)

    content = output.getvalue()
    output.close()

    # 文件名 - 用纯 ASCII 安全的方式
    safe_name = EXPORT_TABLES.get(table_name, table_name).encode('ascii', 'ignore').decode('ascii') or 'export'
    date_str = datetime.now().strftime('%Y%m%d')

    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_{date_str}.csv"',
            "Content-Type": "text/csv; charset=utf-8-sig",
        },
    )


from datetime import datetime
