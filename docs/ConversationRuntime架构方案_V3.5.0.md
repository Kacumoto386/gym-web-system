# ConversationRuntime 架构方案
## 版本: V3.5.0 | 日期: 2026-05-20

---

## 一、背景

V3.4.0 已完成 MCP + ToolExecutor 架构移植，系统拥有 21 个业务工具和完整的 MCP 协议支持，但缺少 **AI agent 对话循环**——LLM 无法自动调用这些工具来回答用户问题。

ConversationRuntime 提供完整的 LLM ↔ tools 交互循环，让自然语言查询能自动触发工具调用。

---

## 二、架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    客户端                                 │
│  ChatGPT / 网页 / API 调用                                │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP
┌────────────────────▼────────────────────────────────────┐
│              FastAPI 路由层                               │
│  POST /api/chat/message → 发送消息并获取回复               │
│  POST /api/chat/stream → 流式推送 (SSE)                  │
│  GET /api/chat/history → 获取对话历史                     │
│  POST /api/chat/clear → 清除对话                         │
│  GET /chat → AI 对话页面 (HTML)                          │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│           ConversationRuntime (核心引擎)                   │
│                                                          │
│  1. 接收用户消息                                          │
│  2. 构建 Tool-augmented System Prompt                     │
│  3. 调用 LLM API (OpenAI-compatible)                      │
│  4. 解析 LLM 输出 → 工具调用 / 最终回复                    │
│  5. 执行工具 → 结果返回 LLM → 回到步骤 3                   │
│  6. 返回最终回复给用户                                     │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              ToolExecutor (已移植)                        │
│  21 个业务工具 + 权限/钩子系统                             │
└─────────────────────────────────────────────────────────┘
```

---

## 三、核心循环流程

```
用户: "今天有多少会员进场了？"

Runtime:
  1. 构造 system prompt (含所有工具定义)
  2. 调用 LLM → LLM 返回 tool_call: get_dashboard_stats
  3. 执行 get_dashboard_stats → 得到统计结果
  4. 调用 LLM (带工具结果) → LLM 返回: "今天有 15 位会员进场"
  5. 返回给用户
```

### 多工具调用处理
```
用户: "查一下会员张三的信息和今天的进场记录"

Runtime:
  1. LLM 返回: 需要两个工具 → get_member + get_dashboard_stats
  2. 依次/并行执行两个工具
  3. 合并结果回传给 LLM
  4. LLM 给出自然语言回复
```

---

## 四、核心模块文件

| 文件 | 说明 | 
|------|------|
| `backend/mcp/conversation.py` | ConversationRuntime 引擎 + 对话管理 |
| `backend/routers/chat_router.py` | FastAPI 聊天路由（消息/流式/历史/页面） |
| `frontend/templates/chat.html` | AI 对话前端页面 |
| `backend/mcp/__init__.py` | 更新模块入口（注册 runtime） |

---

## 五、对话管理

### 消息格式
```python
@dataclass
class ChatMessage:
    role: str          # "user" | "assistant" | "system" | "tool"
    content: str       # 文本内容
    tool_calls: Optional[List[Dict]] = None  # LLM 请求的工具调用
    tool_call_id: Optional[str] = None        # 工具调用 ID
    name: Optional[str] = None                # 工具名称
```

### 会话存储
```python
class Conversation:
    messages: List[ChatMessage]    # 对话历史
    max_turns: int = 20            # 最大轮次（超了自动截断）
    created_at: datetime
```

- 全内存存储（重启丢失，无持久化需求）
- Session ID 通过 HTTP Session 或用户 ID 隔离
- 支持 `max_turns` 自动截断（保留最近的 N 轮）

---

## 六、LLM 集成

### 配置
```python
@dataclass
class LLMConfig:
    api_base: str           # OpenAI-compatible API 地址
    api_key: str            # API Key
    model: str              # 模型名称
    max_tokens: int = 4096
    temperature: float = 0.1
```

### 获取方式
1. **环境变量**: `OPENAI_API_BASE`, `OPENAI_API_KEY`, `OPENAI_MODEL`
2. **后端配置文件**: `config/llm.toml`（可选）
3. **默认值**: 通过环境变量回退到 `http://localhost:11434/v1`（Ollama）

### System Prompt 构造
```python
SYSTEM_PROMPT = """你是鼠小弟健身管理系统的 AI 助手。你有一组工具可以使用。

可用工具：
{tool_descriptions}

使用工具时，请严格按照以下 JSON 格式响应：
```tool_call
{{"name": "工具名称", "arguments": {{"参数1": "值1", ...}}}}
```

如果无需调用工具，直接给出自然语言回复。
"""
```

---

## 七、API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat/message` | POST | 发送消息，获取完整回复 |
| `/api/chat/stream` | POST | 发送消息，SSE 流式推送 |
| `/api/chat/history` | GET | 获取当前会话的对话历史 |
| `/api/chat/clear` | POST | 清除当前会话 |
| `/chat` | GET | AI 对话页面 (HTML) |

---

## 八、前端页面设计

类似 ChatGPT 的聊天界面：
- 左侧：对话历史列表（后续可加）
- 主要区：消息气泡（用户/助手/工具调用）
- 底部：输入框 + 发送按钮
- 流式输出：打字机效果

### 技术栈
- 纯 HTML + Tailwind CSS（复用项目已有 CDN）
- Server-Sent Events (SSE) 实现流式推送
- 无额外前端依赖

---

## 九、与 Claw Code 架构的对应关系

| Claw Code (Rust) | gym-web-system (Python) | 状态 |
|------------------|------------------------|------|
| `ConversationRuntime` | `ConversationRuntime` | 🆕 |
| `ChatMessage / ChatHistory` | `ChatMessage / Conversation` | 🆕 |
| `LLM provider` | `_call_llm()` + OpenAI SDK | 🆕 |
| `Tool-augmented system prompt` | `_build_system_prompt()` | 🆕 |
| `Streaming callback` | SSE streaming | 🆕 |
| `Auto summary / truncation` | `_truncate_history()` | 🆕 |

---

## 十、依赖

- Python 3.12+
- `openai` — OpenAI API 客户端（已有/可安装）
- FastAPI + SSE（streaming）
- 无其他新增依赖
