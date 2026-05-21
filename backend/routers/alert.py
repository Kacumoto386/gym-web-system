# -*- coding: utf-8 -*-
"""
到期提醒 API 路由 + HTMX HTML 片段端点
V3.0.0
"""
from typing import Optional, List
from fastapi import Request,  APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import datetime
from backend.database import get_db
from backend.models.models import Alert
from pydantic import BaseModel

router = APIRouter(prefix="/api/alerts", tags=["到期提醒"])


# ═══════════════════════════════════════════
# HTMX HTML 片段
# ═══════════════════════════════════════════

def _build_table(rows: list) -> str:
    if not rows:
        return '<div class="text-center py-8 text-gray-400">暂无提醒</div>'
    trs = ""
    for a in rows:
        cls = {"已处理": "bg-green-100 text-green-700", "未处理": "bg-red-100 text-red-700",
               "处理中": "bg-yellow-100 text-yellow-700"}.get(a.status, "bg-gray-100")
        handle_btn = ""
        if a.status != "已处理":
            handle_btn = f'<button class="text-green-600 hover:text-green-800 mr-2" hx-put="/api/alerts/{a.id}/process" hx-target="#alertTable" hx-confirm="标记为已处理？">处理</button>'
        trs += f"""<tr class="hover:bg-gray-50 border-b">
            <td class="px-4 py-3 text-sm text-gray-500">{a.id}</td>
            <td class="px-4 py-3 text-sm">{a.alert_type}</td>
            <td class="px-4 py-3">{a.member_name or ''}</td>
            <td class="px-4 py-3 text-sm">{a.member_id or ''}</td>
            <td class="px-4 py-3 text-sm">{a.expire_date or ''}</td>
            <td class="px-4 py-3 text-sm">{a.remaining_days or 0}天</td>
            <td class="px-4 py-3 text-sm"><span class="px-2 py-0.5 {cls} rounded text-xs">{a.status or '未处理'}</span></td>
            <td class="px-4 py-3 text-sm">{a.content[:40] + '...' if a.content and len(a.content) > 40 else (a.content or '')}</td>
            <td class="px-4 py-3 text-sm">
                {handle_btn}
                <button class="text-red-500 hover:text-red-700" hx-delete="/api/alerts/{a.id}" hx-target="#alertTable" hx-confirm="确认删除此提醒？">删除</button>
            </td>
        </tr>"""
    return f"""<table class="w-full bg-white rounded-lg shadow-sm">
        <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
            <tr><th class="px-4 py-3">ID</th><th class="px-4 py-3">类型</th><th class="px-4 py-3">会员</th><th class="px-4 py-3">会员编号</th><th class="px-4 py-3">到期日</th><th class="px-4 py-3">剩余天数</th><th class="px-4 py-3">状态</th><th class="px-4 py-3">内容</th><th class="px-4 py-3">操作</th></tr>
        </thead>
        <tbody>{trs}</tbody>
    </table>"""


@router.get("/table", response_class=HTMLResponse)
def alert_table(status: str = "", alert_type: str = "", db: Session = Depends(get_db)):
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status)
    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)
    return _build_table(query.order_by(Alert.remaining_days.asc()).limit(100).all())


# ═══════════════════════════════════════════
# Pydantic Schemas
# ═══════════════════════════════════════════

class AlertOut(BaseModel):
    id: int
    alert_type: str
    content: str
    member_id: str
    member_name: str
    expire_date: str
    remaining_days: int
    status: str

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════

@router.get("", response_model=List[AlertOut])
def list_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status)
    return query.order_by(Alert.remaining_days.asc()).offset(skip).limit(limit).all()


@router.put("/{alert_id}/process")
def process_alert(alert_id: int, db: Session = Depends(get_db)):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="提醒不存在")
    a.status = "已处理"
    a.process_time = datetime.now()
    db.commit()
    return {"success": True, "message": "已标记为处理"}


@router.delete("/{alert_id}")
def delete_alert(alert_id: int, request: Request, db: Session = Depends(get_db)):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="提醒不存在")
    db.delete(a)
    db.commit()

    return {"success": True, "message": f"提醒已删除"}
