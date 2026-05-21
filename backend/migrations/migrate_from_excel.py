# -*- coding: utf-8 -*-
"""
Excel → SQLite 数据迁移工具
V3.0.0

用法:
    python scripts/migrate_from_excel.py --excel /path/to/健身房管理系统.xlsx

将原 Excel 所有 Sheet 数据迁移到 SQLite 数据库
"""
import sys, os, re
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database import SessionLocal, init_db
from backend.models.models import (
    Staff, Store, Member, MembershipCard, BodyMeasurement, Recharge,
    Course, Sale, LessonPackage, ClassRecord, Booking,
    CardProduct, GroupPackage, MonthlyPass,
    Product, ProductSale, Checkin, Wristband,
    CommissionTier, Contract, FinanceIncome, FinanceExpense,
    OperationLog, Alert,
)


def safe_int(v, default=0):
    if v is None:
        return default
    try:
        return int(float(str(v)))
    except (ValueError, TypeError):
        return default


def safe_float(v, default=0):
    if v is None:
        return default
    try:
        return float(str(v))
    except (ValueError, TypeError):
        return default


def safe_date(v):
    if v is None or str(v).strip() == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        v = v.strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(v, fmt).date()
            except ValueError:
                continue
    return None


def safe_str(v, default=""):
    if v is None:
        return default
    return str(v).strip()


def migrate_sheet(db, sheet_name, rows, model_class, field_map, extra_fixed=None):
    """通用迁移：将 Excel 行数据映射到 ORM 模型

    Args:
        db: 数据库会话
        sheet_name: Sheet 名称（仅用于日志）
        rows: 行数据列表（get_all_data 返回，每个包含 _row）
        model_class: SQLAlchemy 模型类
        field_map: dict {excel字段名: orm属性名} 或 {excel字段名: (orm属性名, 转换函数)}
        extra_fixed: 额外的固定字段值 dict
    """
    # 自动检测需要生成 ID 的字段（unique=True 且包含 _id 的列）
    auto_id_fields = []
    for col in model_class.__table__.columns:
        if col.unique and col.name.endswith('_id') and col.name != 'id':
            auto_id_fields.append(col.name)

    count = 0
    for row in rows:
        kwargs = {}
        for excel_key, mapping in field_map.items():
            val = row.get(excel_key)
            if isinstance(mapping, tuple):
                orm_key, converter = mapping
                kwargs[orm_key] = converter(val)
            else:
                kwargs[mapping] = str(val).strip() if val else ""

        # 自动补空值的 ID（unique _id 字段）
        if auto_id_fields:
            from datetime import date as _d
            for fld in auto_id_fields:
                current = kwargs.get(fld, "")
                if not current or str(current).strip() == "":
                    kwargs[fld] = f"{model_class.__tablename__[:2].upper()}{_d.today().strftime('%Y%m%d')}{count+1:04d}"

        if extra_fixed:
            kwargs.update(extra_fixed)

        obj = model_class(**kwargs)
        db.add(obj)
        count += 1

        if count % 100 == 0:
            db.flush()

    db.commit()
    print(f"  → {sheet_name}: 迁移 {count} 行")
    return count


def migrate(excel_path: str):
    """主迁移流程"""
    if not os.path.exists(excel_path):
        print(f"❌ Excel 文件不存在: {excel_path}")
        return

    from openpyxl import load_workbook
    from core.business import BusinessLayer

    init_db()
    db = SessionLocal()

    print(f"📂 加载 Excel: {excel_path}")
    biz = BusinessLayer(excel_path)
    engine = biz.engine

    total = 0

    # ── 1. 员工 ──
    print("\n📋 员工信息...")
    rows = engine.get_all_data("员工信息")
    total += migrate_sheet(db, "员工信息", rows, Staff, {
        "员工编号": "staff_id", "姓名": "name", "性别": "gender",
        "手机号": "phone", "出生日期": ("birth_date", safe_date),
        "年龄": ("age", safe_int), "岗位": "position",
        "入职日期": ("hire_date", safe_date),
        "底薪": ("base_salary", safe_float),
        "售课提成比例": ("sale_commission_rate", safe_float),
        "上课提成比例": ("class_commission_rate", safe_float),
        "售课提成额": ("sale_commission_amount", safe_float),
        "上课提成额": ("class_commission_amount", safe_float),
        "总提成额": ("total_commission", safe_float),
        "本月售课额": ("month_sale_amount", safe_float),
        "本月上课数": ("month_class_count", safe_int),
        "在职状态": "status", "身份证号": "id_card",
        "银行卡号": "bank_card", "备注": "remark", "门店编号": "store_id",
        "手环编号": "wristband_id",
    })

    # ── 2. 会员 ──
    print("\n📋 会员信息...")
    rows = engine.get_all_data("会员信息")
    total += migrate_sheet(db, "会员信息", rows, Member, {
        "会员编号": "member_id", "姓名": "name", "性别": "gender",
        "手机号": "phone", "出生日期": ("birth_date", safe_date),
        "年龄": ("age", safe_int),
        "身高(cm)": ("height", safe_float),
        "体重(kg)": ("weight", safe_float),
        "体脂率(%)": ("body_fat", safe_float),
        "会员等级": "level", "会员状态": "status",
        "开卡日期": ("start_date", safe_date),
        "到期日期": ("end_date", safe_date),
        "总购课时": ("total_lessons", safe_int),
        "已消耗课时": ("used_lessons", safe_int),
        "剩余课时": ("remaining_lessons", safe_int),
        "充值总额": ("recharge_total", safe_float),
        "剩余金额": ("balance", safe_float),
        "已消耗金额": ("consumed_amount", safe_float),
        "紧急联系人": "emergency_contact", "联系电话": "emergency_phone",
        "身份证号": "id_card", "备注": "remark",
        "累计签到天数": ("total_checkin_days", safe_int),
        "最近签到日期": ("last_checkin_date", safe_date),
        "客户来源": "source", "门店编号": "store_id",
        "手环编号": "wristband_id",
    })

    # ── 3. 课程 ──
    print("\n📋 课程项目...")
    rows = engine.get_all_data("课程项目")
    total += migrate_sheet(db, "课程项目", rows, Course, {
        "课程编号": "course_id", "课程名称": "name",
        "运动项目": "sport_type", "课程类型": "course_type",
        "标准课时": ("standard_hours", safe_int),
        "标准售价": ("standard_price", safe_float),
        "优惠售价": ("discount_price", safe_float),
        "课程有效期(天)": ("valid_days", safe_int),
        "课程状态": "status", "最大预约人数": ("max_bookings", safe_int),
        "教练": "coach", "上课地点": "location",
        "课程描述": "description", "备注": "remark",
        "门店编号": "store_id", "手环编号": "wristband_id",
    })

    # ── 4. 售课记录 ──
    print("\n📋 售课记录...")
    rows = engine.get_all_data("售课记录")
    total += migrate_sheet(db, "售课记录", rows, Sale, {
        "售课编号": "sale_id", "售课日期": ("sale_date", safe_date),
        "会员编号": "member_id", "会员姓名": "member_name",
        "会员手机号": "member_phone",
        "课程编号": "course_id", "课程名称": "course_name",
        "购买课时数": ("bought_hours", safe_int),
        "赠送课时数": ("bonus_hours", safe_int),
        "总课时数": ("total_hours", safe_int),
        "单价": ("unit_price", safe_float),
        "折扣": ("discount", safe_float),
        "折后总价": ("total_price", safe_float),
        "实收金额": ("actual_amount", safe_float),
        "定金金额": ("deposit", safe_float),
        "付款方式": "payment_method",
        "销售员工": "staff_id", "销售员姓名": "staff_name",
        "销售提成比例": ("commission_rate", safe_float),
        "销售提成额": ("commission_amount", safe_float),
        "购课来源": "source", "售课备注": "remark",
        "开卡日期": ("start_date", safe_date),
        "到期日期": ("end_date", safe_date),
        "支付状态": "payment_status",
        "剩余尾款": ("balance_due", safe_float),
        "操作员": "operator", "门店编号": "store_id",
    })

    # ── 5. 上课记录 ──
    print("\n📋 上课记录...")
    rows = engine.get_all_data("上课记录")
    total += migrate_sheet(db, "上课记录", rows, ClassRecord, {
        "上课编号": "record_id", "上课日期": ("class_date", safe_date),
        "上课时间": "start_time", "下课时间": "end_time",
        "授课教练": "coach_id", "教练姓名": "coach_name",
        "会员编号": "member_id", "会员姓名": "member_name",
        "会员手机号": "member_phone",
        "课程编号": "course_id", "课程名称": "course_name",
        "消耗课时数": ("consumed_hours", safe_int),
        "上课状态": "status", "上课评价": "evaluation",
        "会员反馈": "feedback",
        "教练上课提成比例": ("commission_rate", safe_float),
        "教练上课提成额": ("commission_amount", safe_float),
        "上课心得": "notes", "签到人数": ("sign_in_count", safe_int),
        "签到时间": ("sign_in_time", lambda v: datetime.now() if v else None),
        "门店编号": "store_id", "进场签到": "checkin_record",
    })

    # ── 6. 预约管理 ──
    print("\n📋 预约管理...")
    rows = engine.get_all_data("预约管理")
    total += migrate_sheet(db, "预约管理", rows, Booking, {
        "预约编号": "booking_id", "预约日期": ("booking_date", safe_date),
        "开始时间": "start_time", "结束时间": "end_time",
        "会员编号": "member_id", "会员姓名": "member_name",
        "会员手机号": "member_phone",
        "课程编号": "course_id", "课程名称": "course_name",
        "教练编号": "coach_id", "教练姓名": "coach_name",
        "上课地点": "location", "预约状态": "status",
        "签到人数": ("sign_in_count", safe_int),
        "门店编号": "store_id", "手环编号": "wristband_id",
    })

    # ── 7. 商品 ──
    print("\n📋 商品管理...")
    rows = engine.get_all_data("商品管理")
    total += migrate_sheet(db, "商品管理", rows, Product, {
        "商品编号": "product_id", "商品名称": "name",
        "商品类别": "category",
        "进价": ("cost_price", safe_float),
        "售价": ("selling_price", safe_float),
        "库存数量": ("stock", safe_int),
        "单位": "unit", "供应商": "supplier",
        "备注": "remark", "门店编号": "store_id",
    })

    # ── 8. 商品零售 ──
    print("\n📋 商品零售...")
    rows = engine.get_all_data("商品零售")
    total += migrate_sheet(db, "商品零售", rows, ProductSale, {
        "零售编号": "sale_id", "零售日期": ("sale_date", safe_date),
        "会员编号": "member_id", "会员姓名": "member_name",
        "商品名称": "product_name",
        "数量": ("quantity", safe_int),
        "单价": ("unit_price", safe_float),
        "总价": ("total_price", safe_float),
        "支付方式": "payment_method", "操作员": "operator",
        "备注": "remark", "门店编号": "store_id",
    })

    # ── 9. 进场记录 ──
    print("\n📋 进场记录...")
    rows = engine.get_all_data("进场记录")
    total += migrate_sheet(db, "进场记录", rows, Checkin, {
        "进场编号": "checkin_id", "会员编号": "member_id",
        "会员姓名": "member_name",
        "进场日期": ("checkin_date", safe_date),
        "进场时间": "checkin_time",
        "进场类型": "checkin_type",
        "卡片类型": "card_type", "操作员": "operator",
        "跟进员工": "staff_followup", "备注": "remark",
        "门店编号": "store_id",
    })

    # ── 10. 手环管理 ──
    print("\n📋 手环管理...")
    rows = engine.get_all_data("手环管理")
    total += migrate_sheet(db, "手环管理", rows, Wristband, {
        "手环编号": "band_id",
        "读卡器写入值": "reader_value",
        "自定义编号": "custom_id",
        "绑定会员编号": "bound_member_id",
        "绑定会员姓名": "bound_member_name",
        "绑定时间": ("bound_time", safe_date),
        "绑定状态": "status",
        "注册时间": ("register_time", safe_date),
        "备注": "remark",
    })

    # ── 11. 会员充值 ──
    print("\n📋 会员充值...")
    rows = engine.get_all_data("会员充值")
    total += migrate_sheet(db, "会员充值", rows, Recharge, {
        "充值编号": "recharge_id", "充值日期": ("recharge_date", safe_date),
        "会员编号": "member_id", "会员姓名": "member_name",
        "充值金额": ("amount", safe_float),
        "赠送金额": ("bonus", safe_float),
        "实付金额": ("actual_amount", safe_float),
        "付款方式": "payment_method",
        "充值类型": "recharge_type",
        "经办员工": "operator_id",
        "充值备注": "remark",
        "门店编号": "store_id",
    })

    # ── 12. 体测记录 ──
    print("\n📋 体测记录...")
    rows = engine.get_all_data("体测记录")
    total += migrate_sheet(db, "体测记录", rows, BodyMeasurement, {
        "体测编号": "measure_id", "会员编号": "member_id",
        "会员姓名": "member_name",
        "体测日期": ("measure_date", safe_date),
        "身高(cm)": ("height", safe_float),
        "体重(kg)": ("weight", safe_float),
        "体脂率(%)": ("body_fat", safe_float),
        "BMI": ("bmi", safe_float),
        "肌肉量(kg)": ("muscle_mass", safe_float),
        "基础代谢(kcal)": ("basal_metabolism", safe_int),
        "体年龄": ("body_age", safe_int),
        "备注": "remark", "门店编号": "store_id",
        "手环编号": "wristband_id",
    })

    # ── 13. 课程包 ──
    print("\n📋 课程包管理...")
    rows = engine.get_all_data("课程包管理")
    total += migrate_sheet(db, "课程包管理", rows, LessonPackage, {
        "课程包编号": "package_id", "售课编号": "sale_id",
        "会员编号": "member_id", "会员姓名": "member_name",
        "课程编号": "course_id", "课程名称": "course_name",
        "总课时": ("total_hours", safe_int),
        "已消耗课时": ("used_hours", safe_int),
        "剩余课时": ("remaining_hours", safe_int),
        "有效期起": ("valid_from", safe_date),
        "有效期止": ("valid_until", safe_date),
        "状态": "status", "门店编号": "store_id",
        "手环编号": "wristband_id",
    })

    # ── 14. 会籍卡 ──
    print("\n📋 会籍卡管理...")
    rows = engine.get_all_data("会籍卡管理")
    total += migrate_sheet(db, "会籍卡管理", rows, MembershipCard, {
        "会籍编号": "card_id", "会员编号": "member_id",
        "会员姓名": "member_name", "会籍类型": "card_type",
        "有效期(天)": ("duration_days", safe_int),
        "售价": ("price", safe_float),
        "有效期起": ("start_date", safe_date),
        "有效期止": ("end_date", safe_date),
        "状态": "status", "备注": "remark",
        "门店编号": "store_id",
    })

    # ── 15. 可售会籍卡 ──
    print("\n📋 可售会籍卡...")
    rows = engine.get_all_data("可售会籍卡")
    total += migrate_sheet(db, "可售会籍卡", rows, CardProduct, {
        "会籍编号": "card_id", "卡名称": "card_name",
        "有效期(天)": ("duration_days", safe_int),
        "售价": ("price", safe_float),
        "状态": "status", "描述": "description",
        "门店编号": "store_id",
    })

    # ── 16. 团课打包 ──
    print("\n📋 团课打包产品...")
    rows = engine.get_all_data("团课打包产品")
    total += migrate_sheet(db, "团课打包产品", rows, GroupPackage, {
        "打包编号": "package_id", "打包名称": "package_name",
        "包含课程": "included_courses",
        "课程名称列表": "course_names",
        "打包类型": "package_type",
        "总次数": ("total_count", safe_int),
        "标准售价": ("standard_price", safe_float),
        "优惠售价": ("discount_price", safe_float),
        "有效期(天)": ("valid_days", safe_int),
        "状态": "status",
        "创建日期": ("created_date", safe_date),
        "备注": "remark", "门店编号": "store_id",
    })

    # ── 17. 包月团课 ──
    print("\n📋 包月团课...")
    rows = engine.get_all_data("包月团课")
    total += migrate_sheet(db, "包月团课", rows, MonthlyPass, {
        "月卡编号": "pass_id", "月卡名称": "pass_name",
        "会员编号": "member_id", "会员姓名": "member_name",
        "包含课程": "included_courses",
        "课程名称列表": "course_names",
        "售价": ("price", safe_float),
        "有效期起": ("valid_from", safe_date),
        "有效期止": ("valid_until", safe_date),
        "状态": "status",
        "购买日期": ("purchase_date", safe_date),
        "备注": "remark", "门店编号": "store_id",
    })

    # ── 18. 提成梯度 ──
    print("\n📋 提成梯度配置...")
    rows = engine.get_all_data("提成梯度配置")
    total += migrate_sheet(db, "提成梯度配置", rows, CommissionTier, {
        "梯度编号": "tier_id", "类型": "type",
        "区间下限": ("min_amount", safe_float),
        "区间上限": ("max_amount", safe_float),
        "提成率(%)": ("rate", safe_float),
    })

    # ── 19. 合同 ──
    print("\n📋 合同管理...")
    rows = engine.get_all_data("合同管理")
    total += migrate_sheet(db, "合同管理", rows, Contract, {
        "合同编号": "contract_id", "合同名称": "contract_name",
        "会员编号": "member_id", "会员姓名": "member_name",
        "合同类型": "contract_type",
        "合同金额": ("amount", safe_float),
        "签订日期": ("sign_date", safe_date),
        "合同状态": "status", "备注": "remark",
        "门店编号": "store_id",
    })

    # ── 20. 操作日志 ──
    print("\n📋 操作日志...")
    rows = engine.get_all_data("操作日志")
    total += migrate_sheet(db, "操作日志", rows, OperationLog, {
        "日志编号": "log_id",
        "操作时间": ("operation_time", lambda v: datetime.now() if v else datetime.now()),
        "操作类型": "operation_type", "操作模块": "module",
        "操作详情": "detail", "操作人": "operator",
    })

    # ── 21. 到期提醒 ──
    print("\n📋 到期提醒...")
    rows = engine.get_all_data("到期提醒")
    total += migrate_sheet(db, "到期提醒", rows, Alert, {
        "预警类型": "alert_type", "预警内容": "content",
        "会员编号": "member_id", "会员姓名": "member_name",
        "到期日期": ("expire_date", safe_date),
        "预警日期": ("alert_date", safe_date),
        "剩余天数": ("remaining_days", safe_int),
        "状态": "status",
        "处理时间": ("process_time", lambda v: datetime.now() if v else None),
        "处理人": "processor", "处理结果": "result",
        "批次号": "batch_no",
    })

    # ── 22. 收入总账 ──
    print("\n📋 收入总账...")
    rows = engine.get_all_data("收入总账")
    total += migrate_sheet(db, "收入总账", rows, FinanceIncome, {
        "收入编号": "record_id", "日期": ("income_date", safe_date),
        "收入类别": "category",
        "金额": ("amount", safe_float),
        "来源": "source", "支付方式": "payment_method",
        "备注": "remark", "门店编号": "store_id",
    })

    # ── 23. 支出记录 ──
    print("\n📋 支出记录...")
    rows = engine.get_all_data("支出记录")
    total += migrate_sheet(db, "支出记录", rows, FinanceExpense, {
        "支出编号": "record_id", "日期": ("expense_date", safe_date),
        "支出类别": "category",
        "金额": ("amount", safe_float),
        "经办人": "payee", "支付方式": "payment_method",
        "备注": "remark", "门店编号": "store_id",
    })

    db.close()
    print(f"\n{'='*50}")
    print(f"🎉 迁移完成！共迁移 {total} 条记录到 {len(list(db.bind.tables)) if hasattr(db.bind, 'tables') else '(SQLite)'} 张表")
    print(f"{'='*50}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="从 Excel 迁移数据到 SQLite")
    parser.add_argument("--excel", default="",
                        help="Excel 数据文件路径（默认从 config.EXCEL_PATH 读取）")
    args = parser.parse_args()

    if args.excel:
        excel_path = args.excel
    else:
        # 默认读取桌面版的配置文件
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        "..", "gym-excel-system"))
        try:
            from config import EXCEL_PATH
            excel_path = EXCEL_PATH
        except ImportError:
            print("❌ 无法找到 Excel 路径，请用 --excel 指定")
            sys.exit(1)

    migrate(excel_path)
