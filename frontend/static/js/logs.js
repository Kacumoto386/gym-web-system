// ═══════════════════════════════════════
// 页面加载
// ═══════════════════════════════════════
document.addEventListener('DOMContentLoaded', function() {
    // 读取系统名称填入输入框
    fetch('/api/system/settings')
        .then(r => r.json())
        .then(data => {
            if (data.system_name) {
                document.getElementById('systemNameInput').value = data.system_name;
            }
        })
        .catch(() => {});
    // 首次加载日志
    refreshLogs();
});

// ═══════════════════════════════════════
// 保存系统名称
// ═══════════════════════════════════════
function saveSystemName() {
    const name = document.getElementById('systemNameInput').value.trim();
    const statusEl = document.getElementById('saveStatus');

    if (!name) {
        statusEl.innerHTML = '<span class="text-red-500">名称不能为空</span>';
        return;
    }

    fetch('/api/system/settings', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name})
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            statusEl.innerHTML = '<span class="text-green-500">✅ 已保存</span>';
            setTimeout(() => statusEl.innerHTML = '', 3000);
            refreshLogs();
        } else {
            statusEl.innerHTML = '<span class="text-red-500">保存失败</span>';
        }
    })
    .catch(() => {
        statusEl.innerHTML = '<span class="text-red-500">请求失败</span>';
    });
}

// ═══════════════════════════════════════
// 刷新日志列表
// 使用 fetch() 替代 htmx.ajax() 以避免 HTMX 缓存问题
// ═══════════════════════════════════════
function refreshLogs() {
    const action = document.getElementById('actionFilter').value;
    const resource = document.getElementById('resourceFilter').value;
    let url = '/api/logs/table';
    const params = [];
    if (action) params.push('action=' + encodeURIComponent(action));
    if (resource) params.push('resource=' + encodeURIComponent(resource));
    if (params.length) url += '?' + params.join('&');

    // 显示加载中
    document.getElementById('logTable').innerHTML = '<div class="text-center py-8 text-gray-400">加载中...</div>';

    fetch(url)
        .then(r => {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.text();
        })
        .then(html => {
            document.getElementById('logTable').innerHTML = html;
        })
        .catch(() => {
            document.getElementById('logTable').innerHTML = '<div class="text-center py-8 text-red-400">加载失败，请重试</div>';
        });
}
