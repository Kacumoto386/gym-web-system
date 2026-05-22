async function testTool(name) {
    const input = document.getElementById(`test-input-${name}`);
    const result = document.getElementById(`test-result-${name}`);
    let params = {};
    try {
        if (input.value.trim()) {
            params = JSON.parse(input.value);
        }
    } catch(e) {
        result.textContent = `❌ JSON 解析错误: ${e.message}`;
        result.classList.remove('hidden');
        return;
    }

    result.classList.remove('hidden');
    result.textContent = '⏳ 执行中...';

    try {
        const resp = await fetch('/api/mcp/call-tool', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, arguments: params}),
        });
        const data = await resp.json();
        result.textContent = JSON.stringify(data, null, 2);
    } catch(e) {
        result.textContent = `❌ 请求失败: ${e.message}`;
    }
}

async function mcpPing() {
    const el = document.getElementById('mcp-test-result');
    try {
        const resp = await fetch('/api/mcp/ping');
        const data = await resp.json();
        el.textContent = JSON.stringify(data, null, 2);
    } catch(e) {
        el.textContent = `❌ 失败: ${e.message}`;
    }
}

async function mcpListTools() {
    const el = document.getElementById('mcp-test-result');
    try {
        const resp = await fetch('/api/mcp/tools');
        const data = await resp.json();
        el.textContent = JSON.stringify(data, null, 2);
    } catch(e) {
        el.textContent = `❌ 失败: ${e.message}`;
    }
}

async function mcpListResources() {
    const el = document.getElementById('mcp-test-result');
    try {
        const resp = await fetch('/api/mcp/resources');
        const data = await resp.json();
        el.textContent = JSON.stringify(data, null, 2);
    } catch(e) {
        el.textContent = `❌ 失败: ${e.message}`;
    }
}

async function mcpServerInfo() {
    const el = document.getElementById('mcp-test-result');
    try {
        const resp = await fetch('/api/mcp/server-info');
        const data = await resp.json();
        el.textContent = JSON.stringify(data, null, 2);
    } catch(e) {
        el.textContent = `❌ 失败: ${e.message}`;
    }
}
