# -*- coding: utf-8 -*-
"""
认证模块 - 用户管理 + JWT 登录
V3.0.1
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func as sql_func
from jose import JWTError, jwt
import bcrypt
from backend.database import Base, engine, get_db
from backend.routers.operation_log import record_log

# ── 配置 ──
SECRET_KEY = "gym-web-system-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


# ── 密码工具（不用 passlib，避免 bcrypt 5.x 兼容性问题）──

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


# ── ORM 模型 ──

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(200), nullable=False)
    display_name = Column(String(100), default="管理员")
    role = Column(String(20), default="admin")
    created_at = Column(DateTime, server_default=sql_func.now())


# 创建表
User.__table__.create(bind=engine, checkfirst=True)


# ── Pydantic Schemas ──

class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = "管理员"


# ── 工具函数 ──

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    return db.query(User).filter(User.username == username).first()


def require_user(user: Optional[User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


# ── 路由 ──

router = APIRouter(prefix="/auth", tags=["认证"])


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """登录页面"""
    user = get_current_user(request, next(get_db()))
    if user:
        return RedirectResponse(url="/", status_code=302)
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>登录 - 鼠小弟健身管理系统</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gradient-to-br from-blue-50 to-indigo-100 min-h-screen flex items-center justify-center">
        <div class="bg-white rounded-2xl shadow-xl p-8 w-full max-w-sm mx-4">
            <div class="text-center mb-6">
                <div class="text-4xl mb-2">💪</div>
                <h1 class="text-xl font-bold text-gray-800">鼠小弟健身管理系统</h1>
                <p class="text-sm text-gray-400 mt-1">请登录继续</p>
            </div>
            <div id="errorMsg" class="hidden bg-red-50 text-red-600 text-sm p-3 rounded-lg mb-4"></div>
            <form id="loginForm" onsubmit="return doLogin(event)">
                <div class="mb-4">
                    <label class="block text-sm text-gray-600 mb-1">用户名</label>
                    <input id="username" name="username" type="text" required autocomplete="username"
                           class="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none">
                </div>
                <div class="mb-6">
                    <label class="block text-sm text-gray-600 mb-1">密码</label>
                    <input id="password" name="password" type="password" required autocomplete="current-password"
                           class="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none">
                </div>
                <button type="submit"
                        class="w-full bg-blue-600 text-white py-2.5 rounded-lg hover:bg-blue-700 font-medium transition">
                    登 录
                </button>
            </form>
        </div>
        <script>
        async function doLogin(e) {
            e.preventDefault();
            const el = document.getElementById('errorMsg');
            el.classList.add('hidden');
            const form = document.getElementById('loginForm');
            const data = new FormData(form);
            try {
                const res = await fetch('/auth/token', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: data.get('username'), password: data.get('password')})
                });
                if (!res.ok) {
                    const err = await res.json();
                    el.textContent = err.detail || '登录失败';
                    el.classList.remove('hidden');
                    return;
                }
                window.location.href = '/';
            } catch (err) {
                el.textContent = '网络错误，请重试';
                el.classList.remove('hidden');
            }
            return false;
        }
        </script>
    </body>
    </html>
    """, status_code=200)


@router.post("/token")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """登录获取 token"""
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token({"sub": user.username})
    response = JSONResponse({"access_token": token, "token_type": "bearer", "username": user.username})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=86400,
        path="/",
    )
    return response


@router.post("/setup")
def setup_admin(data: UserCreate, db: Session = Depends(get_db)):
    """初始化管理员账号（仅首次使用）"""
    existing = db.query(User).first()
    if existing:
        raise HTTPException(status_code=400, detail="管理员已存在，不能重复初始化")
    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        display_name=data.display_name or "管理员",
        role="admin",
    )
    db.add(user)
    db.commit()
    return {"success": True, "message": f"管理员 {data.username} 创建成功"}


@router.get("/me")
def get_me(user: User = Depends(require_user)):
    return {"username": user.username, "display_name": user.display_name, "role": user.role}
