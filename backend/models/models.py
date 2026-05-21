"""
数据模型 - 所有 SQLAlchemy ORM 模型
V3.0.0 - 对应原 Excel 的 20+ Sheet 页
"""
from datetime import date, datetime
from sqlalchemy import func
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, DECIMAL, ForeignKey
)
from backend.database import Base


# ═══════════════════════════════════════════
# 1. 组织架构
# ═══════════════════════════════════════════

class Staff(Base):
    """员工信息"""
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, autoincrement=True)
    staff_id = Column(String(20), unique=True, nullable=False, comment="员工编号")
    name = Column(String(50), nullable=False, comment="姓名")
    gender = Column(String(4), default="", comment="性别")
    phone = Column(String(20), default="", comment="手机号")
    birth_date = Column(Date, nullable=True, comment="出生日期")
    age = Column(Integer, default=0, comment="年龄")
    position = Column(String(50), default="", comment="岗位")
    hire_date = Column(Date, nullable=True, comment="入职日期")
    base_salary = Column(DECIMAL(10, 2), default=0, comment="底薪")
    sale_commission_rate = Column(DECIMAL(5, 2), default=0, comment="售课提成比例(%)")
    class_commission_rate = Column(DECIMAL(5, 2), default=0, comment="上课提成比例(%)")
    sale_commission_amount = Column(DECIMAL(10, 2), default=0, comment="售课提成额")
    class_commission_amount = Column(DECIMAL(10, 2), default=0, comment="上课提成额")
    total_commission = Column(DECIMAL(10, 2), default=0, comment="总提成额")
    month_sale_amount = Column(DECIMAL(10, 2), default=0, comment="本月售课额")
    month_class_count = Column(Integer, default=0, comment="本月上课数")
    month_sale_commission = Column(DECIMAL(10, 2), default=0, comment="本月售课提成")
    month_class_commission = Column(DECIMAL(10, 2), default=0, comment="本月上课提成")
    month_total_commission = Column(DECIMAL(10, 2), default=0, comment="本月总提成")
    today_class_count = Column(Integer, default=0, comment="今日上课数")
    status = Column(String(10), default="在职", comment="在职状态")
    id_card = Column(String(20), default="", comment="身份证号")
    bank_card = Column(String(30), default="", comment="银行卡号")
    remark = Column(Text, default="", comment="备注")
    store_id = Column(String(20), default="", comment="门店编号")
    wristband_id = Column(String(20), default="", comment="手环编号")

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Store(Base):
    """门店管理"""
    __tablename__ = "store"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(20), unique=True, nullable=False, comment="门店编号")
    name = Column(String(100), nullable=False, comment="门店名称")
    address = Column(String(200), default="", comment="地址")
    phone = Column(String(20), default="", comment="电话")
    status = Column(String(10), default="正常", comment="状态")
    remark = Column(Text, default="", comment="备注")

    created_at = Column(DateTime, default=datetime.now)


# ═══════════════════════════════════════════
# 2. 会员管理
# ═══════════════════════════════════════════

class Member(Base):
    """会员信息"""
    __tablename__ = "member"

    id = Column(Integer, primary_key=True, autoincrement=True)
    member_id = Column(String(20), unique=True, nullable=False, comment="会员编号")
    name = Column(String(50), nullable=False, comment="姓名")
    gender = Column(String(4), default="", comment="性别")
    phone = Column(String(20), default="", comment="手机号")
    birth_date = Column(Date, nullable=True, comment="出生日期")
    age = Column(Integer, default=0, comment="年龄")
    height = Column(DECIMAL(5, 1), default=0, comment="身高(cm)")
    weight = Column(DECIMAL(5, 1), default=0, comment="体重(kg)")
    body_fat = Column(DECIMAL(4, 1), default=0, comment="体脂率(%)")
    level = Column(String(20), default="普通", comment="会员等级")
    status = Column(String(10), default="正常", comment="会员状态")
    start_date = Column(Date, nullable=True, comment="开卡日期")
    end_date = Column(Date, nullable=True, comment="到期日期")
    total_lessons = Column(Integer, default=0, comment="总购课时")
    used_lessons = Column(Integer, default=0, comment="已消耗课时")
    remaining_lessons = Column(Integer, default=0, comment="剩余课时")
    recharge_total = Column(DECIMAL(10, 2), default=0, comment="充值总额")
    balance = Column(DECIMAL(10, 2), default=0, comment="剩余金额")
    consumed_amount = Column(DECIMAL(10, 2), default=0, comment="已消耗金额")
    emergency_contact = Column(String(50), default="", comment="紧急联系人")
    emergency_phone = Column(String(20), default="", comment="联系电话")
    id_card = Column(String(20), default="", comment="身份证号")
    remark = Column(Text, default="", comment="备注")
    total_checkin_days = Column(Integer, default=0, comment="累计签到天数")
    last_checkin_date = Column(Date, nullable=True, comment="最近签到日期")
    source = Column(String(20), default="", comment="客户来源")
    store_id = Column(String(20), default="", comment="门店编号")
    wristband_id = Column(String(20), default="", comment="手环编号")
    photo_path = Column(String(200), default="", comment="照片路径")
    staff_id = Column(String(20), default="", comment="跟进员工编号")
    staff_name = Column(String(50), default="", comment="跟进员工姓名")

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class MembershipCard(Base):
    """会籍卡管理"""
    __tablename__ = "membership_card"

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(String(20), unique=True, nullable=False, comment="会籍编号")
    member_id = Column(String(20), nullable=False, comment="会员编号")
    member_name = Column(String(50), default="", comment="会员姓名")
    card_type = Column(String(50), default="", comment="会籍类型")
    duration_days = Column(Integer, default=0, comment="有效期(天)")
    price = Column(DECIMAL(10, 2), default=0, comment="售价/储值金额")
    face_value = Column(DECIMAL(10, 2), default=0, comment="现金卡面值(仅展示)")
    start_date = Column(Date, nullable=True, comment="有效期起")
    end_date = Column(Date, nullable=True, comment="有效期止")
    status = Column(String(10), default="正常", comment="状态")
    remark = Column(Text, default="", comment="备注")
    store_id = Column(String(20), default="", comment="门店编号")
    total_classes = Column(Integer, default=0, comment="总次数(次卡专用)")
    bonus_classes = Column(Integer, default=0, comment="赠送次数(次卡专用)")
    is_product = Column(Integer, default=0, comment="是否为卡产品模板(1=产品模板,0=已售卡)")
    consumed_amount = Column(DECIMAL(10, 2), default=0, comment="现金卡已扣减金额")
    card_name = Column(String(100), default="", comment="卡名称/套餐名称")

    created_at = Column(DateTime, default=datetime.now)


class BodyMeasurement(Base):
    """体测记录"""
    __tablename__ = "body_measurement"

    id = Column(Integer, primary_key=True, autoincrement=True)
    measure_id = Column(String(20), unique=True, nullable=False, comment="体测编号")
    member_id = Column(String(20), nullable=False, comment="会员编号")
    member_name = Column(String(50), default="", comment="会员姓名")
    measure_date = Column(Date, nullable=True, comment="体测日期")
    height = Column(DECIMAL(5, 1), default=0, comment="身高(cm)")
    weight = Column(DECIMAL(5, 1), default=0, comment="体重(kg)")
    body_fat = Column(DECIMAL(4, 1), default=0, comment="体脂率(%)")
    bmi = Column(DECIMAL(4, 1), default=0, comment="BMI")
    muscle_mass = Column(DECIMAL(5, 1), default=0, comment="肌肉量(kg)")
    basal_metabolism = Column(Integer, default=0, comment="基础代谢(kcal)")
    body_age = Column(Integer, default=0, comment="体年龄")
    remark = Column(Text, default="", comment="备注")
    store_id = Column(String(20), default="", comment="门店编号")
    wristband_id = Column(String(20), default="", comment="手环编号")

    created_at = Column(DateTime, default=datetime.now)


class Recharge(Base):
    """会员充值"""
    __tablename__ = "recharge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recharge_id = Column(String(20), unique=True, nullable=False, comment="充值编号")
    recharge_date = Column(Date, nullable=False, comment="充值日期")
    member_id = Column(String(20), nullable=False, comment="会员编号")
    member_name = Column(String(50), default="", comment="会员姓名")
    amount = Column(DECIMAL(10, 2), default=0, comment="充值金额")
    bonus = Column(DECIMAL(10, 2), default=0, comment="赠送金额")
    actual_amount = Column(DECIMAL(10, 2), default=0, comment="实付金额")
    payment_method = Column(String(20), default="", comment="付款方式")
    recharge_type = Column(String(20), default="", comment="充值类型")
    operator_id = Column(String(20), default="", comment="经办员工")
    remark = Column(Text, default="", comment="充值备注")
    store_id = Column(String(20), default="", comment="门店编号")

    created_at = Column(DateTime, default=datetime.now)


# ═══════════════════════════════════════════
# 3. 课程与上课
# ═══════════════════════════════════════════

class Course(Base):
    """课程项目"""
    __tablename__ = "course"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(String(20), unique=True, nullable=False, comment="课程编号")
    name = Column(String(100), nullable=False, comment="课程名称")
    sport_type = Column(String(50), default="", comment="运动项目")
    course_type = Column(String(20), default="", comment="课程类型")
    standard_hours = Column(Integer, default=1, comment="标准课时")
    standard_price = Column(DECIMAL(10, 2), default=0, comment="标准售价")
    discount_price = Column(DECIMAL(10, 2), default=0, comment="优惠售价")
    valid_days = Column(Integer, default=0, comment="课程有效期(天)")
    status = Column(String(10), default="上架", comment="课程状态")
    max_bookings = Column(Integer, default=0, comment="最大预约人数")
    coach = Column(String(50), default="", comment="教练")
    location = Column(String(100), default="", comment="上课地点")
    description = Column(Text, default="", comment="课程描述")
    remark = Column(Text, default="", comment="备注")
    store_id = Column(String(20), default="", comment="门店编号")
    wristband_id = Column(String(20), default="", comment="手环编号")

    created_at = Column(DateTime, default=datetime.now)


class Sale(Base):
    """售课记录"""
    __tablename__ = "sale"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(String(20), unique=True, nullable=False, comment="售课编号")
    sale_date = Column(Date, nullable=False, comment="售课日期")
    member_id = Column(String(20), nullable=False, comment="会员编号")
    member_name = Column(String(50), default="", comment="会员姓名")
    member_phone = Column(String(20), default="", comment="会员手机号")
    course_id = Column(String(20), default="", comment="课程编号")
    course_name = Column(String(100), default="", comment="课程名称")
    bought_hours = Column(Integer, default=0, comment="购买课时数")
    bonus_hours = Column(Integer, default=0, comment="赠送课时数")
    total_hours = Column(Integer, default=0, comment="总课时数")
    unit_price = Column(DECIMAL(10, 2), default=0, comment="单价")
    discount = Column(DECIMAL(5, 2), default=1, comment="折扣")
    total_price = Column(DECIMAL(10, 2), default=0, comment="折后总价")
    actual_amount = Column(DECIMAL(10, 2), default=0, comment="实收金额")
    deposit = Column(DECIMAL(10, 2), default=0, comment="定金金额")
    payment_method = Column(String(20), default="", comment="付款方式")
    staff_id = Column(String(20), default="", comment="销售员工")
    staff_name = Column(String(50), default="", comment="销售员姓名")
    commission_rate = Column(DECIMAL(5, 2), default=0, comment="销售提成比例(%)")
    commission_amount = Column(DECIMAL(10, 2), default=0, comment="销售提成额")
    source = Column(String(20), default="", comment="购课来源")
    remark = Column(Text, default="", comment="售课备注")
    start_date = Column(Date, nullable=True, comment="开卡日期")
    end_date = Column(Date, nullable=True, comment="到期日期")
    payment_status = Column(String(10), default="已付清", comment="支付状态")
    balance_due = Column(DECIMAL(10, 2), default=0, comment="剩余尾款")
    operator = Column(String(50), default="", comment="操作员")
    store_id = Column(String(20), default="", comment="门店编号")

    created_at = Column(DateTime, default=datetime.now)


class LessonPackage(Base):
    """课程包管理"""
    __tablename__ = "lesson_package"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(String(20), unique=True, nullable=False, comment="课程包编号")
    sale_id = Column(String(20), default="", comment="售课编号")
    member_id = Column(String(20), nullable=False, comment="会员编号")
    member_name = Column(String(50), default="", comment="会员姓名")
    course_id = Column(String(20), default="", comment="课程编号")
    course_name = Column(String(100), default="", comment="课程名称")
    total_hours = Column(Integer, default=0, comment="总课时")
    used_hours = Column(Integer, default=0, comment="已消耗课时")
    remaining_hours = Column(Integer, default=0, comment="剩余课时")
    valid_from = Column(Date, nullable=True, comment="有效期起")
    valid_until = Column(Date, nullable=True, comment="有效期止")
    status = Column(String(10), default="正常", comment="状态")
    package_type = Column(String(20), default="normal", comment="包类型(normal=普通课包/group=团课计次包)")
    included_courses = Column(Text, default="", comment="包含课程ID列表(逗号分隔)")
    course_names = Column(Text, default="", comment="包含课程名称列表")
    store_id = Column(String(20), default="", comment="门店编号")
    wristband_id = Column(String(20), default="", comment="手环编号")

    created_at = Column(DateTime, default=datetime.now)


class ClassRecord(Base):
    """上课记录"""
    __tablename__ = "class_record"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(String(20), unique=True, nullable=False, comment="上课编号")
    class_date = Column(Date, nullable=False, comment="上课日期")
    start_time = Column(String(10), default="", comment="上课时间")
    end_time = Column(String(10), default="", comment="下课时间")
    coach_id = Column(String(20), default="", comment="授课教练")
    coach_name = Column(String(50), default="", comment="教练姓名")
    member_id = Column(String(20), nullable=False, comment="会员编号")
    member_name = Column(String(50), default="", comment="会员姓名")
    member_phone = Column(String(20), default="", comment="会员手机号")
    course_id = Column(String(20), default="", comment="课程编号")
    course_name = Column(String(100), default="", comment="课程名称")
    consumed_hours = Column(Integer, default=1, comment="消耗课时数")
    status = Column(String(10), default="已完成", comment="上课状态")
    evaluation = Column(String(20), default="", comment="上课评价")
    feedback = Column(Text, default="", comment="会员反馈")
    commission_rate = Column(DECIMAL(5, 2), default=0, comment="教练上课提成比例(%)")
    commission_amount = Column(DECIMAL(10, 2), default=0, comment="教练上课提成额")
    notes = Column(Text, default="", comment="上课心得")
    sign_in_count = Column(Integer, default=1, comment="签到人数")
    sign_in_time = Column(DateTime, nullable=True, comment="签到时间")
    store_id = Column(String(20), default="", comment="门店编号")
    checkin_record = Column(String(10), default="", comment="进场签到")

    created_at = Column(DateTime, default=datetime.now)


class Booking(Base):
    """预约管理"""
    __tablename__ = "booking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(String(20), unique=True, nullable=False, comment="预约编号")
    booking_date = Column(Date, nullable=False, comment="预约日期")
    start_time = Column(String(10), default="", comment="开始时间")
    end_time = Column(String(10), default="", comment="结束时间")
    member_id = Column(String(20), nullable=False, comment="会员编号")
    member_name = Column(String(50), default="", comment="会员姓名")
    member_phone = Column(String(20), default="", comment="会员手机号")
    course_id = Column(String(20), default="", comment="课程编号")
    course_name = Column(String(100), default="", comment="课程名称")
    coach_id = Column(String(20), default="", comment="教练编号")
    coach_name = Column(String(50), default="", comment="教练姓名")
    location = Column(String(100), default="", comment="上课地点")
    status = Column(String(10), default="已预约", comment="预约状态")
    sign_in_count = Column(Integer, default=0, comment="签到人数")
    store_id = Column(String(20), default="", comment="门店编号")
    wristband_id = Column(String(20), default="", comment="手环编号")

    created_at = Column(DateTime, default=datetime.now)


# ═══════════════════════════════════════════
# 4. 会籍套餐
# ═══════════════════════════════════════════

class CardProduct(Base):
    """可售会籍卡"""
    __tablename__ = "card_product"

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(String(20), unique=True, nullable=False, comment="会籍编号")
    card_name = Column(String(100), nullable=False, comment="卡名称")
    duration_days = Column(Integer, default=0, comment="有效期(天)")
    price = Column(DECIMAL(10, 2), default=0, comment="售价")
    status = Column(String(10), default="上架", comment="状态")
    description = Column(Text, default="", comment="描述")
    store_id = Column(String(20), default="", comment="门店编号")

    created_at = Column(DateTime, default=datetime.now)


class GroupPackage(Base):
    """团课打包产品"""
    __tablename__ = "group_package"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_id = Column(String(20), unique=True, nullable=False, comment="打包编号")
    package_name = Column(String(100), nullable=False, comment="打包名称")
    included_courses = Column(Text, default="", comment="包含课程")
    course_names = Column(Text, default="", comment="课程名称列表")
    package_type = Column(String(20), default="", comment="打包类型")
    total_count = Column(Integer, default=0, comment="总次数")
    standard_price = Column(DECIMAL(10, 2), default=0, comment="标准售价")
    discount_price = Column(DECIMAL(10, 2), default=0, comment="优惠售价")
    valid_days = Column(Integer, default=0, comment="有效期(天)")
    status = Column(String(10), default="上架", comment="状态")
    created_date = Column(Date, nullable=True, comment="创建日期")
    remark = Column(Text, default="", comment="备注")
    store_id = Column(String(20), default="", comment="门店编号")

    created_at = Column(DateTime, default=datetime.now)


class MonthlyPass(Base):
    """包月团课/包月私教"""
    __tablename__ = "monthly_pass"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pass_id = Column(String(20), unique=True, nullable=False, comment="月卡编号")
    pass_name = Column(String(100), nullable=False, comment="月卡名称")
    member_id = Column(String(20), nullable=False, comment="会员编号")
    member_name = Column(String(50), default="", comment="会员姓名")
    pass_type = Column(String(20), default="group", comment="类型(group=包月团课/private=包月私教)")
    included_courses = Column(Text, default="", comment="包含课程")
    course_names = Column(Text, default="", comment="课程名称列表")
    price = Column(DECIMAL(10, 2), default=0, comment="售价")
    valid_from = Column(Date, nullable=True, comment="有效期起")
    valid_until = Column(Date, nullable=True, comment="有效期止")
    status = Column(String(10), default="正常", comment="状态")
    purchase_date = Column(Date, nullable=True, comment="购买日期")
    remark = Column(Text, default="", comment="备注")
    store_id = Column(String(20), default="", comment="门店编号")

    created_at = Column(DateTime, default=datetime.now)


# ═══════════════════════════════════════════
# 5. 商品零售
# ═══════════════════════════════════════════

class Product(Base):
    """商品管理"""
    __tablename__ = "product"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(20), unique=True, nullable=False, comment="商品编号")
    name = Column(String(100), nullable=False, comment="商品名称")
    category = Column(String(50), default="", comment="商品类别")
    cost_price = Column(DECIMAL(10, 2), default=0, comment="进价")
    selling_price = Column(DECIMAL(10, 2), default=0, comment="售价")
    stock = Column(Integer, default=0, comment="库存数量")
    unit = Column(String(10), default="个", comment="单位")
    supplier = Column(String(100), default="", comment="供应商")
    remark = Column(Text, default="", comment="备注")
    store_id = Column(String(20), default="", comment="门店编号")
    wristband_id = Column(String(20), default="", comment="手环编号")

    created_at = Column(DateTime, default=datetime.now)


class ProductSale(Base):
    """商品零售"""
    __tablename__ = "product_sale"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(String(20), unique=True, nullable=False, comment="零售编号")
    sale_date = Column(Date, nullable=False, comment="零售日期")
    member_id = Column(String(20), default="", comment="会员编号")
    member_name = Column(String(50), default="", comment="会员姓名")
    product_name = Column(String(100), nullable=False, comment="商品名称")
    quantity = Column(Integer, default=1, comment="数量")
    unit_price = Column(DECIMAL(10, 2), default=0, comment="单价")
    total_price = Column(DECIMAL(10, 2), default=0, comment="总价")
    payment_method = Column(String(20), default="", comment="支付方式")
    operator = Column(String(50), default="", comment="操作员")
    remark = Column(Text, default="", comment="备注")
    store_id = Column(String(20), default="", comment="门店编号")
    wristband_id = Column(String(20), default="", comment="手环编号")

    created_at = Column(DateTime, default=datetime.now)


# ═══════════════════════════════════════════
# 6. 进场与手环
# ═══════════════════════════════════════════

class Checkin(Base):
    """进场记录"""
    __tablename__ = "checkin"

    id = Column(Integer, primary_key=True, autoincrement=True)
    checkin_id = Column(String(20), unique=True, nullable=False, comment="进场编号")
    member_id = Column(String(20), nullable=False, comment="会员编号")
    member_name = Column(String(50), default="", comment="会员姓名")
    checkin_date = Column(Date, nullable=False, comment="进场日期")
    checkin_time = Column(String(10), default="", comment="进场时间")
    checkin_type = Column(String(20), default="", comment="进场类型")
    card_type = Column(String(50), default="", comment="卡片类型")
    card_id = Column(String(20), default="", comment="核销会籍卡编号")
    consume_type = Column(String(20), default="", comment="核销方式(次卡/储值/期限)")
    consume_detail = Column(String(100), default="", comment="核销明细")
    operator = Column(String(50), default="", comment="操作员")
    staff_followup = Column(String(50), default="", comment="跟进员工")
    remark = Column(Text, default="", comment="备注")
    store_id = Column(String(20), default="", comment="门店编号")

    created_at = Column(DateTime, default=datetime.now)


class Wristband(Base):
    """手环管理"""
    __tablename__ = "wristband"

    id = Column(Integer, primary_key=True, autoincrement=True)
    band_id = Column(String(20), unique=True, nullable=False, comment="手环编号")
    reader_value = Column(String(50), unique=True, nullable=False, comment="读卡器写入值")
    custom_id = Column(String(50), default="", comment="自定义编号")
    bound_member_id = Column(String(20), default="", comment="绑定会员编号")
    bound_member_name = Column(String(50), default="", comment="绑定会员姓名")
    bound_time = Column(Date, nullable=True, comment="绑定时间")
    status = Column(String(10), default="未绑定", comment="绑定状态")
    register_time = Column(Date, nullable=False, comment="注册时间")
    remark = Column(Text, default="", comment="备注")

    created_at = Column(DateTime, default=datetime.now)


# ═══════════════════════════════════════════
# 7. 财务与统计
# ═══════════════════════════════════════════

class CommissionTier(Base):
    """提成梯度配置"""
    __tablename__ = "commission_tier"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tier_id = Column(String(20), unique=True, nullable=False, comment="梯度编号")
    type = Column(String(20), nullable=False, comment="类型(售课/上课)")
    min_amount = Column(DECIMAL(10, 2), default=0, comment="区间下限")
    max_amount = Column(DECIMAL(10, 2), default=0, comment="区间上限")
    rate = Column(DECIMAL(5, 2), default=0, comment="提成率(%)")

    created_at = Column(DateTime, default=datetime.now)


class Contract(Base):
    """合同管理"""
    __tablename__ = "contract"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(20), unique=True, nullable=False, comment="合同编号")
    contract_name = Column(String(100), default="", comment="合同名称")
    member_id = Column(String(20), default="", comment="会员编号")
    member_name = Column(String(50), default="", comment="会员姓名")
    contract_type = Column(String(20), default="", comment="合同类型")
    amount = Column(DECIMAL(10, 2), default=0, comment="合同金额")
    sign_date = Column(Date, nullable=True, comment="签订日期")
    status = Column(String(10), default="正常", comment="合同状态")
    remark = Column(Text, default="", comment="备注")
    store_id = Column(String(20), default="", comment="门店编号")

    created_at = Column(DateTime, default=datetime.now)


# ═══════════════════════════════════════════
# 8. 收入/支出
# ═══════════════════════════════════════════

class FinanceIncome(Base):
    """收入总账"""
    __tablename__ = "finance_income"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(String(20), unique=True, nullable=False, comment="收入编号")
    income_date = Column(Date, nullable=False, comment="收入日期")
    category = Column(String(50), default="", comment="收入类别")
    amount = Column(DECIMAL(10, 2), default=0, comment="金额")
    source = Column(String(100), default="", comment="来源")
    payment_method = Column(String(20), default="", comment="支付方式")
    remark = Column(Text, default="", comment="备注")
    store_id = Column(String(20), default="", comment="门店编号")

    created_at = Column(DateTime, default=datetime.now)


class FinanceExpense(Base):
    """支出记录"""
    __tablename__ = "finance_expense"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(String(20), unique=True, nullable=False, comment="支出编号")
    expense_date = Column(Date, nullable=False, comment="支出日期")
    category = Column(String(50), default="", comment="支出类别")
    amount = Column(DECIMAL(10, 2), default=0, comment="金额")
    payee = Column(String(100), default="", comment="收款方")
    payment_method = Column(String(20), default="", comment="支付方式")
    remark = Column(Text, default="", comment="备注")
    store_id = Column(String(20), default="", comment="门店编号")

    created_at = Column(DateTime, default=datetime.now)


# ═══════════════════════════════════════════
# 9. 系统
# ═══════════════════════════════════════════

class OperationLog(Base):
    """操作日志"""
    __tablename__ = "operation_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    log_id = Column(String(20), unique=True, nullable=False, comment="日志编号")
    operation_time = Column(DateTime, default=datetime.now, comment="操作时间")
    operation_type = Column(String(20), default="", comment="操作类型")
    module = Column(String(50), default="", comment="操作模块")
    detail = Column(Text, default="", comment="操作详情")
    operator = Column(String(50), default="", comment="操作人")
    ip_address = Column(String(50), default="", comment="IP地址")

    created_at = Column(DateTime, default=datetime.now)


class Alert(Base):
    """到期提醒"""
    __tablename__ = "alert"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(String(20), nullable=False, comment="预警类型")
    content = Column(Text, default="", comment="预警内容")
    member_id = Column(String(20), default="", comment="会员编号")
    member_name = Column(String(50), default="", comment="会员姓名")
    expire_date = Column(Date, nullable=True, comment="到期日期")
    alert_date = Column(Date, nullable=True, comment="预警日期")
    remaining_days = Column(Integer, default=0, comment="剩余天数")
    status = Column(String(10), default="未处理", comment="状态")
    process_time = Column(DateTime, nullable=True, comment="处理时间")
    processor = Column(String(50), default="", comment="处理人")
    result = Column(Text, default="", comment="处理结果")
    batch_no = Column(String(50), default="", comment="批次号")

    created_at = Column(DateTime, default=datetime.now)
