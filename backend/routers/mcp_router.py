"""
MCP FastAPI 路由
===============
将 MCP Server 暴露为 FastAPI HTTP 端点，支持:
1. MCP 协议端点（/api/mcp/ 前缀）
2. 管理界面（查看工具列表/执行/状态）
3. AI agent 集成端点
"""

from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

from backend.database import get_db
from backend.mcp import get_executor as _get_executor
from backend.mcp import get_mcp_server as _get_mcp_server
from backend.mcp.executor import (
    ToolExecutor, McpServer, ToolDefinition, ToolResult,
    PermissionMode,
)


router = APIRouter(tags=["mcp"])

# 委托到 __init__.py 的全局单例
get_executor = _get_executor
get_mcp_server = _get_mcp_server


# ── Pydantic 模型 ──

class MCPCallToolRequest(BaseModel):
    """MCP tools/call 请求"""
    name: str
    arguments: dict = {}


class MCPBatchRequest(BaseModel):
    """批量工具执行请求"""
    calls: list[MCPCallToolRequest]


class MCPReadResourceRequest(BaseModel):
    """MCP resources/read 请求"""
    uri: str


# ═══════════════════════════════════════════
# MCP 协议端点
# ═══════════════════════════════════════════

@router.get("/api/mcp/tools")
async def mcp_list_tools():
    """MCP tools/list — 列出所有可用工具"""
    mcp = get_mcp_server()
    return JSONResponse(mcp.handle_list_tools())


@router.post("/api/mcp/call-tool")
async def mcp_call_tool(req: MCPCallToolRequest):
    """MCP tools/call — 调用指定工具"""
    mcp = get_mcp_server()
    return JSONResponse(mcp.handle_call_tool(req.name, req.arguments))


@router.get("/api/mcp/resources")
async def mcp_list_resources():
    """MCP resources/list — 列出可用资源"""
    mcp = get_mcp_server()
    return JSONResponse(mcp.handle_list_resources())


@router.post("/api/mcp/read-resource")
async def mcp_read_resource(req: MCPReadResourceRequest):
    """MCP resources/read — 读取指定资源"""
    mcp = get_mcp_server()
    return JSONResponse(mcp.handle_read_resource(req.uri))


@router.get("/api/mcp/ping")
async def mcp_ping():
    """MCP ping — 健康检查"""
    mcp = get_mcp_server()
    return JSONResponse(mcp.handle_ping())


# ═══════════════════════════════════════════
# 扩展端点（非标准 MCP 协议）
# ═══════════════════════════════════════════

@router.post("/api/mcp/batch-execute")
async def mcp_batch_execute(req: MCPBatchRequest):
    """批量执行多个工具调用"""
    mcp = get_mcp_server()
    calls = [{"name": c.name, "arguments": c.arguments} for c in req.calls]
    results = mcp.handle_batch_execute(calls)
    return JSONResponse({"results": results})


@router.get("/api/mcp/server-info")
async def mcp_server_info():
    """MCP 服务器信息"""
    mcp = get_mcp_server()
    return JSONResponse(mcp.get_server_info())


@router.get("/api/mcp/parity-report")
async def mcp_parity_report():
    """MCP 兼容性报告"""
    mcp = get_mcp_server()
    return JSONResponse(mcp.get_parity_report())


@router.post("/api/mcp/set-permission")
async def mcp_set_permission(mode: str):
    """设置当前权限级别"""
    executor = get_executor()
    try:
        pm = PermissionMode(mode)
        executor.set_permission(pm)
        return JSONResponse({"success": True, "mode": mode})
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"无效的权限模式: {mode}，可选: {[m.value for m in PermissionMode]}"
        )


@router.get("/api/mcp/search-tools")
async def mcp_search_tools(q: str = ""):
    """搜索工具"""
    executor = get_executor()
    if q:
        tools = executor.search_tools(q)
    else:
        tools = executor.list_tools()
    return JSONResponse({
        "total": len(tools),
        "tools": [
            {"name": t.name, "description": t.description,
             "category": t.category, "permission": t.permission_mode.value}
            for t in tools
        ],
    })


# ═══════════════════════════════════════════
# 管理界面页面
# ═══════════════════════════════════════════

@router.get("/mcp-tools", response_class=HTMLResponse)
async def mcp_tools_page(request: Request):
    """MCP工具管理页面"""
    from fastapi.templating import Jinja2Templates
    from pathlib import Path
    templates_dir = Path(__file__).parent.parent.parent / "frontend" / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))
    
    executor = get_executor()
    mcp = get_mcp_server()
    tools = executor.list_tools()
    info = mcp.get_server_info()
    
    return templates.TemplateResponse(
        request=request,
        name="mcp_tools.html",
        context={
            "title": "MCP 工具管理",
            "tool_count": len(tools),
            "server_info": info,
            "tools_by_category": {
                cat: [t for t in tools if t.category == cat]
                for cat in sorted(set(t.category for t in tools))
            },
        },
    )
