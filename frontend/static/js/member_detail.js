var tabLoaded = { cards: true, checkins: false, classes: false, body: false, purchases: false };
var tabIds = ['Cards', 'Checkins', 'Classes', 'Body', 'Purchases'];
var tabEndpoints = {
    Cards: '/api/members/' + window._pageData.memberId + '/cards-html',
    Checkins: '/api/members/' + window._pageData.memberId + '/checkins-html',
    Classes: '/api/members/' + window._pageData.memberId + '/class-records-html',
    Body: '/api/members/' + window._pageData.memberId + '/body-measurements-html',
    Purchases: '/api/members/' + window._pageData.memberId + '/purchases-html',
};
var bodyChartInstance = null;

function switchTab(tab) {
    tabIds.forEach(function(t) {
        var btn = document.getElementById('tab' + t);
        var content = document.getElementById('tab' + t + 'Content');
        var isActive = (t.toLowerCase() === tab);
        content.style.display = isActive ? '' : 'none';
        if (isActive) {
            btn.classList.remove('text-gray-500', 'border-transparent');
            btn.classList.add('text-blue-600', 'border-blue-600');
        } else {
            btn.classList.remove('text-blue-600', 'border-blue-600');
            btn.classList.add('text-gray-500', 'border-transparent');
        }
        // 懒加载
        if (isActive && !tabLoaded[tab]) {
            var url = tabEndpoints[t];
            if (t === 'Body') {
                // Body tab 使用自定义加载（含图表）
                loadBodyTab();
            } else {
                htmx.ajax('GET', url, {target: '#tab' + t + 'Content', swap: 'innerHTML'});
            }
            tabLoaded[tab] = true;
        }
    });
}

function loadBodyTab() {
    var contentEl = document.getElementById('tabBodyContent');

    // 加载体测趋势图
    var canvas = document.getElementById('bodyTrendChart');
    if (canvas && typeof Chart !== 'undefined') {
        fetch('/api/members/' + window._pageData.memberId + '/body-trend')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.labels && data.labels.length > 0) {
                    if (bodyChartInstance) bodyChartInstance.destroy();
                    bodyChartInstance = new Chart(canvas, {
                        type: 'line',
                        data: data,
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: { legend: { position: 'top', labels: { boxWidth: 12, padding: 8, font: { size: 10 } } } },
                            scales: {
                                x: { ticks: { font: { size: 10 } } },
                                y: { beginAtZero: false, ticks: { font: { size: 10 } } }
                            }
                        }
                    });
                } else {
                    canvas.style.display = 'none';
                }
            })
            .catch(function() { canvas.style.display = 'none'; });
    }

    // 加载体测记录表格
    htmx.ajax('GET', tabEndpoints.Body, {target: '#tabBodyInner', swap: 'outerHTML'});
}

// 从列表页跳转过来时自动打开编辑弹窗
document.addEventListener('DOMContentLoaded', function() {
    var editId = sessionStorage.getItem('editMember');
    if (editId === window._pageData.memberId) {
        sessionStorage.removeItem('editMember');
        window.location.href = '/members?edit=' + editId;
    }
});
