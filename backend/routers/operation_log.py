# -*- coding: utf-8 -*-
"""
操作日志模块 — 记录所有写操作（增删改）
V3.2.9 — 新增系统名称自定义
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Text, func
from backend.database import Base, engine, get_db

# ══════════════════════════════════════
# ORM 模型
# ══════════════════════════════════════

class OperationLog(Base):
    """操作日志（全局写操作记录）"""
    __tablename__ = "operation_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), default="", comment="操作人")
    action = Column(String(20), nullable=False, comment="操作类型: create/update/delete")
    resource = Column(String(50), nullable=False, comment="资源名")
    resource_id = Column(String(50), default="", comment="资源ID")
    detail = Column(Text, default="", comment="详情")
    ip_address = Column(String(50), default="", comment="IP")
    created_at = Column(DateTime, default=datetime.now, comment="操作时间")

OperationLog.__table__.create(bind=engine, checkfirst=True)


class SystemSetting(Base):
    """系统设置（KV 存储）"""
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, nullable=False, comment="设置键")
    value = Column(Text, default="", comment="设置值")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

SystemSetting.__table__.create(bind=engine, checkfirst=True)


# ══════════════════════════════════════
# 工具函数
# ══════════════════════════════════════

def record_log(db: Session, username: str, action: str, resource: str,
               resource_id: str = "", detail: str = "", ip: str = ""):
    """记录一条操作日志"""
    log = OperationLog(
        username=username or "",
        action=action,
        resource=resource,
        resource_id=resource_id or "",
        detail=(detail or "")[:500],
        ip_address=ip or "",
        created_at=datetime.now(),
    )
    db.add(log)
    db.commit()


def get_operator(request: Request, db: Session) -> str:
    """从请求中获取操作人用户名"""
    token = request.cookies.get("access_token", "")
    if token:
        from jose import jwt
        try:
            from backend.routers.auth import SECRET_KEY, ALGORITHM
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload.get("sub", "系统")
        except Exception:
            pass
    return "系统"


def get_system_name(db: Session) -> str:
    """获取系统名称，不存在则返回默认值"""
    setting = db.query(SystemSetting).filter(SystemSetting.key == "system_name").first()
    if setting and setting.value:
        return setting.value
    return "健身房管理系统"


def set_system_name(db: Session, name: str):
    """设置系统名称（upsert）"""
    setting = db.query(SystemSetting).filter(SystemSetting.key == "system_name").first()
    if setting:
        setting.value = name
        setting.updated_at = datetime.now()
    else:
        setting = SystemSetting(key="system_name", value=name, updated_at=datetime.now())
        db.add(setting)
    db.commit()


# ══════════════════════════════════════
# 系统设置路由（挂载到 /api/system）
# ══════════════════════════════════════

system_router = APIRouter(prefix="/api/system", tags=["系统设置"])


class SystemNameUpdate(BaseModel):
    name: str


@system_router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    """获取所有系统设置"""
    settings = db.query(SystemSetting).all()
    result = {s.key: s.value for s in settings}
    # 确保 system_name 总有默认值
    if "system_name" not in result:
        result["system_name"] = "健身房管理系统"
    return result


@system_router.put("/settings")
def update_setting(data: SystemNameUpdate, request: Request, db: Session = Depends(get_db)):
    """更新系统设置"""
    name = data.name.strip()
    if not name:
        return JSONResponse(status_code=400, content={"detail": "系统名称不能为空"})
    if len(name) > 50:
        return JSONResponse(status_code=400, content={"detail": "系统名称不能超过50个字符"})

    operator = get_operator(request, db)
    old_name = get_system_name(db)
    set_system_name(db, name)
    record_log(db, operator, "update", "系统设置", "",
               f"修改系统名称: 「{old_name}」→「{name}」",
               ip=request.client.host if request.client else "")
    return {"success": True, "system_name": name}


# ══════════════════════════════════════
# 操作日志路由
# ══════════════════════════════════════

router = APIRouter(prefix="/api/logs", tags=["操作日志"])


@router.get("/table", response_class=HTMLResponse)
def log_table(
    action: str = "",
    resource: str = "",
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(OperationLog)
    if action:
        query = query.filter(OperationLog.action == action)
    if resource:
        query = query.filter(OperationLog.resource == resource)
    rows = query.order_by(OperationLog.id.desc()).offset(skip).limit(limit).all()

    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无操作日志</div>'

    trs = ""
    for log in rows:
        colors = {
            "create": "bg-green-100 text-green-700",
            "update": "bg-blue-100 text-blue-700",
            "delete": "bg-red-100 text-red-700",
        }
        cls = colors.get(log.action, "bg-gray-100 text-gray-700")
        trs += f"""<tr class="hover:bg-gray-50 border-b text-sm">
            <td class="px-3 py-2 text-gray-400">{log.created_at.strftime('%m-%d %H:%M') if log.created_at else ''}</td>
            <td class="px-3 py-2">{log.username}</td>
            <td class="px-3 py-2"><span class="px-2 py-0.5 rounded text-xs {cls}">{log.action}</span></td>
            <td class="px-3 py-2 text-gray-600">{log.resource}</td>
            <td class="px-3 py-2 text-gray-500">{log.resource_id}</td>
            <td class="px-3 py-2 text-gray-400 max-w-xs truncate">{log.detail}</td>
        </tr>"""

    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-3 py-2">时间</th><th class="px-3 py-2">操作人</th><th class="px-3 py-2">操作</th><th class="px-3 py-2">资源</th><th class="px-3 py-2">ID</th><th class="px-3 py-2">详情</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("")
def list_logs(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    rows = db.query(OperationLog).order_by(OperationLog.id.desc()).offset(skip).limit(limit).all()
    return [
        {
            "id": r.id,
            "username": r.username,
            "action": r.action,
            "resource": r.resource,
            "resource_id": r.resource_id,
            "detail": r.detail,
            "time": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


@router.get("/stats")
def log_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(OperationLog.id)).scalar()
    return {"total_logs": total}
