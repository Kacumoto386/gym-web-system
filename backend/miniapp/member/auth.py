"""会员小程序 · 认证：微信 code + 手机号一键登录"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import time

from backend.database import get_db
from backend.models.models import Member
from backend.miniapp.common import success, MiniAppException
from backend.miniapp.auth import verify_member_token
from backend.core.config import settings
from backend.routers.auth import hash_password, verify_password
import random

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
from jose import jwt

router = APIRouter(prefix="/auth", tags=["会员认证"])


class LoginRequest(BaseModel):
    code: str  # wx.login() 获取的临时 code
    encrypted_data: Optional[str] = ""
    iv: Optional[str] = ""
    phone: Optional[str] = ""  # 备用：直接传手机号


class LoginResponse(BaseModel):
    token: str
    member_id: str
    member_name: str
    phone: str


# ── 验证码存储（开发阶段用内存，生产环境应替换为 Redis） ──
_sms_codes: dict[str, dict] = {}
CODE_EXPIRE_SECONDS = 300  # 5 分钟


class SendCodeRequest(BaseModel):
    phone: str


class LoginByPasswordRequest(BaseModel):
    phone: str
    password: str


class LoginByCodeRequest(BaseModel):
    phone: str
    code: str


class SetPasswordRequest(BaseModel):
    phone: str
    code: str
    password: str


@router.post("/login")
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    """微信 code + 手机号登录。

    流程：
    1. 通过 code 换取 openid（调用微信 code2Session 接口）
    2. 根据手机号匹配 Member 表
    3. 创建/更新 member_wechat_accounts 映射
    4. 颁发 JWT
    """
    # TODO: 接入微信 code2Session 接口获取 openid
    # openid = await wechat_code2session(body.code)
    openid = f"mock_openid_{body.code}"  # 预开发阶段 mock

    # 根据手机号查找会员
    member = None
    if body.phone:
        member = db.query(Member).filter(Member.phone == body.phone).first()

    if not member:
        raise MiniAppException(2002, "未找到匹配的会员，请确认手机号正确")

    token = jwt.encode(
        {
            "sub": member.member_id,
            "type": "member",
            "exp": datetime.utcnow() + timedelta(days=30),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return success(data={
        "token": token,
        "member_id": member.member_id,
        "member_name": member.name,
        "phone": member.phone,
    })


@router.post("/logout")
async def logout(payload: dict = Depends(verify_member_token)):
    """会员登出。"""
    return success(message="已登出")


@router.post("/send-code")
async def send_code(body: SendCodeRequest, db: Session = Depends(get_db)):
    """发送短信验证码。"""
    member = db.query(Member).filter(Member.phone == body.phone).first()
    if not member:
        raise MiniAppException(2002, "该手机号未注册")

    code = f"{random.randint(100000, 999999)}"
    _sms_codes[body.phone] = {"code": code, "expired_at": time.time() + CODE_EXPIRE_SECONDS}
    # 开发阶段直接返回 code 方便调试
    return success(data={"code": code}, message="验证码已发送")


@router.post("/login-by-password")
async def login_by_password(body: LoginByPasswordRequest, db: Session = Depends(get_db)):
    """密码登录。"""
    member = db.query(Member).filter(Member.phone == body.phone).first()
    if not member:
        raise MiniAppException(2002, "该手机号未注册")
    if not member.password_hash:
        raise MiniAppException(2001, "请先设置密码")
    if not verify_password(body.password, member.password_hash):
        raise MiniAppException(2001, "手机号或密码错误")

    token = jwt.encode(
        {
            "sub": member.member_id,
            "type": "member",
            "exp": datetime.utcnow() + timedelta(days=30),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return success(data={
        "token": token,
        "member_id": member.member_id,
        "member_name": member.name,
        "phone": member.phone,
    })


@router.post("/login-by-code")
async def login_by_code(body: LoginByCodeRequest, db: Session = Depends(get_db)):
    """验证码登录。"""
    member = db.query(Member).filter(Member.phone == body.phone).first()
    if not member:
        raise MiniAppException(2002, "该手机号未注册")

    stored = _sms_codes.get(body.phone)
    if not stored or stored["code"] != body.code:
        raise MiniAppException(2001, "验证码错误")
    if time.time() > stored["expired_at"]:
        del _sms_codes[body.phone]
        raise MiniAppException(2001, "验证码已过期")

    del _sms_codes[body.phone]  # 使用后删除

    token = jwt.encode(
        {
            "sub": member.member_id,
            "type": "member",
            "exp": datetime.utcnow() + timedelta(days=30),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return success(data={
        "token": token,
        "member_id": member.member_id,
        "member_name": member.name,
        "phone": member.phone,
    })


@router.post("/set-password")
async def set_password(body: SetPasswordRequest, db: Session = Depends(get_db)):
    """设置/重置密码（需验证码验证身份）。"""
    member = db.query(Member).filter(Member.phone == body.phone).first()
    if not member:
        raise MiniAppException(2002, "该手机号未注册")

    stored = _sms_codes.get(body.phone)
    if not stored or stored["code"] != body.code:
        raise MiniAppException(2001, "验证码错误")
    if time.time() > stored["expired_at"]:
        del _sms_codes[body.phone]
        raise MiniAppException(2001, "验证码已过期")

    if len(body.password) < 6:
        raise MiniAppException(2001, "密码长度不能少于6位")

    del _sms_codes[body.phone]
    member.password_hash = hash_password(body.password)
    db.commit()
    return success(message="密码设置成功")
