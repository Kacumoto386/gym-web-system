"""
ToolExecutor 引擎
================
从 Claw Code 移植的核心工具执行引擎。

功能:
- 工具注册（内置工具 + 动态注册）
- 工具查找（名称精确匹配 + 前缀匹配 MCP）
- 权限检查（PermissionMode 三层模型）
- 工具执行（同步/异步）
- 工具定义（名称/描述/输入 schema/权限）

使用方式:
    executor = ToolExecutor()
    executor.register_tool(ToolDefinition(
        name="get_member",
        description="查询会员信息",
        input_schema={...},
        handler=my_handler,
        permission_mode=PermissionMode.READ_ONLY,
    ))
    result = executor.execute("get_member", {"member_id": "M001"})
"""

from __future__ import annotations
import json
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime


# ═══════════════════════════════════════════
# 权限模型
# ═══════════════════════════════════════════

class PermissionMode(str, Enum):
    """权限级别，从低到高"""
    READ_ONLY = "read_only"           # 只读操作：查询、统计
    WORKSPACE_WRITE = "workspace_write"  # 写入操作：增删改
    DANGER_FULL_ACCESS = "danger_full_access"  # 危险操作：删除/重置/批量


PERMISSION_ORDER = {
    PermissionMode.READ_ONLY: 1,
    PermissionMode.WORKSPACE_WRITE: 2,
    PermissionMode.DANGER_FULL_ACCESS: 3,
}


def permission_ge(required: PermissionMode, current: PermissionMode) -> bool:
    """检查当前权限是否满足所需的权限级别"""
    return PERMISSION_ORDER.get(current, 0) >= PERMISSION_ORDER.get(required, 0)


# ═══════════════════════════════════════════
# 工具定义
# ═══════════════════════════════════════════

@dataclass
class ToolDefinition:
    """工具定义规范 — 对应 Claw Code 的 ToolSpec"""
    name: str                              # 工具名称（全局唯一）
    description: str                       # 工具描述（供 LLM 理解用途）
    input_schema: Dict[str, Any]           # JSON Schema 输入格式
    handler: Callable                      # 执行函数
    permission_mode: PermissionMode = PermissionMode.READ_ONLY  # 所需最低权限
    category: str = "通用"                  # 工具分类
    tags: List[str] = field(default_factory=list)  # 标签
    examples: List[Dict[str, Any]] = field(default_factory=list)  # 示例

    def to_mcp_tool(self) -> Dict[str, Any]:
        """转换为 MCP 兼容的工具定义格式"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class ToolResult:
    """工具执行结果 — 对应 Claw Code 的 ToolResultContentBlock"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0

    def to_json(self) -> str:
        return json.dumps({
            "success": self.success,
            "data": self.data,
            "error": self.error,
        }, ensure_ascii=False, default=str)

    @classmethod
    def ok(cls, data: Any = None) -> "ToolResult":
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        return cls(success=False, error=error)


# ═══════════════════════════════════════════
# 工具执行引擎
# ═══════════════════════════════════════════

class ToolExecutor:
    """
    工具执行引擎 — 对应 Claw Code 的 GlobalToolRegistry + ToolExecutor trait
    
    功能:
    - 内置工具注册
    - 动态工具注册
    - 工具执行（带权限检查）
    - 工具发现（列表/搜索）
    """
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._current_permission: PermissionMode = PermissionMode.READ_ONLY
        self._hook_pre: List[Callable] = []    # Pre-hooks（对应 Claw Code HookRunner）
        self._hook_post: List[Callable] = []   # Post-hooks
    
    # ── 工具注册 ──
    
    def register_tool(self, tool: ToolDefinition) -> None:
        """注册一个工具"""
        if tool.name in self._tools:
            raise ValueError(f"工具 '{tool.name}' 已注册")
        self._tools[tool.name] = tool
    
    def register_tools(self, tools: List[ToolDefinition]) -> None:
        """批量注册工具"""
        for tool in tools:
            self.register_tool(tool)
    
    def unregister_tool(self, name: str) -> None:
        """注销一个工具"""
        self._tools.pop(name, None)
    
    # ── 权限设置 ──
    
    def set_permission(self, mode: PermissionMode) -> None:
        """设置当前会话的权限级别"""
        self._current_permission = mode
    
    def get_permission(self) -> PermissionMode:
        return self._current_permission
    
    # ── Hook 系统（对应 Claw Code 的 hook system） ──
    
    def add_pre_hook(self, hook: Callable) -> None:
        """添加前置钩子：工具执行前调用，返回 False 可阻止执行"""
        self._hook_pre.append(hook)
    
    def add_post_hook(self, hook: Callable) -> None:
        """添加后置钩子：工具执行后调用"""
        self._hook_post.append(hook)
    
    def _run_pre_hooks(self, tool_name: str, params: Dict) -> Optional[str]:
        """运行所有前置钩子，返回拒绝原因或 None"""
        for hook in self._hook_pre:
            result = hook(tool_name, params)
            if result is not None:
                return result
        return None
    
    def _run_post_hooks(self, tool_name: str, params: Dict, result: ToolResult) -> None:
        """运行所有后置钩子"""
        for hook in self._hook_post:
            hook(tool_name, params, result)
    
    # ── 工具发现 ──
    
    def list_tools(self, category: Optional[str] = None) -> List[ToolDefinition]:
        """列出所有工具，可选按分类过滤"""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return sorted(tools, key=lambda t: t.name)
    
    def search_tools(self, query: str) -> List[ToolDefinition]:
        """搜索工具（名称+描述模糊匹配）"""
        query = query.lower()
        return [
            t for t in self._tools.values()
            if query in t.name.lower() or query in t.description.lower()
        ]
    
    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """获取指定工具的定义"""
        return self._tools.get(name)
    
    def get_mcp_tool_list(self) -> List[Dict[str, Any]]:
        """获取 MCP 兼容的工具列表（供 LLM 使用）"""
        return [
            t.to_mcp_tool()
            for t in sorted(self._tools.values(), key=lambda t: t.name)
            if permission_ge(t.permission_mode, self._current_permission)
        ]
    
    # ── 工具执行 ──
    
    def execute(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        """
        执行工具
        
        Args:
            tool_name: 工具名称
            params: 参数字典
            
        Returns:
            ToolResult 执行结果
            
        Raises:
            KeyError: 工具未找到
            PermissionError: 权限不足
        """
        import time
        
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult.fail(f"工具 '{tool_name}' 未注册")
        
        # 权限检查（对应 Claw Code 的 PermissionPolicy.authorize）
        if not permission_ge(tool.permission_mode, self._current_permission):
            return ToolResult.fail(
                f"权限不足：工具 '{tool_name}' 需要 {tool.permission_mode.value}，"
                f"当前权限 {self._current_permission.value}"
            )
        
        # Pre-hooks
        deny_reason = self._run_pre_hooks(tool_name, params)
        if deny_reason:
            return ToolResult.fail(f"前置钩子拒绝执行: {deny_reason}")
        
        # 执行
        start = time.time()
        try:
            result = tool.handler(**params)
            elapsed = (time.time() - start) * 1000
            
            if isinstance(result, ToolResult):
                result.execution_time_ms = elapsed
                # Post-hooks
                self._run_post_hooks(tool_name, params, result)
                return result
            
            tool_result = ToolResult.ok(data=result)
            tool_result.execution_time_ms = elapsed
            # Post-hooks
            self._run_post_hooks(tool_name, params, tool_result)
            return tool_result
            
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            error_result = ToolResult.fail(str(e))
            error_result.execution_time_ms = elapsed
            self._run_post_hooks(tool_name, params, error_result)
            return error_result


# ═══════════════════════════════════════════
# MCP Server 实现
# ═══════════════════════════════════════════

class McpServer:
    """
    MCP Server — 将 ToolExecutor 暴露为 MCP 协议端点
    
    对应 Claw Code 的:
    - mcp_server.rs — MCP 服务器端
    - mcp_client.rs — MCP 客户端
    - mcp_tool_bridge.rs — 工具桥接
    
    支持两种模式:
    1. Stdio — 子进程通信（适用于本地集成）
    2. HTTP — 通过 FastAPI 暴露 REST 接口（适用于 Web 系统）
    """
    
    def __init__(self, executor: ToolExecutor):
        self.executor = executor
        self.server_info = {
            "name": "gym-web-system-mcp",
            "version": "1.0.0",
            "description": "健身房管理系统 MCP Server — 提供会员/员工/课程/财务等业务工具的 MCP 接口",
        }
    
    # ── MCP 协议端点 ──
    
    def handle_list_tools(self) -> Dict[str, Any]:
        """MCP tools/list — 列出所有可用工具"""
        return {
            "jsonrpc": "2.0",
            "result": {
                "tools": self.executor.get_mcp_tool_list(),
            },
        }
    
    def handle_call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """MCP tools/call — 调用指定工具"""
        result = self.executor.execute(tool_name, arguments or {})
        
        # MCP 协议要求返回 content 数组
        content = []
        if result.success:
            content.append({
                "type": "text",
                "text": json.dumps(result.data, ensure_ascii=False, default=str)
                if result.data is not None else "ok",
            })
        else:
            content.append({
                "type": "text",
                "text": f"错误: {result.error}",
            })
            return {
                "jsonrpc": "2.0",
                "result": {
                    "content": content,
                    "isError": True,
                },
            }
        
        return {
            "jsonrpc": "2.0",
            "result": {
                "content": content,
                "meta": {
                    "execution_time_ms": result.execution_time_ms,
                },
            },
        }
    
    def handle_list_resources(self) -> Dict[str, Any]:
        """MCP resources/list — 列出可用资源"""
        return {
            "jsonrpc": "2.0",
            "result": {
                "resources": [
                    {
                        "uri": "gym://members/list",
                        "name": "会员列表",
                        "description": "所有会员的基本信息",
                        "mimeType": "application/json",
                    },
                    {
                        "uri": "gym://staff/list",
                        "name": "员工列表",
                        "description": "所有员工的基本信息",
                        "mimeType": "application/json",
                    },
                    {
                        "uri": "gym://dashboard/stats",
                        "name": "仪表盘统计",
                        "description": "首页仪表盘统计数据",
                        "mimeType": "application/json",
                    },
                ],
            },
        }
    
    def handle_read_resource(self, uri: str) -> Dict[str, Any]:
        """MCP resources/read — 读取指定资源"""
        from backend.database import get_db
        
        db = next(get_db())
        try:
            if uri == "gym://members/list":
                from backend.models.models import Member
                members = db.query(Member).limit(100).all()
                data = [
                    {"id": m.member_id, "name": m.name, "phone": m.phone}
                    for m in members
                ]
            elif uri == "gym://staff/list":
                from backend.models.models import Staff
                staff = db.query(Staff).limit(100).all()
                data = [
                    {"id": s.staff_id, "name": s.name, "position": s.position}
                    for s in staff
                ]
            elif uri == "gym://dashboard/stats":
                from backend.models.models import Member, Staff, Course, Checkin
                data = {
                    "total_members": db.query(Member).count(),
                    "total_staff": db.query(Staff).count(),
                    "total_courses": db.query(Course).count(),
                    "today_checkins": db.query(Checkin).filter(
                        Checkin.checkin_date == datetime.now().date().isoformat()
                    ).count(),
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "content": [{"type": "text", "text": f"资源 '{uri}' 未找到"}],
                        "isError": True,
                    },
                }
            
            return {
                "jsonrpc": "2.0",
                "result": {
                    "content": [{
                        "type": "text",
                        "text": json.dumps(data, ensure_ascii=False, default=str),
                    }],
                },
            }
        finally:
            db.close()
    
    def handle_ping(self) -> Dict[str, Any]:
        """MCP ping — 健康检查"""
        return {
            "jsonrpc": "2.0",
            "result": {},
        }
    
    # ── 批量工具执行（非标准 MCP，为 AI agent 提供的批量接口） ──
    
    def handle_batch_execute(self, calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量执行多个工具调用"""
        results = []
        for call in calls:
            tool_name = call.get("name", "")
            arguments = call.get("arguments", {})
            result = self.executor.execute(tool_name, arguments)
            results.append({
                "tool": tool_name,
                "success": result.success,
                "data": result.data,
                "error": result.error,
            })
        return results
    
    # ── 信息查询 ──
    
    def get_server_info(self) -> Dict[str, Any]:
        """获取服务器信息"""
        tools = self.executor.list_tools()
        return {
            **self.server_info,
            "tool_count": len(tools),
            "tools_by_category": {
                cat: len([t for t in tools if t.category == cat])
                for cat in set(t.category for t in tools)
            },
        }
    
    def get_parity_report(self) -> Dict[str, Any]:
        """
        兼容性报告 — 对应 Claw Code 的 PARITY.md
        
        报告所有工具的注册状态和执行情况
        """
        tools = self.executor.list_tools()
        return {
            "total_tools": len(tools),
            "permission_distribution": {
                mode.value: len([t for t in tools if t.permission_mode == mode])
                for mode in PermissionMode
            },
            "category_distribution": {
                cat: len([t for t in tools if t.category == cat])
                for cat in sorted(set(t.category for t in tools))
            },
            "tools": [
                {
                    "name": t.name,
                    "category": t.category,
                    "permission": t.permission_mode.value,
                    "status": "registered",
                }
                for t in tools
            ],
        }
