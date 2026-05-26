/* ============================================
   健身管理系统 — 公共 JS
   ============================================ */

// ── 侧边栏分组折叠 ──

const GROUP_NAMES = window._GROUP_NAMES || ['members', 'courses', 'checkin', 'staff', 'finance', 'system'];
const STORAGE_PREFIX = 'sidebar_';

function toggleGroup(name) {
    const el = document.getElementById('group-' + name);
    const arrow = document.getElementById('arrow-' + name);
    if (!el || !arrow) return;
    const isOpen = el.style.display !== 'none';
    el.style.display = isOpen ? 'none' : '';
    arrow.textContent = isOpen ? '▶' : '▼';
    try { localStorage.setItem(STORAGE_PREFIX + name, isOpen ? '0' : '1'); } catch (e) {}
}

function restoreGroups() {
    const curPath = window.location.pathname;

    GROUP_NAMES.forEach(function(name) {
        const el = document.getElementById('group-' + name);
        const arrow = document.getElementById('arrow-' + name);
        if (!el || !arrow) return;

        const links = el.querySelectorAll('a');
        let isActive = false;
        links.forEach(function(a) {
            const href = a.getAttribute('href');
            if (href && curPath.startsWith(href.split('?')[0])) {
                isActive = true;
            }
        });

        let shouldOpen = true;
        try {
            const saved = localStorage.getItem(STORAGE_PREFIX + name);
            if (saved !== null) {
                shouldOpen = saved === '1';
            } else {
                shouldOpen = isActive;
            }
        } catch (e) {
            shouldOpen = isActive;
        }

        el.style.display = shouldOpen ? '' : 'none';
        arrow.textContent = shouldOpen ? '▼' : '▶';
    });
}

// ── 系统名称加载 ──

function loadSystemName() {
    fetch('/api/system/settings')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var el = document.getElementById('sidebarTitle');
            if (el && data.system_name) {
                el.innerHTML = '🏋️ ' + data.system_name;
            }
        })
        .catch(function() {});
}

// ── HTMX 配置 ──

document.body.addEventListener('htmx:beforeSwap', function(evt) {
    if (evt.detail.xhr.status >= 400) {
        evt.detail.shouldSwap = false;
    }
});

// ── 移动端侧边栏切换 ──

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
    document.getElementById('sidebarOverlay').classList.toggle('open');
}

function closeSidebar() {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebarOverlay').classList.remove('open');
}

// ── DOM 就绪 ──

document.addEventListener('DOMContentLoaded', function() {
    loadSystemName();
    restoreGroups();
});

// ── 作废弹窗 ──

let _voidData = {};

function openVoidModal(recordId, apiPath) {
    _voidData = { id: recordId, api: apiPath };
    document.getElementById('voidReasonInput').value = '';
    document.getElementById('voidError').classList.add('hidden');
    document.getElementById('voidModal').classList.remove('hidden');
}

function closeVoidModal() {
    document.getElementById('voidModal').classList.add('hidden');
}

function confirmVoid() {
    var reason = document.getElementById('voidReasonInput').value.trim();
    if (!reason) {
        document.getElementById('voidError').classList.remove('hidden');
        return;
    }
    document.getElementById('voidError').classList.add('hidden');
    var apiPath = _voidData.api;
    fetch(apiPath, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({reason: reason})
    }).then(function(r) {
        if (!r.ok) { throw new Error('操作失败'); }
        return r.json();
    }).then(function() {
        closeVoidModal();
        location.reload();
    }).catch(function(e) {
        alert('作废失败: ' + e.message);
    });
}
