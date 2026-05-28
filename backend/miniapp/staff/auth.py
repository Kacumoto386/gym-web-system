"""员工小程序 · 认证：账号密码登录（复用系统 User 表）"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta

from backend.database import get_db
from backend.models.models import Staff
from backend.miniapp.common import success, error, MiniAppException
from backend.miniapp.auth import verify_staff_token
from backend.core.config import settings
from backend.routers.auth import User, verify_password

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
from jose import jwt

router = APIRouter(prefix="/auth", tags=["员工认证"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    staff_id: str
    staff_name: str
    role: str


@router.post("/login")
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    # 1. 复用系统 User 表验证账号密码
    user = db.query(User).filter(User.username == body.username).first()
    if not user:
        raise MiniAppException(2002, "用户不存在")
    if not verify_password(body.password, user.hashed_password):
        raise MiniAppException(2001, "密码错误")

    # 2. 查找对应的员工档案
    staff = db.query(Staff).filter(Staff.staff_id == user.username).first()
    staff_id = staff.staff_id if staff else user.username
    staff_name = staff.name if staff else user.display_name
    staff_role = staff.position if staff else user.role

    token = jwt.encode(
        {
            "sub": staff_id,
            "type": "staff",
            "exp": datetime.utcnow() + timedelta(days=30),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return success(data={
        "token": token,
        "staff_id": staff_id,
        "staff_name": staff_name,
        "role": staff_role or "",
    })


@router.post("/logout")
async def logout(payload: dict = Depends(verify_staff_token)):
    """员工登出（客户端清除 token，服务端无状态）。"""
    return success(message="已登出")
