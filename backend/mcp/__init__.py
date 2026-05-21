"""
MCP + ToolExecutor 架构
=======================
从 Claw Code 移植的核心架构组件。

架构层次:
1. ToolDefinition — 工具定义（名称/描述/输入 schema/所需权限）
2. ToolExecutor — 工具执行引擎（注册/查找/执行/权限检查）
3. McpServer — MCP 协议服务端（通过 HTTP FastAPI 路由暴露）
4. ConversationRuntime — LLM ↔ 工具 对话循环引擎
5. Session — 多会话管理（待移植）

组件关系:
    ConversationRuntime
        ↳ ToolExecutor.execute() — 调用业务工具
        ↳ McpServer.handle_call_tool() — 也可走 MCP 协议
    ToolExecutor
        ↳ ToolDefinition（注册的业务工具）
        ↳ PermissionMode（三级权限检查）
        ↳ Pre/Post Hooks（钩子系统）
"""

from backend.mcp.executor import (
    ToolExecutor,
    ToolDefinition,
    ToolResult,
    McpServer,
    PermissionMode,
    permission_ge,
)

from backend.mcp.business_tools import register_all_business_tools

# 全局单例
_executor: ToolExecutor = None


def get_executor() -> ToolExecutor:
    """获取全局 ToolExecutor 实例（懒初始化）"""
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
        register_all_business_tools(_executor)
    return _executor


def get_mcp_server() -> McpServer:
    """获取全局 McpServer 实例"""
    return McpServer(get_executor())
