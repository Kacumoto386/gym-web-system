"""
业务工具定义
===========
将健身房管理系统的所有 CRUD 操作封装为 ToolExecutor 可执行的工具。

每个模块对应一个工具注册函数，返回 List[ToolDefinition]。
"""

from __future__ import annotations
import json
from typing import Any, Dict, List, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal

from backend.database import get_db
from backend.models.models import (
    Member, Staff, Course, Sale, ClassRecord, Checkin, Wristband,
    MembershipCard, Product, ProductSale, BodyMeasurement, Recharge,
    GroupPackage, LessonPackage, MonthlyPass, Booking,
    Store, FinanceIncome, FinanceExpense, Alert,
)
from backend.mcp.executor import (
    ToolDefinition, ToolResult, PermissionMode,
)

# ═══════════════════════════════════════════
# Helper 函数
# ═══════════════════════════════════════════

def _json_safe(obj: Any) -> Any:
    """将任意 Python 对象转为 JSON 安全格式"""
    if obj is None:
        return None
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    # SQLAlchemy 模型实例：有 __table__ 属性
    if hasattr(obj, "__table__"):
        cols = {c.name: _json_safe(getattr(obj, c.name)) for c in obj.__table__.columns}
        return cols
    # SQLAlchemy Row（无 __table__）：尝试 dict 转换
    if hasattr(obj, "_mapping"):
        return {k: _json_safe(v) for k, v in obj._mapping.items()}
    if hasattr(obj, "_asdict"):
        return {k: _json_safe(v) for k, v in obj._asdict().items()}
    # 普通 dict/list
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(item) for item in obj]
    # 兜底：尝试 JSON 序列化；失败时转为字符串
    try:
        json.dumps(obj, ensure_ascii=False)
        return obj
    except (TypeError, ValueError):
        s = str(obj)
        # 排除 Python 默认的 __repr__ 垃圾文本
        if s == '[object Object]':
            return str(type(obj).__name__)
        return s


def _get_db_session():
    """获取数据库会话（记得关闭）"""
    return next(get_db())


# ═══════════════════════════════════════════
# 会员管理工具
# ═══════════════════════════════════════════

def register_member_tools() -> List[ToolDefinition]:
    """注册所有会员相关工具"""
    
    def get_member(member_id: str = "", phone: str = "", name: str = "") -> ToolResult:
        """查询会员信息。支持按编号/手机号/姓名搜索"""
        db = _get_db_session()
        try:
            query = db.query(Member)
            if member_id:
                m = query.filter(Member.member_id == member_id).first()
            elif phone:
                m = query.filter(Member.phone == phone).first()
            elif name:
                m = query.filter(Member.name.like(f"%{name}%")).first()
            else:
                # 返回最近10个会员
                ms = query.order_by(Member.id.desc()).limit(10).all()
                return ToolResult.ok(data=[_json_safe(m) for m in ms])
            
            if not m:
                return ToolResult.fail(f"未找到会员")
            return ToolResult.ok(data=_json_safe(m))
        finally:
            db.close()
    
    def list_members(page: int = 1, page_size: int = 20, status: str = "", keyword: str = "") -> ToolResult:
        """分页查询会员列表"""
        db = _get_db_session()
        try:
            query = db.query(Member)
            if status:
                query = query.filter(Member.status == status)
            if keyword:
                query = query.filter(
                    Member.name.like(f"%{keyword}%") |
                    Member.phone.like(f"%{keyword}%") |
                    Member.member_id.like(f"%{keyword}%")
                )
            total = query.count()
            ms = query.order_by(Member.id.desc()).offset((page-1)*page_size).limit(page_size).all()
            return ToolResult.ok(data={
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [_json_safe(m) for m in ms],
            })
        finally:
            db.close()
    
    def create_member(
        name: str, phone: str = "", gender: str = "",
        birth_date: str = "", id_card: str = "",
        member_type: str = "普通会员", source: str = "到店",
        remark: str = "",
    ) -> ToolResult:
        """创建新会员"""
        db = _get_db_session()
        try:
            # 生成会员编号
            from backend.services.id_gen import generate_id
            from backend.routers.auto_num import auto_number
            member_id = auto_number.get("会员") or f"M{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            m = Member(
                member_id=member_id,
                name=name, phone=phone, gender=gender,
                birth_date=date.fromisoformat(birth_date) if birth_date else None,
                id_card=id_card,
                member_type=member_type, source=source,
                status="正常", remark=remark,
            )
            db.add(m)
            db.commit()
            return ToolResult.ok(data=_json_safe(m))
        except Exception as e:
            db.rollback()
            return ToolResult.fail(f"创建会员失败: {e}")
        finally:
            db.close()
    
    def update_member(member_id: str, **kwargs) -> ToolResult:
        """更新会员信息"""
        db = _get_db_session()
        try:
            m = db.query(Member).filter(Member.member_id == member_id).first()
            if not m:
                return ToolResult.fail(f"会员 {member_id} 未找到")
            for k, v in kwargs.items():
                if hasattr(m, k) and v is not None:
                    if k == "birth_date" and isinstance(v, str):
                        v = date.fromisoformat(v)
                    setattr(m, k, v)
            db.commit()
            return ToolResult.ok(data=_json_safe(m))
        except Exception as e:
            db.rollback()
            return ToolResult.fail(f"更新会员失败: {e}")
        finally:
            db.close()
    
    def delete_member(member_id: str) -> ToolResult:
        """删除会员（危险操作）"""
        db = _get_db_session()
        try:
            m = db.query(Member).filter(Member.member_id == member_id).first()
            if not m:
                return ToolResult.fail(f"会员 {member_id} 未找到")
            db.delete(m)
            db.commit()
            return ToolResult.ok(data={"deleted": member_id})
        except Exception as e:
            db.rollback()
            return ToolResult.fail(f"删除会员失败: {e}")
        finally:
            db.close()
    
    def get_member_balance(member_id: str) -> ToolResult:
        """查询会员储值余额"""
        db = _get_db_session()
        try:
            # 从会员表拿余额
            m = db.query(Member).filter(Member.member_id == member_id).first()
            if not m:
                return ToolResult.fail(f"会员 {member_id} 未找到")
            # 计算剩余储值
            from sqlalchemy import func
            total_recharge = db.query(func.coalesce(func.sum(Recharge.amount), 0)).filter(
                Recharge.member_id == member_id,
                Recharge.payment_method != "扣次",
            ).scalar()
            return ToolResult.ok(data={
                "member_id": member_id,
                "name": m.name,
                "total_recharge": float(total_recharge),
            })
        finally:
            db.close()
    
    return [
        ToolDefinition(
            name="get_member",
            description="查询会员信息。支持按 member_id(会员编号), phone(手机号) 或 name(姓名) 搜索",
            input_schema={
                "type": "object",
                "properties": {
                    "member_id": {"type": "string", "description": "会员编号，如 M20260505001"},
                    "phone": {"type": "string", "description": "手机号"},
                    "name": {"type": "string", "description": "姓名"},
                },
            },
            handler=get_member,
            permission_mode=PermissionMode.READ_ONLY,
            category="会员管理",
            tags=["查询", "会员"],
        ),
        ToolDefinition(
            name="list_members",
            description="分页查询会员列表",
            input_schema={
                "type": "object",
                "properties": {
                    "page": {"type": "integer", "default": 1},
                    "page_size": {"type": "integer", "default": 20},
                    "status": {"type": "string", "description": "会员状态筛选"},
                    "keyword": {"type": "string", "description": "搜索关键词(姓名/手机/编号)"},
                },
            },
            handler=list_members,
            permission_mode=PermissionMode.READ_ONLY,
            category="会员管理",
            tags=["列表", "会员"],
        ),
        ToolDefinition(
            name="create_member",
            description="创建新会员",
            input_schema={
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "description": "会员姓名"},
                    "phone": {"type": "string", "description": "手机号"},
                    "gender": {"type": "string", "enum": ["男", "女", ""]},
                    "birth_date": {"type": "string", "description": "出生日期 YYYY-MM-DD"},
                    "id_card": {"type": "string", "description": "身份证号"},
                    "member_type": {"type": "string", "description": "会员类型"},
                    "source": {"type": "string", "description": "来源"},
                },
            },
            handler=create_member,
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            category="会员管理",
            tags=["创建", "会员"],
        ),
        ToolDefinition(
            name="update_member",
            description="更新会员信息",
            input_schema={
                "type": "object",
                "required": ["member_id"],
                "properties": {
                    "member_id": {"type": "string", "description": "会员编号"},
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "gender": {"type": "string"},
                    "remark": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
            handler=update_member,
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            category="会员管理",
            tags=["更新", "会员"],
        ),
        ToolDefinition(
            name="delete_member",
            description="⚠️ 删除会员（不可恢复）",
            input_schema={
                "type": "object",
                "required": ["member_id"],
                "properties": {
                    "member_id": {"type": "string", "description": "会员编号"},
                },
            },
            handler=delete_member,
            permission_mode=PermissionMode.DANGER_FULL_ACCESS,
            category="会员管理",
            tags=["删除", "会员", "危险"],
        ),
        ToolDefinition(
            name="get_member_balance",
            description="查询会员储值余额",
            input_schema={
                "type": "object",
                "required": ["member_id"],
                "properties": {
                    "member_id": {"type": "string", "description": "会员编号"},
                },
            },
            handler=get_member_balance,
            permission_mode=PermissionMode.READ_ONLY,
            category="会员管理",
            tags=["储值", "余额"],
        ),
    ]


# ═══════════════════════════════════════════
# 员工管理工具
# ═══════════════════════════════════════════

def register_staff_tools() -> List[ToolDefinition]:
    
    def get_staff(staff_id: str = "", name: str = "") -> ToolResult:
        """查询员工信息"""
        db = _get_db_session()
        try:
            query = db.query(Staff)
            if staff_id:
                s = query.filter(Staff.staff_id == staff_id).first()
            elif name:
                s = query.filter(Staff.name.like(f"%{name}%")).first()
            else:
                ss = query.order_by(Staff.id.desc()).limit(10).all()
                return ToolResult.ok(data=[_json_safe(s) for s in ss])
            if not s:
                return ToolResult.fail("员工未找到")
            return ToolResult.ok(data=_json_safe(s))
        finally:
            db.close()
    
    def list_staff(page: int = 1, page_size: int = 20, position: str = "", keyword: str = "") -> ToolResult:
        """分页查询员工列表"""
        db = _get_db_session()
        try:
            query = db.query(Staff)
            if position:
                query = query.filter(Staff.position == position)
            if keyword:
                query = query.filter(Staff.name.like(f"%{keyword}%"))
            total = query.count()
            ss = query.order_by(Staff.id.desc()).offset((page-1)*page_size).limit(page_size).all()
            return ToolResult.ok(data={
                "total": total, "items": [_json_safe(s) for s in ss],
            })
        finally:
            db.close()
    
    return [
        ToolDefinition(
            name="get_staff", description="查询员工信息",
            input_schema={"type": "object", "properties": {
                "staff_id": {"type": "string"}, "name": {"type": "string"},
            }},
            handler=get_staff, permission_mode=PermissionMode.READ_ONLY,
            category="员工管理", tags=["查询", "员工"],
        ),
        ToolDefinition(
            name="list_staff", description="分页查询员工列表",
            input_schema={"type": "object", "properties": {
                "page": {"type": "integer"}, "page_size": {"type": "integer"},
                "position": {"type": "string"}, "keyword": {"type": "string"},
            }},
            handler=list_staff, permission_mode=PermissionMode.READ_ONLY,
            category="员工管理", tags=["列表", "员工"],
        ),
    ]


# ═══════════════════════════════════════════
# 课程管理工具
# ═══════════════════════════════════════════

def register_course_tools() -> List[ToolDefinition]:
    
    def list_courses(course_type: str = "", keyword: str = "") -> ToolResult:
        """查询课程列表"""
        db = _get_db_session()
        try:
            query = db.query(Course)
            if course_type:
                query = query.filter(Course.course_type == course_type)
            if keyword:
                query = query.filter(Course.name.like(f"%{keyword}%"))
            cs = query.order_by(Course.id.desc()).all()
            return ToolResult.ok(data=[_json_safe(c) for c in cs])
        finally:
            db.close()
    
    def get_course_stats() -> ToolResult:
        """课程统计数据：总数、类型分布、价格区间"""
        db = _get_db_session()
        try:
            from sqlalchemy import func
            total = db.query(Course).count()
            type_dist = db.query(Course.course_type, func.count(Course.id)).group_by(Course.course_type).all()
            return ToolResult.ok(data={
                "total": total,
                "types": {t: int(c) for t, c in type_dist},
            })
        finally:
            db.close()
    
    return [
        ToolDefinition(
            name="list_courses", description="查询课程列表",
            input_schema={"type": "object", "properties": {
                "course_type": {"type": "string"}, "keyword": {"type": "string"},
            }},
            handler=list_courses, permission_mode=PermissionMode.READ_ONLY,
            category="课程管理", tags=["课程"],
        ),
        ToolDefinition(
            name="get_course_stats", description="课程统计数据",
            input_schema={"type": "object", "properties": {}},
            handler=get_course_stats, permission_mode=PermissionMode.READ_ONLY,
            category="课程管理", tags=["统计", "课程"],
        ),
    ]


# ═══════════════════════════════════════════
# 售课记录工具
# ═══════════════════════════════════════════

def register_sale_tools() -> List[ToolDefinition]:
    
    def list_sales(member_id: str = "", staff_id: str = "", date_from: str = "", date_to: str = "") -> ToolResult:
        """查询售课记录"""
        db = _get_db_session()
        try:
            query = db.query(Sale)
            if member_id:
                query = query.filter(Sale.member_id == member_id)
            if staff_id:
                query = query.filter(Sale.staff_id == staff_id)
            if date_from:
                query = query.filter(Sale.sale_date >= date_from)
            if date_to:
                query = query.filter(Sale.sale_date <= date_to)
            ss = query.order_by(Sale.id.desc()).limit(50).all()
            return ToolResult.ok(data=[_json_safe(s) for s in ss])
        finally:
            db.close()
    
    def create_sale(member_id: str, course_id: str, quantity: float = 1,
                    unit_price: float = 0, total_amount: float = 0,
                    payment_method: str = "现金", staff_id: str = "") -> ToolResult:
        """创建售课记录"""
        db = _get_db_session()
        try:
            # 验证会员存在
            m = db.query(Member).filter(Member.member_id == member_id).first()
            if not m:
                return ToolResult.fail("会员未找到")
            
            sale = Sale(
                member_id=member_id, member_name=m.name,
                course_id=course_id, quantity=quantity,
                unit_price=unit_price, total_amount=total_amount or unit_price*quantity,
                sale_date=date.today().isoformat(),
                payment_method=payment_method, staff_id=staff_id,
                status="已售",
            )
            db.add(sale)
            db.commit()
            return ToolResult.ok(data=_json_safe(sale))
        except Exception as e:
            db.rollback()
            return ToolResult.fail(f"创建售课记录失败: {e}")
        finally:
            db.close()
    
    def get_sale_summary(date_from: str = "", date_to: str = "") -> ToolResult:
        """售课汇总统计"""
        db = _get_db_session()
        try:
            from sqlalchemy import func
            query = db.query(
                func.sum(Sale.total_amount),
                func.count(Sale.id),
            )
            if date_from:
                query = query.filter(Sale.sale_date >= date_from)
            if date_to:
                query = query.filter(Sale.sale_date <= date_to)
            total_amount, total_count = query.first()
            return ToolResult.ok(data={
                "total_sales": int(total_count or 0),
                "total_amount": float(total_amount or 0),
            })
        finally:
            db.close()
    
    return [
        ToolDefinition(name="list_sales", description="查询售课记录",
            input_schema={"type": "object", "properties": {
                "member_id": {"type": "string"}, "staff_id": {"type": "string"},
                "date_from": {"type": "string"}, "date_to": {"type": "string"},
            }},
            handler=list_sales, permission_mode=PermissionMode.READ_ONLY,
            category="售课管理", tags=["售课"]),
        ToolDefinition(name="create_sale", description="创建售课记录",
            input_schema={"type": "object", "required": ["member_id", "course_id"],
                "properties": {
                    "member_id": {"type": "string"}, "course_id": {"type": "string"},
                    "quantity": {"type": "number"}, "unit_price": {"type": "number"},
                    "total_amount": {"type": "number"},
                    "payment_method": {"type": "string"},
                    "staff_id": {"type": "string"},
                }},
            handler=create_sale, permission_mode=PermissionMode.WORKSPACE_WRITE,
            category="售课管理", tags=["创建", "售课"]),
        ToolDefinition(name="get_sale_summary", description="售课汇总统计",
            input_schema={"type": "object", "properties": {
                "date_from": {"type": "string"}, "date_to": {"type": "string"},
            }},
            handler=get_sale_summary, permission_mode=PermissionMode.READ_ONLY,
            category="售课管理", tags=["统计", "售课"]),
    ]


# ═══════════════════════════════════════════
# 进场核销工具
# ═══════════════════════════════════════════

def register_checkin_tools() -> List[ToolDefinition]:
    
    def checkin_member(member_id: str, method: str = "手环", staff_id: str = "") -> ToolResult:
        """会员进场签到"""
        db = _get_db_session()
        try:
            m = db.query(Member).filter(Member.member_id == member_id).first()
            if not m:
                return ToolResult.fail("会员未找到")
            
            checkin = Checkin(
                member_id=member_id, member_name=m.name,
                checkin_date=date.today().isoformat(),
                checkin_time=datetime.now().strftime("%H:%M:%S"),
                method=method, staff_id=staff_id,
            )
            db.add(checkin)
            db.commit()
            return ToolResult.ok(data=_json_safe(checkin))
        except Exception as e:
            db.rollback()
            return ToolResult.fail(f"进场签到失败: {e}")
        finally:
            db.close()
    
    def list_checkins(date_from: str = "", date_to: str = "", page: int = 1) -> ToolResult:
        """查询进场记录"""
        db = _get_db_session()
        try:
            query = db.query(Checkin)
            if date_from:
                query = query.filter(Checkin.checkin_date >= date_from)
            if date_to:
                query = query.filter(Checkin.checkin_date <= date_to)
            cs = query.order_by(Checkin.id.desc()).limit(50).all()
            return ToolResult.ok(data=[_json_safe(c) for c in cs])
        finally:
            db.close()
    
    def get_checkin_stats(date_from: str = "", date_to: str = "") -> ToolResult:
        """进场统计"""
        db = _get_db_session()
        try:
            from sqlalchemy import func
            query = db.query(
                func.count(Checkin.id),
                func.count(func.distinct(Checkin.member_id)),
            )
            if date_from:
                query = query.filter(Checkin.checkin_date >= date_from)
            if date_to:
                query = query.filter(Checkin.checkin_date <= date_to)
            total, unique = query.first()
            return ToolResult.ok(data={
                "total_checkins": int(total or 0),
                "unique_members": int(unique or 0),
            })
        finally:
            db.close()
    
    return [
        ToolDefinition(name="checkin_member", description="会员进场签到",
            input_schema={"type": "object", "required": ["member_id"],
                "properties": {
                    "member_id": {"type": "string"},
                    "method": {"type": "string", "enum": ["手环", "扫码", "手动"]},
                    "staff_id": {"type": "string"},
                }},
            handler=checkin_member, permission_mode=PermissionMode.WORKSPACE_WRITE,
            category="进场核销", tags=["签到"]),
        ToolDefinition(name="list_checkins", description="查询进场记录",
            input_schema={"type": "object", "properties": {
                "date_from": {"type": "string"}, "date_to": {"type": "string"},
                "page": {"type": "integer"},
            }},
            handler=list_checkins, permission_mode=PermissionMode.READ_ONLY,
            category="进场核销", tags=["查询", "进场"]),
        ToolDefinition(name="get_checkin_stats", description="进场统计",
            input_schema={"type": "object", "properties": {
                "date_from": {"type": "string"}, "date_to": {"type": "string"},
            }},
            handler=get_checkin_stats, permission_mode=PermissionMode.READ_ONLY,
            category="进场核销", tags=["统计", "进场"]),
    ]


# ═══════════════════════════════════════════
# 财务管理工具
# ═══════════════════════════════════════════

def register_finance_tools() -> List[ToolDefinition]:
    
    def get_finance_summary(year: int = 0, month: int = 0) -> ToolResult:
        """财务汇总"""
        db = _get_db_session()
        try:
            from sqlalchemy import func
            today = date.today()
            y = year or today.year
            m = month or today.month
            
            income = db.query(func.coalesce(func.sum(FinanceIncome.amount), 0)).filter(
                func.strftime("%Y", FinanceIncome.income_date) == str(y),
                func.strftime("%m", FinanceIncome.income_date) == f"{m:02d}",
            ).scalar()
            
            expense = db.query(func.coalesce(func.sum(FinanceExpense.amount), 0)).filter(
                func.strftime("%Y", FinanceExpense.expense_date) == str(y),
                func.strftime("%m", FinanceExpense.expense_date) == f"{m:02d}",
            ).scalar()
            
            return ToolResult.ok(data={
                "year": y, "month": m,
                "total_income": float(income or 0),
                "total_expense": float(expense or 0),
                "net_profit": float((income or 0) - (expense or 0)),
            })
        finally:
            db.close()
    
    return [
        ToolDefinition(name="get_finance_summary", description="财务汇总",
            input_schema={"type": "object", "properties": {
                "year": {"type": "integer"}, "month": {"type": "integer"},
            }},
            handler=get_finance_summary, permission_mode=PermissionMode.READ_ONLY,
            category="财务管理", tags=["财务", "统计"]),
    ]


# ═══════════════════════════════════════════
# 仪表盘工具
# ═══════════════════════════════════════════

def register_dashboard_tools() -> List[ToolDefinition]:
    
    def get_dashboard_stats() -> ToolResult:
        """获取首页仪表盘统计数据"""
        db = _get_db_session()
        try:
            from sqlalchemy import func
            today = date.today().isoformat()
            
            total_members = db.query(Member).count()
            active_members = db.query(Member).filter(Member.status == "正常").count()
            total_staff = db.query(Staff).count()
            total_courses = db.query(Course).count()
            today_checkins = db.query(Checkin).filter(Checkin.checkin_date == today).count()
            today_sales = db.query(Sale).filter(Sale.sale_date == today).count()
            
            # 今日销售额
            today_amt = db.query(func.coalesce(func.sum(Sale.actual_amount), 0)).filter(
                Sale.sale_date == today
            ).scalar()
            
            return ToolResult.ok(data={
                "total_members": total_members,
                "active_members": active_members,
                "total_staff": total_staff,
                "total_courses": total_courses,
                "today_checkins": today_checkins,
                "today_sales": today_sales,
                "today_sale_amount": float(today_amt or 0),
            })
        finally:
            db.close()
    
    return [
        ToolDefinition(name="get_dashboard_stats", description="首页仪表盘统计数据",
            input_schema={"type": "object", "properties": {}},
            handler=get_dashboard_stats, permission_mode=PermissionMode.READ_ONLY,
            category="仪表盘", tags=["统计", "首页"]),
    ]


# ═══════════════════════════════════════════
# 手环管理工具
# ═══════════════════════════════════════════

def register_wristband_tools() -> List[ToolDefinition]:
    
    def find_member_by_wristband(reader_value: str) -> ToolResult:
        """通过手环读卡器值查找会员"""
        db = _get_db_session()
        try:
            w = db.query(Wristband).filter(Wristband.reader_value == reader_value).first()
            if not w:
                return ToolResult.fail("未找到该手环")
            if not w.member_id:
                return ToolResult.fail("该手环未绑定会员")
            m = db.query(Member).filter(Member.member_id == w.member_id).first()
            if not m:
                return ToolResult.fail("绑定的会员不存在")
            return ToolResult.ok(data={
                "member_id": m.member_id, "name": m.name,
                "phone": m.phone, "member_type": m.member_type,
            })
        finally:
            db.close()
    
    return [
        ToolDefinition(name="find_member_by_wristband", description="通过手环读卡器值查找会员",
            input_schema={"type": "object", "required": ["reader_value"],
                "properties": {
                    "reader_value": {"type": "string", "description": "手环读卡器值 (10位数字)"},
                }},
            handler=find_member_by_wristband, permission_mode=PermissionMode.READ_ONLY,
            category="手环管理", tags=["手环", "刷卡"]),
    ]


# ═══════════════════════════════════════════
# 通用工具
# ═══════════════════════════════════════════

def register_common_tools() -> List[ToolDefinition]:
    
    def get_system_info() -> ToolResult:
        """获取系统基本信息"""
        return ToolResult.ok(data={
            "name": "鼠小弟健身管理系统",
            "version": "3.7.0",
            "description": "健身房综合管理系统 — 会员/员工/课程/售课/进场/财务",
            "database": "SQLite",
            "framework": "FastAPI + HTMX + TailwindCSS",
        })
    
    def search(query: str, scope: str = "all", limit: int = 5) -> ToolResult:
        """全局搜索：搜索会员/员工/课程"""
        db = _get_db_session()
        try:
            results = {}
            q = f"%{query}%"
            
            if scope in ("all", "member"):
                ms = db.query(Member).filter(
                    Member.name.like(q) | Member.phone.like(q) | Member.member_id.like(q)
                ).limit(limit).all()
                results["members"] = [{"id": m.member_id, "name": m.name, "phone": m.phone} for m in ms]
            
            if scope in ("all", "staff"):
                ss = db.query(Staff).filter(
                    Staff.name.like(q) | Staff.staff_id.like(q)
                ).limit(limit).all()
                results["staff"] = [{"id": s.staff_id, "name": s.name, "position": s.position} for s in ss]
            
            if scope in ("all", "course"):
                cs = db.query(Course).filter(
                    Course.name.like(q) | Course.course_id.like(q)
                ).limit(limit).all()
                results["courses"] = [{"id": c.course_id, "name": c.name, "type": c.course_type} for c in cs]
            
            return ToolResult.ok(data=results)
        finally:
            db.close()
    
    return [
        ToolDefinition(
            name="get_system_info", description="获取系统基本信息",
            input_schema={"type": "object", "properties": {}},
            handler=get_system_info, permission_mode=PermissionMode.READ_ONLY,
            category="系统", tags=["系统信息"],
        ),
        ToolDefinition(
            name="search", description="全局搜索会员/员工/课程",
            input_schema={"type": "object", "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "scope": {"type": "string", "enum": ["all", "member", "staff", "course"], "default": "all"},
                    "limit": {"type": "integer", "default": 5},
                }},
            handler=search, permission_mode=PermissionMode.READ_ONLY,
            category="系统", tags=["搜索"],
        ),
    ]


# ═══════════════════════════════════════════
# 注册所有业务工具
# ═══════════════════════════════════════════

def register_all_business_tools(executor) -> None:
    """将所有业务工具注册到指定的 ToolExecutor 实例"""
    all_tools = []
    all_tools.extend(register_member_tools())
    all_tools.extend(register_staff_tools())
    all_tools.extend(register_course_tools())
    all_tools.extend(register_sale_tools())
    all_tools.extend(register_checkin_tools())
    all_tools.extend(register_finance_tools())
    all_tools.extend(register_dashboard_tools())
    all_tools.extend(register_wristband_tools())
    all_tools.extend(register_common_tools())
    
    executor.register_tools(all_tools)
    return all_tools
