// ── AI 助手浮动窗口 ──
var _chatOpen = false;
var _chatLoading = false;
var _chatMsgId = 0;

function toggleChat() {
    _chatOpen = !_chatOpen;
    var d = document.getElementById('chatDialog');
    var t = document.getElementById('chatToggle');
    d.className = _chatOpen ? 'show' : '';
    t.className = _chatOpen ? 'open' : '';
    if (_chatOpen) {
        setTimeout(function(){ document.getElementById('chatInput').focus(); }, 350);
    }
}

function addMsg(role, html) {
    var el = document.createElement('div');
    el.className = 'chat-msg ' + role;
    el.innerHTML = html;
    el.id = 'chatMsg_' + (++_chatMsgId);
    document.getElementById('chatMsgs').appendChild(el);
    el.scrollIntoView({behavior:'smooth',block:'end'});
    return el;
}

function addLoading() {
    var el = document.createElement('div');
    el.className = 'chat-msg assistant';
    el.id = 'chatLoading';
    el.innerHTML = '<div class="chat-loading"><span></span><span></span><span></span></div>';
    document.getElementById('chatMsgs').appendChild(el);
    el.scrollIntoView({behavior:'smooth',block:'end'});
}

function removeLoading() {
    var el = document.getElementById('chatLoading');
    if (el) el.remove();
}

// 简易 Markdown 渲染
function renderMd(text) {
    if (!text) return '';
    // 转义 HTML
    text = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    // 过滤垃圾
    text = text.replace(/\[object Object\]/g,'').replace(/```tool_calls?\n[\s\S]*?```/g,'');
    // 代码块（必须在其他标记之前）
    text = text.replace(/```(\w*)\n([\s\S]*?)```/g, function(_, lang, code) {
        var langCls = lang ? ' class="lang-'+lang+'"' : '';
        return '<pre><button class="copy-btn" onclick="(function(b){var t=b.nextElementSibling||b.parentNode.querySelector(\'code\');navigator.clipboard.writeText(t.textContent).then(function(){b.textContent=\'已复制\';setTimeout(function(){b.textContent=\'复制\'},1500)})})(this)">复制</button><code'+langCls+'>'+code.trim()+'</code></pre>';
    });
    // 行内代码
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
    // 表格
    text = text.replace(/^\|(.+)\|$/gm, function(m, row) {
        var cells = row.split('|');
        var isHeader = /^[\s:-]+$/.test(cells[1] && cells[1].trim());
        if (isHeader) return '';
        var tag = 'td';
        return '<tr>' + cells.map(function(c){return '<'+tag+'>'+c.trim()+'</'+tag+'>';}).join('') + '</tr>';
    });
    // 标题
    text = text.replace(/^### (.+)$/gm, '<h4 style="margin:8px 0 4px;font-size:14px;font-weight:600">$1</h4>');
    text = text.replace(/^## (.+)$/gm, '<h4 style="margin:8px 0 4px;font-size:14px;font-weight:600">$1</h4>');
    text = text.replace(/^# (.+)$/gm, '<h4 style="margin:8px 0 4px;font-size:14px;font-weight:600">$1</h4>');
    // 粗体 + 斜体
    text = text.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // 链接
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:#3b82f6;text-decoration:underline">$1</a>');
    // 分割线
    text = text.replace(/^---$/gm, '<hr>');
    // 引用
    text = text.replace(/^>\s?(.+)$/gm, '<blockquote>$1</blockquote>');
    // 无序列表
    text = text.replace(/^[-*]\s(.+)$/gm, '<li>$1</li>');
    text = text.replace(/(<li>.*<\/li>\n?)/g, '<ul>$1</ul>');
    // 合并相邻 ul
    text = text.replace(/<\/ul>\n?<ul>/g, '');
    // 段落（剩余文本换行转段落）
    var lines = text.split('\n');
    var result = [];
    var inTable = false;
    for (var i=0; i<lines.length; i++) {
        var line = lines[i].trim();
        if (!line) { if (!inTable) result.push(''); continue; }
        if (line.startsWith('<pre') || line.startsWith('<h4') || line.startsWith('<blockquote') || line.startsWith('<hr') || line.startsWith('<ul') || line.startsWith('<tr')) {
            inTable = line.startsWith('<tr');
            result.push(line);
        } else if (line.startsWith('</')) {
            result.push(line);
            inTable = false;
        } else {
            result.push(line);
        }
    }
    var html = result.join('\n');
    // 表格包裹（首行→thead，其余→tbody）
    html = html.replace(/((?:<tr>[\s\S]*?<\/tr>\n?)+)/g, function(m) {
        var rows = m.match(/<tr>[\s\S]*?<\/tr>/g) || [];
        if (rows.length===0) return m;
        var thead = rows[0].replace(/<td>/g,'<th>').replace(/<\/td>/g,'</th>');
        var tbody = rows.slice(1).join('\n');
        return '<table><thead>'+thead+'</thead><tbody>'+tbody+'</tbody></table>';
    });
    // 剩余文本段落化
    html = html.replace(/^(?!<[hupbcht]|<\/)(.+)$/gm, '<p>$1</p>');
    // 清理空段落
    html = html.replace(/<p>\s*<\/p>/g, '');
    return html;
}

function sendMsg() {
    if (_chatLoading) return;
    var input = document.getElementById('chatInput');
    var text = input.value.trim();
    if (!text) return;
    input.value = '';
    document.getElementById('chatSendBtn').disabled = true;
    addMsg('user', '<p>'+text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')+'</p>');

    // 移除欢迎语里的快捷标签
    var firstMsg = document.querySelector('#chatMsgs .chat-msg.assistant:first-child .chat-tag');
    if (firstMsg) {
        var tags = document.querySelectorAll('#chatMsgs .chat-msg.assistant:first-child .chat-tag');
        tags.forEach(function(t){t.parentNode.removeChild(t)});
    }

    addLoading();
    _chatLoading = true;

    fetch('/api/chat/message', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({message:text, session_id:'widget'})
    }).then(function(r) {
        if (!r.ok) throw new Error('请求失败');
        return r.json();
    }).then(function(data) {
        removeLoading();
        addMsg('assistant', renderMd(data.reply || ''));
    }).catch(function(e) {
        removeLoading();
        addMsg('assistant', '<p style="color:#dc2626">❌ 请求失败: '+e.message+'</p>');
    }).finally(function() {
        _chatLoading = false;
        document.getElementById('chatSendBtn').disabled = false;
        document.getElementById('chatInput').focus();
    });
}

function quickAsk(text) {
    document.getElementById('chatInput').value = text;
    sendMsg();
}
