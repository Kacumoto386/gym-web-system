# MCP + ToolExecutor 架构移植方案
## 版本: V3.4.0 | 日期: 2026-05-20

---

## 一、背景

从 [claw-code](https://github.com/Kacumoto386/claw-code) 移植其核心的 ToolExecutor + MCP 架构到 gym-web-system。

### 来源项目架构

Claw Code 的 Rust 实现包含:
- **ToolExecutor trait** — 泛型工具执行引擎
- **GlobalToolRegistry** — 工具注册表（内置 + 插件 + MCP + Runtime）
- **PermissionMode** — 三级权限模型（read-only / workspace-write / danger-full-access）
- **McpServer** — MCP 协议服务端（tools/list, tools/call, resources/list, resources/read, ping）
- **Hook 系统** — pre/post tool 钩子（Claw Code 的 HookRunner）
- **McpToolRegistry + McpToolBridge** — MCP 工具注册和桥接
- **ConversationRuntime** — 完整的 LLM ↔ tools 交互循环（暂未移植）

### 移植原则

1. **保持 Python 风格** — 不强行照搬 Rust 的 trait/泛型，用 Pythonic 的 dataclass + 鸭子类型
2. **适配 FastAPI** — MCP 协议通过 HTTP 端点暴露
3. **接入真实数据** — 所有工具直接操作 gym.db 已有数据
4. **可扩展** — 新业务模块只需添加一个 register_xxx_tools() 函数

---

## 二、架构设计

```
┌─────────────────────────────────────────────────────┐
│                   客户端                               │
│  AI Agent / 浏览器 / 命令行                            │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP (JSON-RPC)
┌──────────────────▼──────────────────────────────────┐
│              FastAPI 路由层                           │
│  /api/mcp/ping → handle_ping()                       │
│  /api/mcp/tools → handle_list_tools()                │
│  /api/mcp/call-tool → handle_call_tool()             │
│  /api/mcp/resources → handle_list_resources()        │
│  /api/mcp/read-resource → handle_read_resource()     │
│  /api/mcp/batch-execute → handle_batch_execute()     │
│  /api/mcp/server-info → 服务器信息                    │
│  /api/mcp/parity-report → 兼容性报告                   │
│  /api/mcp/set-permission → 设置权限                    │
│  /api/mcp/search-tools → 搜索工具                      │
│  /mcp-tools → 管理界面 (HTML)                          │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│              McpServer (协议层)                       │
│  - 实现 MCP JSON-RPC 协议                            │
│  - 将 HTTP 请求转为 ToolExecutor 调用                 │
│  - 处理错误/格式化输出                                │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│              ToolExecutor (核心引擎)                   │
│  - 工具注册 / 查找 / 执行                              │
│  - 三级权限检查                                        │
│  - Pre/Post Hook 系统                                 │
│  - MCP 兼容工具列表生成                                 │
└─────────┬────────────────────────┬──────────────────┘
          │                        │
┌─────────▼──────────┐  ┌─────────▼──────────┐
│  业务工具定义        │  │  MCP 资源          │
│  - 会员: 6个工具     │  │  - members/list    │
│  - 员工: 2个工具     │  │  - staff/list      │
│  - 课程: 2个工具     │  │  - dashboard/stats │
│  - 售课: 3个工具     │  │                     │
│  - 进场: 3个工具     │  │                     │
│  - 财务: 1个工具     │  │                     │
│  - 手环: 1个工具     │  │                     │
│  - 仪表盘: 1个工具   │  │                     │
│  - 系统: 2个工具     │  │                     │
└─────────────────────┘  └─────────────────────┘
```

---

## 三、核心模块文件

| 文件 | 说明 | 代码行数 |
|------|------|---------|
| `backend/mcp/executor.py` | ToolExecutor 引擎 + McpServer 协议层 | ~15KB |
| `backend/mcp/business_tools.py` | 所有业务工具定义 (21个工具) | ~31KB |
| `backend/routers/mcp_router.py` | FastAPI 路由注册 | ~5KB |
| `frontend/templates/mcp_tools.html` | MCP 工具管理页面 | ~12KB |
| `backend/mcp/__init__.py` | 模块入口文档 | 0.3KB |

---

## 四、工具清单（21个）

### 只读工具 (16个)
| 工具名 | 分类 | 说明 |
|--------|------|------|
| get_member | 会员管理 | 按编号/手机/姓名查询会员 |
| list_members | 会员管理 | 分页查询会员列表 |
| get_member_balance | 会员管理 | 查询会员储值余额 |
| get_staff | 员工管理 | 查询员工信息 |
| list_staff | 员工管理 | 分页查询员工列表 |
| list_courses | 课程管理 | 查询课程列表 |
| get_course_stats | 课程管理 | 课程统计数据 |
| list_sales | 售课管理 | 查询售课记录 |
| get_sale_summary | 售课管理 | 售课汇总统计 |
| list_checkins | 进场核销 | 查询进场记录 |
| get_checkin_stats | 进场核销 | 进场统计 |
| get_finance_summary | 财务管理 | 财务汇总 |
| get_dashboard_stats | 仪表盘 | 首页仪表盘统计 |
| find_member_by_wristband | 手环管理 | 通过手环读卡器值查找会员 |
| get_system_info | 系统 | 系统基本信息 |
| search | 系统 | 全局搜索 |

### 写入工具 (4个)
| 工具名 | 分类 | 说明 |
|--------|------|------|
| create_member | 会员管理 | 创建新会员 |
| update_member | 会员管理 | 更新会员信息 |
| create_sale | 售课管理 | 创建售课记录 |
| checkin_member | 进场核销 | 会员进场签到 |

### 危险工具 (1个)
| 工具名 | 分类 | 说明 |
|--------|------|------|
| delete_member | 会员管理 | 删除会员（不可恢复） |

---

## 五、权限模型

```
PermissionMode.READ_ONLY (1)      → 可查看，不可修改
PermissionMode.WORKSPACE_WRITE (2) → 可增删改普通数据
PermissionMode.DANGER_FULL_ACCESS (3) → 可执行危险操作（删除等）
```

工具注册时指定所需最低权限，执行时自动检查。

---

## 六、Hook 系统

对应 Claw Code 的 HookRunner：
- **Pre-hook** — 工具执行前调用，返回 None 放行，返回字符串拒绝
- **Post-hook** — 工具执行后调用，可记录日志/审计

---

## 七、MCP 协议支持

完全兼容 JSON-RPC 2.0 格式的 MCP 协议：

### 已实现
- ✅ `ping` — 健康检查
- ✅ `tools/list` — 列出工具（含权限过滤）
- ✅ `tools/call` — 调用工具
- ✅ `resources/list` — 列出资源
- ✅ `resources/read` — 读取资源

### 扩展
- ✅ `batch-execute` — 批量执行（非标准）
- ✅ `server-info` — 服务器信息
- ✅ `parity-report` — 兼容性报告
- ✅ `set-permission` — 设置当前权限
- ✅ `search-tools` — 搜索工具

---

## 八、完成的功能测试

- ✅ 21个工具全部注册成功
- ✅ MCP Ping 返回正确
- ✅ MCP List Tools 返回工具列表（含权限过滤）
- ✅ MCP List Resources 返回资源列表
- ✅ MCP Call Tool（系统信息）返回正确
- ✅ MCP Call Tool（数据库查询：仪表盘）返回真实数据
- ✅ MCP Call Tool（数据库查询：会员列表）返回真实数据
- ✅ MCP Call Tool（全局搜索）返回正确
- ✅ 权限系统：READ_ONLY 拒绝删除，FULL_ACCESS 允许所有
- ✅ Parity Report 生成正确（21个工具/9分类/3级权限）
- ✅ HTTP 端点全部可达
- ✅ 管理页面可访问

---

## 九、与 Claw Code 架构的对应关系

| Claw Code (Rust) | gym-web-system (Python) | 状态 |
|------------------|------------------------|------|
| `ToolSpec` / `RuntimeToolDefinition` | `ToolDefinition` (dataclass) | ✅ |
| `GlobalToolRegistry` | `ToolExecutor._tools` (dict) | ✅ |
| `ToolExecutor` trait (Rust trait) | `ToolExecutor.execute()` (method) | ✅ |
| `PermissionMode` | `PermissionMode` (Enum) | ✅ |
| `PermissionPolicy.authorize()` | `permission_ge()` + execute 内检查 | ✅ |
| `HookRunner` (pre/post hook) | `_run_pre_hooks()` / `_run_post_hooks()` | ✅ |
| `McpServer` | `McpServer` class | ✅ |
| `McpToolRegistry` / `McpToolBridge` | `McpServer` 内置 | ✅ |
| `ConversationRuntime` | 未移植（后续） | ⏳ |
| `McpClient` | 未移植（后续） | ⏳ |
| `PluginSystem` / `PluginManager` | 未移植（后续） | ⏳ |
| `Session / SessionStore` | 未移植（后续） | ⏳ |
| `Agent / Team / Cron` | 未移植（后续） | ⏳ |

---

## 十、后续扩展方向

1. **ConversationRuntime** — 完整的 LLM 对话循环，支持 AI agent 自动调用工具
2. **McpClient** — 对接外部 MCP Server（如数据库/API gateway）
3. **Plugin 系统** — 支持热插拔业务模块
4. **Session 管理** — 多会话/多 agent 协调
5. **Auto compaction** — 长对话自动摘要压缩
6. **Tool 缓存** — 高频查询结果缓存
7. **异步工具执行** — 长时间运行的后台工具

---

## 十一、启动 && 验证

```bash
# 启动
cd gym-web-system
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000

# 验证
curl http://127.0.0.1:8000/api/mcp/ping
curl http://127.0.0.1:8000/api/mcp/tools
curl -X POST http://127.0.0.1:8000/api/mcp/call-tool \
  -H "Content-Type: application/json" \
  -d '{"name":"get_dashboard_stats","arguments":{}}'

# 管理界面
# http://127.0.0.1:8000/mcp-tools
```

---

## 十二、依赖

- Python 3.12+
- FastAPI + SQLAlchemy
- 无新增外部依赖（复用项目已有依赖）
