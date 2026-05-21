"""
ConversationRuntime
===================
LLM ↔ 工具 对话循环引擎。

功能:
- 接收用户自然语言消息
- 自动调用 MCP 工具回答用户问题
- 多轮对话管理（历史截断/上下文保持）
- 支持 SSE 流式推送
- 支持 OpenAI-compatible API（OpenAI / Ollama / 任意兼容后端）

用法:
    runtime = ConversationRuntime(executor)
    reply = runtime.send_message("今天有多少会员进场了？")
    # → "今天有 15 位会员进场，其中 12 人刷卡，3 人无卡体验"
"""

from __future__ import annotations
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, AsyncIterator

from openai import OpenAI

from backend.mcp.executor import ToolExecutor, ToolDefinition


# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════

@dataclass
class LLMConfig:
    """LLM 配置"""
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.1

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """从环境变量读取配置（自动加载 .env 文件）"""
        try:
            env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            k, v = line.split('=', 1)
                            os.environ[k.strip()] = v.strip()
        except Exception:
            pass
        return cls(
            api_base=os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1"),
            api_key=os.getenv("OPENAI_API_KEY", "sk-placeholder"),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        )


# ═══════════════════════════════════════════
# 消息模型
# ═══════════════════════════════════════════

@dataclass
class ChatMessage:
    """单条对话消息"""
    role: str                     # "user" | "assistant" | "system" | "tool"
    content: str = ""              # 文本内容
    tool_calls: Optional[List[Dict]] = None  # LLM 请求的工具调用
    tool_call_id: Optional[str] = None        # 工具调用 ID
    name: Optional[str] = None                 # 工具名称
    timestamp: float = field(default_factory=time.time)

    def to_openai_dict(self) -> Dict:
        """转换为 OpenAI API 兼容的消息字典"""
        msg = {"role": self.role}
        if self.content:
            msg["content"] = self.content
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg


@dataclass
class Conversation:
    """对话会话 — 存储消息历史"""
    messages: List[ChatMessage] = field(default_factory=list)
    max_turns: int = 20            # 最大轮次（超过自动截断）
    created_at: float = field(default_factory=time.time)

    def add_message(self, msg: ChatMessage):
        """添加一条消息，自动触发截断"""
        self.messages.append(msg)
        self._truncate_if_needed()

    def _truncate_if_needed(self):
        """如果消息数量超过 max_turns，保留最近的 N 轮"""
        if len(self.messages) > self.max_turns * 2 + 5:
            # 保留 system prompt + 最近 max_turns*2 条消息
            system_msgs = [m for m in self.messages if m.role == "system"]
            recent_msgs = [m for m in self.messages if m.role != "system"]
            self.messages = system_msgs + recent_msgs[-(self.max_turns * 2):]

    def to_openai_messages(self) -> List[Dict]:
        """转换为 OpenAI API 兼容的消息列表"""
        return [m.to_openai_dict() for m in self.messages]

    def clear(self):
        """清除所有消息"""
        self.messages.clear()


# ═══════════════════════════════════════════
# System Prompt 模板
# ═══════════════════════════════════════════

SYSTEM_PROMPT_TEMPLATE = """你是鼠小弟健身管理系统的 AI 助手。用户会根据他们的健身房业务提问，你可以使用以下工具来查找信息和执行操作。

## 规则
1. 当用户的问题需要数据时，**必须**使用工具来获取真实数据，不要凭空编造
2. 每次可以调用一个或多个工具（并行调用）
3. 如果工具返回的数据不足以回答问题，可以继续调用其他工具
4. 最终回答需要自然流畅，不要暴露工具调用的技术细节
5. 如果用户的请求涉及写入操作（创建/修改/删除），先确认再执行

## 可用工具
{tool_descriptions}

## 响应格式
如果需要调用工具，请输出一个 JSON 格式的工具调用：
```tool_call
{{"name": "工具名称", "arguments": {{"参数1": "值1"}}}}
```

如果需要同时调用多个工具，请在一组三引号内输出多行 JSON，每行一个调用：
```tool_call
{{"name": "工具1", "arguments": {{...}}}}
{{"name": "工具2", "arguments": {{...}}}}
```

如果无需调用工具，直接给出自然语言回复即可。

## 回答排版要求
你的回答会以 Markdown 格式渲染到前端界面，请遵守以下排版规则：

### 数据展示
- **多条数据时使用表格**：当需要展示多个会员/员工/课程记录时，优先使用 markdown 表格
- **表格格式**：第一行为表头加粗，对齐工整，不要多余空格
- **单条数据使用卡片式描述**：用 `**字段**：值` 格式，分点列出
- **数值对齐**：金额数值保留小数点后 2 位，百分比用整数

### 格式规范
- **标题层级**：用 `###` 作为小节标题，不要用 `#`
- **重要数据加粗**：会员姓名、金额、数量等关键数字用 `**粗体**`
- **状态用 emoji 标注**：正常 ✅、异常 ❌、待处理 ⏳、已完成 ✅
- **列表用 `-`**：不要用 `*`
- **禁止输出 tool_call 相关内容**：不要在你的回答中包含任何工具调用的原始数据或 JSON

### 美观要求
- 每个段落之间空行分隔
- 数据较多时分小节展示，用 `---` 分隔不同部分
- 回答开头先用一句话总结，再展开细节
"""


# ═══════════════════════════════════════════
# ConversationRuntime — 核心引擎
# ═══════════════════════════════════════════

class ConversationRuntime:
    """
    对话循环引擎
    
    负责:
    1. 维护对话历史
    2. 构造 tool-augmented 的 system prompt
    3. 调用 LLM
    4. 解析工具调用请求
    5. 执行工具
    6. 将结果送回 LLM
    7. 返回最终回复
    """
    
    def __init__(
        self,
        executor: ToolExecutor,
        llm_config: Optional[LLMConfig] = None,
    ):
        self.executor = executor
        self.llm_config = llm_config or LLMConfig.from_env()
        self._client: Optional[OpenAI] = None
        self._conversations: Dict[str, Conversation] = {}
    
    # ── 客户端 ──
    
    def _get_client(self) -> OpenAI:
        """获取或创建 OpenAI 客户端"""
        if self._client is None:
            self._client = OpenAI(
                base_url=self.llm_config.api_base,
                api_key=self.llm_config.api_key,
            )
        return self._client
    
    # ── System Prompt ──
    
    def _build_system_prompt(self) -> str:
        """构造工具增强的 system prompt"""
        tools = self.executor.list_tools()
        tool_descriptions = []
        for t in tools:
            tool_descriptions.append(
                f"- **{t.name}** ({t.category}): {t.description}\n"
                f"  参数: {json.dumps(t.input_schema, ensure_ascii=False)}"
            )
        return SYSTEM_PROMPT_TEMPLATE.format(
            tool_descriptions="\n".join(tool_descriptions)
        )
    
    # ── 工具调用解析 ──
    
    _TOOL_CALL_PATTERN = re.compile(
        r'```tool_call\s*\n(.*?)\n```',
        re.DOTALL,
    )
    _DSML_INVOKE_PATTERN = re.compile(
        r'<(?:DSML)?invoke\s+name="(\w+)"(.*?)</(?:DSML)?invoke>',
        re.DOTALL,
    )
    _DSML_PARAM_PATTERN = re.compile(
        r'<(?:DSML)?parameter\s+name="(\w+)"\s+string="true">(.*?)</(?:DSML><)?(?:DSML)?parameter>',
        re.DOTALL,
    )
    
    def _extract_tool_calls(self, text: str) -> Optional[List[Dict]]:
        """从 LLM 回复中提取工具调用（支持 JSON 和 DSML/XML 格式）"""
        # 尝试 JSON 格式 (```tool_call)
        matches = self._TOOL_CALL_PATTERN.findall(text)
        if matches:
            calls = []
            for block in matches:
                for line in block.strip().split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        call = json.loads(line)
                        if "name" in call:
                            calls.append(call)
                    except json.JSONDecodeError:
                        continue
            return calls if calls else None
        
        # 尝试 XML 格式 (<invoke name="..." ...> 或 <DSML><invoke ...>)
        xml_matches = self._DSML_INVOKE_PATTERN.findall(text)
        if xml_matches:
            calls = []
            for name, params_block in xml_matches:
                params = {}
                param_matches = self._DSML_PARAM_PATTERN.findall(params_block)
                for pname, pvalue in param_matches:
                    params[pname] = pvalue
                calls.append({"name": name, "parameters": params, "arguments": params})
            return calls if calls else None
        
        return None
    
    def _clean_assistant_response(self, text: str) -> str:
        """Remove tool_call/XML/DSML/backtick blocks and garbage text, keep NL text"""
        text = self._TOOL_CALL_PATTERN.sub("", text)
        # DeepSeek DSML tag blocks (variants: <DSML>, <DSMLtool_calls>, etc)
        text = re.sub(r'<DSML>.*?</DSML>', '', text, flags=re.DOTALL)
        text = re.sub(r'<DSMLtool_calls>.*?</DSMLtool_calls>', '', text, flags=re.DOTALL)
        text = re.sub(r'<tool_calls>.*?</tool_calls>', '', text, flags=re.DOTALL)
        text = re.sub(r'<invoke\s+name=.*?</invoke>', '', text, flags=re.DOTALL)
        # Markdown code blocks (```xml, ```json, ```)
        text = re.sub(r'```(?:xml|json)\s*\n.*?\n```', '', text, flags=re.DOTALL)
        text = re.sub(r'```\s*\n.*?\n```', '', text, flags=re.DOTALL)
        # Residual single-line XML tags
        lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped.startswith('<') and stripped.endswith('>'):
                continue
            lines.append(line)
        result = '\n'.join(lines).strip()
        # 强力过滤 [object Object] 类垃圾文本（LLM 偶尔会输出这些）
        result = re.sub(r'\[object\s+Object\](,\s*\[object\s+Object\])*(undefined)?', '', result)
        result = result.replace('[object Object]', '')
        return result.strip()

    def send_message(
        self,
        message: str,
        session_id: str = "default",
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        发送用户消息，获取完整回复
        
        Args:
            message: 用户消息
            session_id: 会话 ID（用于隔离多用户对话）
            stream_callback: 流式回调（每收到一段文本就调用）
            
        Returns:
            最终回复文本
        """
        conv = self._get_or_create_conversation(session_id)
        
        # 1. 首次对话时注入 system prompt
        if not conv.messages:
            system_prompt = self._build_system_prompt()
            conv.add_message(ChatMessage(role="system", content=system_prompt))
        
        # 2. 添加用户消息
        conv.add_message(ChatMessage(role="user", content=message))
        
        # 3. 循环：LLM → 工具执行 → LLM → …
        max_iterations = 10  # 防止无限循环
        for iteration in range(max_iterations):
            # 调用 LLM
            reply = self._call_llm(conv.to_openai_messages())
            
            # 清理 DeepSeek 返回的 FF5C 控制字符（U+FF5C 全角竖线）
            reply = reply.replace(chr(0xFF5C), '')
            
            # 提取工具调用
            tool_calls = self._extract_tool_calls(reply)
            
            if tool_calls:
                # 有工具调用 → 执行工具 → 结果加回对话 → 继续
                clean_reply = self._clean_assistant_response(reply)
                if clean_reply:
                    conv.add_message(ChatMessage(
                        role="assistant",
                        content=clean_reply,
                        tool_calls=[{
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": c["name"],
                                "arguments": json.dumps(c.get("arguments", {}), ensure_ascii=False),
                            },
                        } for i, c in enumerate(tool_calls)],
                    ))
                    if stream_callback:
                        stream_callback(clean_reply)
                else:
                    # 仅 tool_call 无文本的 assistant 消息
                    conv.add_message(ChatMessage(
                        role="assistant",
                        content="",
                        tool_calls=[{
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": c["name"],
                                "arguments": json.dumps(c.get("arguments", {}), ensure_ascii=False),
                            },
                        } for i, c in enumerate(tool_calls)],
                    ))
                
                # 执行每个工具
                for call in tool_calls:
                    tool_name = call["name"]
                    arguments = call.get("arguments", {})

                    
                    result = self.executor.execute(tool_name, arguments)
                    
                    tool_msg_content = (
                        json.dumps(result.data, ensure_ascii=False, default=str)
                        if result.success
                        else f"错误: {result.error}"
                    )
                    # 防御性过滤：json.dumps 的 default=str 可能输出 "[object Object]"
                    tool_msg_content = re.sub(r'"\[object\s+Object\]"(,\s*"\[object\s+Object\]")*("undefined")?', '', tool_msg_content)
                    tool_msg_content = tool_msg_content.replace('"[object Object]"', '')
                    
                    conv.add_message(ChatMessage(
                        role="tool",
                        content=tool_msg_content,
                        tool_call_id=f"call_{tool_calls.index(call)}",
                        name=tool_name,
                    ))
                
                # 继续下一轮 LLM 调用
                continue
            else:
                # 无工具调用 → 最终回复
                reply = self._clean_assistant_response(reply)
                conv.add_message(ChatMessage(role="assistant", content=reply))
                if stream_callback:
                    stream_callback(reply)
                return reply
        
        # 到达最大迭代次数
        fallback = "抱歉，处理超时，请简化你的问题。"
        conv.add_message(ChatMessage(role="assistant", content=fallback))
        return fallback
    
    def _call_llm(self, messages: List[Dict]) -> str:
        """调用 LLM API 获取回复"""
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=self.llm_config.model,
                messages=messages,
                max_tokens=self.llm_config.max_tokens,
                temperature=self.llm_config.temperature,
            )
            raw = response.choices[0].message.content or ""
            # 在源头过滤垃圾文本，避免污染对话历史
            if '[object' in raw:
                log.warning(f"LLLLM: [object Object] detected in LLM output! len={len(raw)}, preview={raw[:200]}")
                raw = raw.replace('[object Object]', '[FILTERED]')
                raw = raw.replace('[object', '[FIL')

            # 另外也过滤工具调用参数中的 object Object（如果 DeepSeek 在参数中加入了垃圾文本）
            raw = re.sub(r'\[object\s+Object\](,\s*\[object\s+Object\])*(undefined)?', '', raw)
            raw = raw.replace('[object Object]', '')
            return raw
        except Exception as e:
            error_msg = str(e)
            raise RuntimeError(
                f"LLM API 调用失败: {error_msg}\n"
                f"请检查 LLM 配置：OPENAI_API_BASE={self.llm_config.api_base}, "
                f"OPENAI_MODEL={self.llm_config.model}"
            ) from e
    
    # ── 流式（SSE） ──
    
    async def stream_message(
        self,
        message: str,
        session_id: str = "default",
    ) -> AsyncIterator[str]:
        """
        流式发送消息，逐步推送回复
        
        用于 SSE 端点，每 yield 一段文本就推送给前端
        """
        conv = self._get_or_create_conversation(session_id)
        
        if not conv.messages:
            system_prompt = self._build_system_prompt()
            conv.add_message(ChatMessage(role="system", content=system_prompt))
        
        conv.add_message(ChatMessage(role="user", content=message))
        
        max_iterations = 10
        final_reply = ""
        
        for iteration in range(max_iterations):
            reply = self._call_llm(conv.to_openai_messages())
            tool_calls = self._extract_tool_calls(reply)
            
            if tool_calls:
                clean_reply = self._clean_assistant_response(reply)
                if clean_reply:
                    conv.add_message(ChatMessage(
                        role="assistant",
                        content=clean_reply,
                        tool_calls=[{
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": c["name"],
                                "arguments": json.dumps(c.get("arguments", {}), ensure_ascii=False),
                            },
                        } for i, c in enumerate(tool_calls)],
                    ))
                    final_reply += clean_reply
                    yield f"data: {json.dumps({'type': 'text', 'content': clean_reply})}\n\n"
                    yield f"data: {json.dumps({'type': 'tool_calls', 'count': len(tool_calls)})}\n\n"
                else:
                    conv.add_message(ChatMessage(
                        role="assistant",
                        content="",
                        tool_calls=[{
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": c["name"],
                                "arguments": json.dumps(c.get("arguments", {}), ensure_ascii=False),
                            },
                        } for i, c in enumerate(tool_calls)],
                    ))
                    yield f"data: {json.dumps({'type': 'tool_calls', 'count': len(tool_calls)})}\n\n"
                
                for call in tool_calls:
                    tool_name = call["name"]
                    arguments = call.get("arguments", {})
                    result = self.executor.execute(tool_name, arguments)
                    
                    yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'success': result.success})}\n\n"
                    
                    tool_msg_content = (
                        json.dumps(result.data, ensure_ascii=False, default=str)
                        if result.success
                        else f"错误: {result.error}"
                    )
                    
                    conv.add_message(ChatMessage(
                        role="tool",
                        content=tool_msg_content,
                        tool_call_id=f"call_{tool_calls.index(call)}",
                        name=tool_name,
                    ))
                continue
            else:
                conv.add_message(ChatMessage(role="assistant", content=reply))
                final_reply += reply
                yield f"data: {json.dumps({'type': 'text', 'content': reply})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return
        
        fallback = "抱歉，处理超时。"
        conv.add_message(ChatMessage(role="assistant", content=fallback))
        yield f"data: {json.dumps({'type': 'text', 'content': fallback})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    # ── 对话管理 ──
    
    def _get_or_create_conversation(self, session_id: str) -> Conversation:
        """获取或创建会话"""
        if session_id not in self._conversations:
            self._conversations[session_id] = Conversation()
        return self._conversations[session_id]
    
    def get_history(self, session_id: str = "default") -> List[Dict]:
        """获取对话历史（JSON 安全格式）"""
        conv = self._conversations.get(session_id)
        if not conv:
            return []
        return [
            {"role": m.role, "content": m.content[:200] if m.content else ""}
            for m in conv.messages
            if m.role != "system"  # 不暴露 system prompt
        ]
    
    def clear_conversation(self, session_id: str = "default"):
        """清除指定会话"""
        if session_id in self._conversations:
            del self._conversations[session_id]
    
    def get_tool_descriptions_for_debug(self) -> str:
        """调试用：获取工具描述的纯文本"""
        return self._build_system_prompt()
