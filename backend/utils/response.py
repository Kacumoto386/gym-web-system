# -*- coding: utf-8 -*-
"""
统一 API 响应格式
V3.9.0
"""
from typing import Any, Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    success: bool = True
    data: Any = None
    message: str = "ok"


def success(data: Any = None, message: str = "ok") -> ApiResponse:
    return ApiResponse(success=True, data=data, message=message)


def fail(message: str = "请求失败", data: Any = None) -> ApiResponse:
    return ApiResponse(success=False, data=data, message=message)
