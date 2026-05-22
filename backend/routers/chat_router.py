"""
聊天路由 — 提供 AI 对话 API 端点和前端页面
"""

from __future__ import annotations
import json
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from backend.mcp.executor import ToolExecutor
from backend.mcp.conversation import ConversationRuntime
from backend.mcp import get_executor


# ═══════════════════════════════════════════
# 请求/响应模型
# ═══════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    session_id: str


# ═══════════════════════════════════════════
# 路由
# ═══════════════════════════════════════════

router = APIRouter(prefix="/api/chat", tags=["AI 对话"])

# 全局 runtime 实例（懒初始化）
_runtime: Optional[ConversationRuntime] = None


def _get_runtime(request: Request = None) -> ConversationRuntime:
    """获取或创建 ConversationRuntime 实例"""
    global _runtime
    if _runtime is None:
        executor = get_executor()
        _runtime = ConversationRuntime(executor)
    return _runtime


@router.post("/message")
async def chat_message(
    req: ChatRequest,
    request: Request = None,
):
    """
    发送消息并获取回复
    
    Body:
    {
        "message": "今天有多少会员进场了？",
        "session_id": "default"      # 可选，用于隔离多用户对话
    }
    
    Response:
    {
        "reply": "今天有 15 位会员进场...",
        "session_id": "default"
    }
    """
    runtime = _get_runtime(request)
    
    try:
        reply = runtime.send_message(req.message, session_id=req.session_id)
        return {
            "reply": reply,
            "session_id": req.session_id,
        }
    except Exception as e:
        error_msg = str(e)
        if "LLM API 调用失败" in error_msg:
            detail = f"LLM 连接错误。{error_msg}"
        else:
            detail = f"对话处理错误: {error_msg}"
        raise HTTPException(status_code=500, detail=detail)


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    request: Request = None,
):
    """
    流式发送消息，通过 SSE 逐步推送回复
    
    事件类型:
    - data: {"type": "text", "content": "..."}     — 文本片段
    - data: {"type": "tool_calls", "count": 2}     — 工具调用
    - data: {"type": "tool_result", "tool": "...", "success": true}  — 工具结果
    - data: {"type": "done"}                        — 完成
    """
    runtime = _get_runtime(request)
    
    async def event_generator():
        try:
            async for chunk in runtime.stream_message(req.message, session_id=req.session_id):
                yield chunk
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history")
async def chat_history(
    session_id: str = "default",
    request: Request = None,
):
    """获取指定会话的对话历史"""
    runtime = _get_runtime(request)
    history = runtime.get_history(session_id)
    return {
        "session_id": session_id,
        "history": history,
    }


@router.post("/clear")
async def chat_clear(
    session_id: str = "default",
    request: Request = None,
):
    """清除指定会话的历史"""
    runtime = _get_runtime(request)
    runtime.clear_conversation(session_id)
    return {"status": "ok", "session_id": session_id}


# ═══════════════════════════════════════════
# 前端页面
# ═══════════════════════════════════════════

# 在 app.py 中注册页面路由
async def chat_page(request: Request):
    """AI 对话页面"""
    return HTMLResponse(_CHAT_PAGE_HTML)


_CHAT_PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 助手 — 健身管理系统</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        /* 自定义滚动条 */
        #chatContainer::-webkit-scrollbar { width: 6px; }
        #chatContainer::-webkit-scrollbar-track { background: transparent; }
        #chatContainer::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
        #chatContainer::-webkit-scrollbar-thumb:hover { background: #9ca3af; }

        /* 打字动画 */
        @keyframes blink { 0%,50% { opacity: 1; } 51%,100% { opacity: 0; } }
        .cursor-blink { animation: blink 0.8s infinite; }

        /* Markdown 渲染样式 */
        .markdown-body { line-height: 1.7; word-break: break-word; }
        .markdown-body p { margin: 0.4em 0; }
        .markdown-body p:first-child { margin-top: 0; }
        .markdown-body p:last-child { margin-bottom: 0; }
        .markdown-body strong { font-weight: 700; }
        .markdown-body em { font-style: italic; }
        .markdown-body ul, .markdown-body ol { padding-left: 1.5em; margin: 0.4em 0; }
        .markdown-body li { margin: 0.15em 0; }
        .markdown-body li > p { margin: 0; }
        .markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4 {
            font-weight: 700; margin: 0.8em 0 0.3em 0; line-height: 1.4;
        }
        .markdown-body h1 { font-size: 1.25rem; }
        .markdown-body h2 { font-size: 1.15rem; }
        .markdown-body h3 { font-size: 1.05rem; }
        .markdown-body code {
            background: #f3f4f6; padding: 0.15em 0.4em; border-radius: 4px;
            font-size: 0.85em; font-family: 'Cascadia Code', 'Fira Code', monospace;
        }
        .markdown-body pre {
            background: #1e293b; color: #e2e8f0; padding: 1em; border-radius: 10px;
            overflow-x: auto; margin: 0.6em 0; font-size: 0.85em; line-height: 1.6;
            position: relative;
        }
        .markdown-body pre code {
            background: none; padding: 0; color: inherit;
            font-size: inherit; border-radius: 0;
        }
        .markdown-body blockquote {
            border-left: 3px solid #93c5fd; padding: 0.3em 0.8em; margin: 0.5em 0;
            background: #f0f7ff; border-radius: 0 8px 8px 0; color: #475569;
        }
        .markdown-body hr { border: none; border-top: 1px solid #e5e7eb; margin: 0.8em 0; }

        /* 表格美化 */
        .markdown-body table {
            border-collapse: collapse; width: 100%; margin: 0.6em 0;
            font-size: 0.85em; border-radius: 10px; overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }
        .markdown-body thead tr { background: #eef2ff; }
        .markdown-body th {
            padding: 0.6em 0.8em; text-align: left; font-weight: 600;
            color: #1e293b; border-bottom: 2px solid #c7d2fe; white-space: nowrap;
        }
        .markdown-body td {
            padding: 0.5em 0.8em; border-bottom: 1px solid #f1f5f9; color: #334155;
        }
        .markdown-body tbody tr:hover { background: #f8fafc; }
        .markdown-body tbody tr:last-child td { border-bottom: none; }

        /* 用户气泡中的 markdown 覆盖 */
        .user-bubble .markdown-body p { color: white; }
        .user-bubble .markdown-body strong { color: #dbeafe; }
        .user-bubble .markdown-body code { background: rgba(255,255,255,0.15); color: #dbeafe; }
        .user-bubble .markdown-body table { background: rgba(255,255,255,0.1); color: white; }
        .user-bubble .markdown-body th,
        .user-bubble .markdown-body td { border-color: rgba(255,255,255,0.15); color: white; }
        .user-bubble .markdown-body thead tr { background: rgba(255,255,255,0.12); }
        .user-bubble .markdown-body th { border-bottom-color: rgba(255,255,255,0.2); color: white; }

        /* 打字闪烁光标 */
        .typing-cursor::after {
            content: '▊';
            color: #6366f1;
            animation: blink 0.8s infinite;
        }

        /* 代码块复制按钮 */
        .code-header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 0.3em 0.8em; background: #334155; border-radius: 10px 10px 0 0;
            font-size: 0.75em; color: #94a3b8; margin-bottom: 0;
        }
        .code-header + pre { border-radius: 0 0 10px 10px; margin-top: 0; }
        .copy-btn {
            cursor: pointer; padding: 0.15em 0.6em; border-radius: 4px;
            background: rgba(255,255,255,0.08); color: #94a3b8; border: none;
            font-size: inherit; transition: background 0.2s;
        }
        .copy-btn:hover { background: rgba(255,255,255,0.15); color: #e2e8f0; }

        /* 建议标签 */
        .suggestion-tag {
            display: inline-block; padding: 0.35em 0.8em; margin: 0.2em;
            background: #f0f4ff; border: 1px solid #dbeafe; color: #2563eb;
            border-radius: 999px; font-size: 0.8em; cursor: pointer;
            transition: all 0.15s; white-space: nowrap;
        }
        .suggestion-tag:hover { background: #dbeafe; border-color: #93c5fd; transform: translateY(-1px); }

        /* 消息进入动画 */
        .message-enter { animation: messageSlide 0.25s ease-out; }
        @keyframes messageSlide {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* 流式输出渐变 */
        .streaming-glow {
            box-shadow: 0 0 12px rgba(99, 102, 241, 0.1);
        }
    </style>
</head>
<body class="bg-gray-50 h-screen flex flex-col">
    <!-- 顶部导航 -->
    <header class="bg-gradient-to-r from-blue-900 to-blue-800 text-white px-6 py-3 flex items-center justify-between shadow-sm">
        <div class="flex items-center gap-3">
            <a href="/" class="text-white/60 hover:text-white transition text-sm flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                返回
            </a>
            <div class="w-px h-5 bg-white/20"></div>
            <h1 class="text-lg font-bold flex items-center gap-2">
                <span class="text-xl">🤖</span>
                AI 助手
            </h1>
            <span class="text-xs bg-white/10 px-2 py-0.5 rounded-full text-white/70">v3.6.2</span>
        </div>
        <div class="flex items-center gap-3">
            <button onclick="clearChat()" class="text-sm text-white/60 hover:text-white transition px-3 py-1.5 rounded-lg border border-white/20 hover:border-white/50 flex items-center gap-1">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                清除对话
            </button>
        </div>
    </header>

    <!-- 消息列表 -->
    <div id="chatContainer" class="flex-1 overflow-y-auto px-4 py-6">
        <div id="messages" class="max-w-4xl mx-auto space-y-5">
            <!-- 欢迎消息 -->
            <div class="flex justify-start message-enter">
                <div class="flex gap-3 max-w-[85%]">
                    <div class="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center text-white text-lg flex-shrink-0 shadow-sm mt-1">🤖</div>
                    <div class="bg-white rounded-2xl rounded-tl-sm px-5 py-3.5 shadow-sm border border-gray-100">
                        <div class="text-xs font-medium text-gray-400 mb-1.5">AI 助手</div>
                        <div class="markdown-body text-gray-800">
                            <p>你好！我是<strong>鼠小弟健身管理系统</strong>的 AI 助手 🧀</p>
                            <p>我可以帮你查询：</p>
                            <ul>
                                <li>🔍 <strong>会员信息</strong> — 资料、余额、进场记录</li>
                                <li>📊 <strong>经营数据</strong> — 今日进场、本月营收</li>
                                <li>👥 <strong>员工课程</strong> — 教练排班、课程信息</li>
                                <li>📈 <strong>业绩统计</strong> — 售课、课程包、会籍卡</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 快捷建议 -->
            <div id="suggestions" class="flex justify-start">
                <div class="ml-12 flex flex-wrap gap-1.5">
                    <span class="suggestion-tag" onclick="quickAsk('今天有多少会员进场了？')">📊 今日进场</span>
                    <span class="suggestion-tag" onclick="quickAsk('本月营收多少？')">💰 本月营收</span>
                    <span class="suggestion-tag" onclick="quickAsk('查一下鼠小弟的会员信息')">👤 查会员</span>
                    <span class="suggestion-tag" onclick="quickAsk('有哪些课程？')">🏋️ 课程列表</span>
                    <span class="suggestion-tag" onclick="quickAsk('教练的排班情况')">📅 排班</span>
                </div>
            </div>
        </div>

        <!-- 加载指示器 -->
        <div id="loading" class="hidden max-w-4xl mx-auto mt-4">
            <div class="flex gap-3">
                <div class="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center text-white text-lg flex-shrink-0 shadow-sm">🤖</div>
                <div class="bg-white rounded-2xl rounded-tl-sm px-5 py-4 shadow-sm border border-gray-100 streaming-glow">
                    <div class="flex items-center gap-2.5">
                        <div class="flex gap-1">
                            <div class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
                            <div class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
                            <div class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
                        </div>
                        <span class="text-sm text-gray-400">AI 正在思考...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 输入区 -->
    <div class="border-t bg-white px-4 py-4 shadow-[0_-1px_3px_rgba(0,0,0,0.04)]">
        <div class="max-w-4xl mx-auto">
            <div class="flex gap-3 items-end">
                <div class="flex-1 relative">
                    <input
                        id="input"
                        type="text"
                        placeholder="输入你的问题，例如「查一下鼠小弟的会员信息」"
                        class="w-full border border-gray-200 rounded-xl px-4 py-3 pr-10 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm bg-gray-50 hover:bg-white transition-colors"
                        onkeydown="if(event.key==='Enter') sendMessage()"
                    />
                </div>
                <button
                    id="sendBtn"
                    onclick="sendMessage()"
                    class="bg-indigo-600 text-white px-5 py-3 rounded-xl hover:bg-indigo-700 transition font-medium disabled:opacity-50 flex items-center gap-2 shadow-sm"
                    type="button"
                >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19V5m0 0l-7 7m7-7l7 7"/></svg>
                    发送
                </button>
            </div>
        </div>
    </div>

    <script>
        // ── 全局 JS 错误捕获 ──
        window.onerror = function(msg, url, line, col, err) {
            console.error('GLOBAL ERROR:', msg, line, col);
            // 如果发送按钮已禁用，恢复它
            var btn = document.getElementById('sendBtn');
            if (btn && btn.disabled) {
                btn.disabled = false;
                console.warn('sendBtn recovered from global error');
            }
            return true; // 阻止默认处理
        };

        // ── DOM 引用（延迟初始化） ──
        let messagesEl, inputEl, sendBtn, loadingEl, chatContainer;
        function initDom() {
            messagesEl = document.getElementById('messages');
            inputEl = document.getElementById('input');
            sendBtn = document.getElementById('sendBtn');
            loadingEl = document.getElementById('loading');
            chatContainer = document.getElementById('chatContainer');
            // 确保按钮初始可用
            if (sendBtn) sendBtn.disabled = false;
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initDom);
        } else {
            initDom();
        }

        // ── Markdown 渲染配置 ──
        // 使用内置简易渲染器，不依赖 marked.js（避免 CDN 问题和渲染 bug）

        function renderMarkdown(text) {
            // 简易 markdown 渲染器（不依赖 marked.js，避免 CDN 问题和渲染 bug）
            try {
                // 1. 过滤垃圾
                var cleanText = String(text)
                    .replace(/```tool_call[^]*?```/g, '')
                    .replace(/```json[^]*?```/g, '')
                    .replace(/```[^]*?```/g, '')
                    .replace(/<tool_calls?>[^]*?<\\/tool_calls?>/g, '')
                    .replace(/<DSML[^>]*>.*?<\\/DSML>/g, '');
                cleanText = cleanText.replace(/\[object\s+Object\](,[\s]*\[object\s+Object\])*undefined/gi, '');
                cleanText = cleanText.replace(/\[object\s+Object\]/gi, '');
                if (!cleanText.trim()) return '<p></p>';
                
                // 2. HTML 转义
                function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
                
                // 3. 分块处理
                var lines = cleanText.split(String.fromCharCode(10));
                var html = '';
                var inCodeBlock = false;
                var codeBlockLang = '';
                var codeBlockContent = '';
                var inTable = false;
                var tableHtml = '';
                
                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i];
                    
                    // 代码块
                    if (/^```/.test(line) && !inTable) {
                        if (inCodeBlock) {
                            // 结束代码块
                            var code = esc(codeBlockContent);
                            html += '<div class="code-header"><span>' + esc(codeBlockLang) + '</span></div><pre><code>' + code + '</code></pre>' + String.fromCharCode(10);
                            inCodeBlock = false;
                            codeBlockLang = '';
                            codeBlockContent = '';
                        } else {
                            inCodeBlock = true;
                            codeBlockLang = line.replace(/^```/, '').trim();
                            codeBlockContent = '';
                        }
                        continue;
                    }
                    
                    if (inCodeBlock) {
                        codeBlockContent += (codeBlockContent ? String.fromCharCode(10) : '') + line;
                        continue;
                    }
                    
                    // ---- 内联处理 ----
                    function renderInline(s) {
                        s = esc(s);
                        // **粗体**
                        s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
                        // *斜体*
                        s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
                        // `行内代码`
                        s = s.replace(/`(.+?)`/g, '<code>$1</code>');
                        // [text](url) 链接
                        s = s.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank">$1</a>');
                        return s;
                    }
                    
                    // 水平分割线
                    if (/^(-{3,}|_{3,}|\*{3,})$/.test(line.trim())) {
                        if (inTable) { /* 不处理表格内的 --- */ }
                        else { html += '<hr>' + String.fromCharCode(10); }
                        continue;
                    }
                    
                    // 标题 ### xxx
                    var headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
                    if (headingMatch && !inTable) {
                        var level = headingMatch[1].length;
                        var hText = renderInline(headingMatch[2]);
                        html += '<h' + level + '>' + hText + '</h' + level + '>' + String.fromCharCode(10);
                        continue;
                    }
                    
                    // 表格行
                    var tableRowMatch = line.match(/^\|(.+)\|$/);
                    if (tableRowMatch) {
                        var cells = tableRowMatch[1].split('|');
                        // 检查是否表头分隔行
                        var isSep = true;
                        for (var c = 0; c < cells.length; c++) {
                            if (!/^[\s:-]+$/.test(cells[c].trim())) { isSep = false; break; }
                        }
                        if (!inTable) {
                            inTable = true;
                            tableHtml = '<table><thead>';
                        }
                        
                        if (isSep) {
                            // 分隔行 → 结束 thead，开始 tbody
                            tableHtml = tableHtml.replace('<tbody>', '') + '</thead><tbody>';
                        } else {
                            var trHtml = '<tr>';
                            for (var c = 0; c < cells.length; c++) {
                                var tag = inTable && tableHtml.indexOf('</thead>') >= 0 ? 'td' : 'th';
                                trHtml += '<' + tag + '>' + renderInline(cells[c].trim()) + '</' + tag + '>';
                            }
                            trHtml += '</tr>';
                            tableHtml += trHtml;
                        }
                        continue;
                    } else if (inTable && !tableRowMatch) {
                        // 表格结束
                        tableHtml += '</tbody></table>' + String.fromCharCode(10);
                        html += tableHtml;
                        inTable = false;
                        tableHtml = '';
                    }
                    
                    // 空行
                    if (line.trim() === '') {
                        if (inTable) continue;
                        // 如果上文是非段落块，直接加空行
                        html += String.fromCharCode(10);
                        continue;
                    }
                    
                    // 普通段落行
                    if (!inTable) {
                        html += '<p>' + renderInline(line.trim()) + '</p>' + String.fromCharCode(10);
                    }
                }
                
                // 关闭未闭合的代码块
                if (inCodeBlock) {
                    var code = esc(codeBlockContent);
                    html += '<div class="code-header"><span>' + esc(codeBlockLang) + '</span></div><pre><code>' + code + '</code></pre>' + String.fromCharCode(10);
                }
                // 关闭未闭合的表格
                if (inTable) {
                    tableHtml += '</tbody></table>' + String.fromCharCode(10);
                    html += tableHtml;
                }
                
                return html;
            } catch(e) {
                console.warn('renderMarkdown error:', e);
                return '<pre style="white-space:pre-wrap;font-family:inherit;margin:0">'+String(text).replace(/</g,'&lt;').replace(/>/g,'&gt;')+'</pre>';
            }
        }

        // 高亮复制按钮
        function copyCode(btn) {
            const pre = btn.closest('.code-header').nextElementSibling;
            const code = pre.querySelector('code') || pre;
            const text = code.textContent;
            navigator.clipboard.writeText(text).then(() => {
                btn.textContent = '✅ 已复制';
                setTimeout(() => { btn.textContent = '📋 复制'; }, 1500);
            });
        }

        // ── 添加消息 ──
        function addMessage(role, text, isStreaming) {
            try {
                const div = document.createElement('div');
                div.className = (role === 'user' ? 'flex justify-end' : 'flex justify-start') + ' message-enter';

                if (role === 'user') {
                    div.innerHTML = `
                        <div class="bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 shadow-sm max-w-[75%] user-bubble">
                            <div class="text-xs font-medium text-indigo-200 text-right mb-1">👤 你</div>
                            <div class="markdown-body text-sm">${renderMarkdown(text)}</div>
                        </div>
                    `;
                } else {
                    div.innerHTML = `
                        <div class="flex gap-3 max-w-[85%]">
                            <div class="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center text-white text-lg flex-shrink-0 shadow-sm mt-0.5">🤖</div>
                            <div class="bg-white rounded-2xl rounded-tl-sm px-5 py-3.5 shadow-sm border border-gray-100 ${isStreaming ? 'streaming-glow' : ''}">
                                <div class="text-xs font-medium text-gray-400 mb-1.5">AI 助手</div>
                                <div class="markdown-body text-gray-800 text-sm">${renderMarkdown(text)}</div>
                            </div>
                        </div>
                    `;
                }

                messagesEl.appendChild(div);
                scrollToBottom();
                return div;
            } catch(e) {
                // 极端 fallback：纯文本消息
                const div = document.createElement('div');
                div.className = 'flex justify-start message-enter';
                div.textContent = role === 'user' ? ('👤 你: ' + text) : ('🤖: ' + text);
                messagesEl.appendChild(div);
                return div;
            }
        }

        // ── 流式更新消息 ──
        let lastAssistantEl = null;
        let lastContentDiv = null;

        function addOrUpdateAssistant(text, isStreaming) {
            if (!lastAssistantEl) {
                const div = document.createElement('div');
                div.className = 'flex justify-start message-enter';

                div.innerHTML = `
                    <div class="flex gap-3 max-w-[85%]">
                        <div class="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center text-white text-lg flex-shrink-0 shadow-sm mt-0.5">🤖</div>
                        <div class="bg-white rounded-2xl rounded-tl-sm px-5 py-3.5 shadow-sm border border-gray-100 streaming-glow" id="streamingBubble">
                            <div class="text-xs font-medium text-gray-400 mb-1.5">AI 助手</div>
                            <div class="markdown-body text-gray-800 text-sm" id="streamingContent"></div>
                        </div>
                    </div>
                `;

                messagesEl.appendChild(div);
                lastAssistantEl = div;
                lastContentDiv = div.querySelector('#streamingContent');
                scrollToBottom();
            }

            if (lastContentDiv) {
                if (isStreaming) {
                    // 流式打字期间：纯文本 + 闪烁光标（避免不完整 markdown 导致错误）
                    var escaped = String(text).replace(/</g, '&lt;').replace(/>/g, '&gt;');
                    lastContentDiv.innerHTML = '<pre style="white-space:pre-wrap;font-family:inherit;margin:0;font-size:inherit;color:inherit;background:none">' + escaped + '<span class="cursor-blink text-indigo-500">▊</span></pre>';
                } else {
                    // 完整内容：markdown 渲染
                    lastContentDiv.innerHTML = renderMarkdown(text);
                }
                scrollToBottom();
            }
        }

        function finalizeStreaming(fullReplyText) {
            if (lastContentDiv) {
                // 直接用原始回复文本渲染 markdown，避开 DOM textContent 可能的问题
                var rawText = typeof fullReplyText === 'string' ? fullReplyText : (lastContentDiv.textContent || '').replace(/▊/g, '');
                console.log('DEBUG finalize rawText:', rawText);
                // 检查是否有 [object Object]
                if (rawText.indexOf('[object Object]') >= 0) {
                    console.warn('DEBUG: rawText contains [object Object]!');
                }
                // 前端 + 后端双保险过滤
                rawText = rawText.replace(/\[object\s+Object\](,\s*\[object\s+Object\])*(undefined)?/gi, '');
                rawText = rawText.replace(/\[object\s+Object\]/gi, '');
                try {
                    var html = renderMarkdown(rawText);
                    if (typeof html === 'string') {
                        lastContentDiv.innerHTML = html;
                    } else {
                        lastContentDiv.innerHTML = '<pre>' + rawText.replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</pre>';
                    }
                } catch(e) {
                    lastContentDiv.innerHTML = '<pre>' + rawText.replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</pre>';
                }
                // 移除流光效果
                const bubble = document.getElementById('streamingBubble');
                if (bubble) {
                    bubble.classList.remove('streaming-glow');
                    bubble.id = '';
                }
            }
            lastAssistantEl = null;
            lastContentDiv = null;
        }

        function scrollToBottom() {
            setTimeout(() => {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }, 50);
        }

        // ── 发送消息 ──
        async function sendMessage() {
            const text = inputEl.value.trim();
            if (!text || sendBtn.disabled) return;

            inputEl.value = '';
            sendBtn.disabled = true;
            loadingEl.classList.remove('hidden');
            scrollToBottom();

            // 隐藏建议标签
            const suggestions = document.getElementById('suggestions');
            if (suggestions) suggestions.remove();

            // 添加用户消息
            addMessage('user', text);

            try {
                const response = await fetch('/api/chat/message', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: text, session_id: 'default'}),
                });

                loadingEl.classList.add('hidden');

                if (!response.ok) {
                    let detail = '未知错误';
                    try { const err = await response.json(); detail = err.detail || detail; } catch(e) {}
                    addMessage('assistant', '抱歉，处理出错：' + detail);
                    sendBtn.disabled = false;
                    return;
                }

                const data = await response.json();
                let reply = data.reply || '抱歉，我没有理解你的问题。';
                console.log('DEBUG api reply has [object]:', reply.indexOf('[object') >= 0);
                // 直接渲染 markdown
                try {
                    const el = addMessage('assistant', reply);
                    // 渲染后检查 DOM textContent 是否被污染（兜底）
                    setTimeout(() => {
                        try {
                            if (el) {
                                const contentEl = el.querySelector('.markdown-body');
                                if (contentEl) {
                                    const tc = contentEl.textContent || '';
                                    if (tc.indexOf('[object Object]') >= 0) {
                                        console.warn('DEBUG [object Object] found in DOM!');
                                        contentEl.innerHTML = '<pre style="white-space:pre-wrap;font-family:inherit;margin:0">' + String(reply).replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</pre>';
                                    }
                                }
                            }
                        } catch(e) { console.warn('post-render check error:', e); }
                    }, 50);
                } catch(e) {
                    console.warn('addMessage error:', e);
                    // 极端的全兜底
                    addMessage('assistant', '[回复内容] ' + String(reply));
                }
                sendBtn.disabled = false;
                inputEl.focus();

            } catch (err) {
                loadingEl.classList.add('hidden');
                addMessage('assistant', '网络错误，请稍后重试。');
                sendBtn.disabled = false;
            }
        }

        // ── 快捷问题 ──
        function quickAsk(text) {
            inputEl.value = text;
            sendMessage();
        }

        // ── 清除对话 ──
        async function clearChat() {
            if (!confirm('确定清除当前对话？')) return;
            try {
                await fetch('/api/chat/clear', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({session_id: 'default'}),
                });
                messagesEl.innerHTML = `
                    <div class="flex justify-start message-enter">
                        <div class="flex gap-3 max-w-[85%]">
                            <div class="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center text-white text-lg flex-shrink-0 shadow-sm mt-1">🤖</div>
                            <div class="bg-white rounded-2xl rounded-tl-sm px-5 py-3.5 shadow-sm border border-gray-100">
                                <div class="text-xs font-medium text-gray-400 mb-1.5">AI 助手</div>
                                <div class="markdown-body text-gray-800">
                                    <p>对话已清除 ✨ 有什么可以帮你的？</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div id="suggestions" class="flex justify-start">
                        <div class="ml-12 flex flex-wrap gap-1.5">
                            <span class="suggestion-tag" onclick="quickAsk('今天有多少会员进场了？')">📊 今日进场</span>
                            <span class="suggestion-tag" onclick="quickAsk('本月营收多少？')">💰 本月营收</span>
                            <span class="suggestion-tag" onclick="quickAsk('查一下鼠小弟的会员信息')">👤 查会员</span>
                            <span class="suggestion-tag" onclick="quickAsk('有哪些课程？')">🏋️ 课程列表</span>
                        </div>
                    </div>
                `;
            } catch (err) {
                alert('清除失败');
            }
        }

        // ── Enter 发送 ──
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey && document.activeElement === inputEl) {
                e.preventDefault();
                sendMessage();
            }
        });
    </script>
</body>
</html>"""
