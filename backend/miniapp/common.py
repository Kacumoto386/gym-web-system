"""小程序公用工具：统一响应格式 + 异常处理 + 分页"""

from fastapi.responses import JSONResponse


def success(data=None, message="ok") -> dict:
    return {"code": 0, "data": data, "message": message}


def error(code: int, message: str, data=None) -> dict:
    return {"code": code, "data": data, "message": message}


class MiniAppException(Exception):
    """小程序业务异常，由全局异常处理器捕获并返回统一 JSON 格式。"""

    def __init__(self, code: int, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code


def mini_app_exception_handler(request, exc: MiniAppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "data": None, "message": exc.message},
    )


# 错误码定义
# 0     = 成功
# 1001  = 令牌无效
# 1002  = 令牌过期
# 2001  = 参数错误
# 2002  = 资源不存在
# 3001  = 业务逻辑错误（如余额不足）
# 5000  = 服务端内部错误
