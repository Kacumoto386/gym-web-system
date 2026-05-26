# -*- coding: utf-8 -*-
"""
业务异常体系
V3.9.0
"""
from fastapi import HTTPException


class AppException(HTTPException):
    """业务异常基类"""
    def __init__(self, status_code: int = 400, message: str = "请求失败"):
        super().__init__(status_code=status_code, detail=message)


class NotFoundError(AppException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(status_code=404, message=message)


class ValidationError(AppException):
    def __init__(self, message: str = "参数错误"):
        super().__init__(status_code=422, message=message)


class AuthError(AppException):
    def __init__(self, message: str = "未登录或权限不足"):
        super().__init__(status_code=401, message=message)


class BizError(AppException):
    """通用业务错误（如冲突、重复、不允许的操作）"""
    def __init__(self, message: str = "操作失败"):
        super().__init__(status_code=400, message=message)
