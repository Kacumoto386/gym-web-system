"""小程序 JWT 验证依赖

与后台共用签名密钥，Payload 增加 type 字段区分身份：
  - type: "staff"   → 员工小程序
  - type: "member"  → 会员小程序
"""

from fastapi import Request, HTTPException
from jose import JWTError, jwt

from backend.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM


async def verify_miniapp_token(request: Request, require_type: str = None) -> dict:
    """验证小程序 Bearer JWT。

    Args:
        request: FastAPI 请求对象
        require_type: 要求的身类型（"staff" / "member"），None 表示不限制

    Returns:
        JWT payload 字典，包含 sub（用户ID）和 type（身份类型）

    Raises:
        HTTPException 401/403
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "未提供认证令牌")
    try:
        payload = jwt.decode(auth[7:], SECRET_KEY, algorithms=[ALGORITHM])
        if require_type and payload.get("type") != require_type:
            raise HTTPException(403, "身份类型不匹配")
        return payload
    except JWTError:
        raise HTTPException(401, "令牌无效或已过期")


async def verify_staff_token(request: Request) -> dict:
    return await verify_miniapp_token(request, require_type="staff")


async def verify_member_token(request: Request) -> dict:
    return await verify_miniapp_token(request, require_type="member")
