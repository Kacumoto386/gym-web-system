// ── 仪表盘趋势图 ──
var registerChartInstance = null;
var revenueChartInstance = null;
var trendDataCache = {};

function switchTrendTab(tab) {
    // 切换 tab 按钮样式
    ['checkin', 'register', 'revenue'].forEach(function(t) {
        var btn = document.getElementById('trendTab' + t.charAt(0).toUpperCase() + t.slice(1));
        var content = document.getElementById('trendChart' + t.charAt(0).toUpperCase() + t.slice(1));
        if (t === tab) {
            btn.className = 'px-2.5 py-1 rounded bg-blue-600 text-white';
            content.style.display = '';
        } else {
            btn.className = 'px-2.5 py-1 rounded text-gray-500 hover:bg-gray-100';
            content.style.display = 'none';
        }
    });

    // 注册趋势：懒加载 Chart.js
    if (tab === 'register') {
        if (!trendDataCache.register) {
            fetch('/api/dashboard/registration-trend')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    trendDataCache.register = data;
                    renderRegisterChart(data);
                })
                .catch(function() {});
        } else {
            renderRegisterChart(trendDataCache.register);
        }
    }

    // 月营收趋势
    if (tab === 'revenue') {
        if (!trendDataCache.revenue) {
            fetch('/api/dashboard/monthly-revenue')
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    trendDataCache.revenue = data;
                    renderRevenueChart(data);
                })
                .catch(function() {});
        } else {
            renderRevenueChart(trendDataCache.revenue);
        }
    }
}

function renderRegisterChart(data) {
    if (registerChartInstance) registerChartInstance.destroy();
    var canvas = document.getElementById('registerTrendChart');
    if (!canvas || !data.labels || data.labels.length === 0) return;

    registerChartInstance = new Chart(canvas, {
        type: 'line',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { font: { size: 9 }, maxTicksLimit: 15 } },
                y: { beginAtZero: true, ticks: { font: { size: 9 }, stepSize: 1 } }
            }
        }
    });
}

function renderRevenueChart(data) {
    if (revenueChartInstance) revenueChartInstance.destroy();
    var canvas = document.getElementById('revenueTrendChart');
    if (!canvas || !data.labels || data.labels.length === 0) return;

    revenueChartInstance = new Chart(canvas, {
        type: 'bar',
        data: data,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { font: { size: 9 } } },
                y: { beginAtZero: true, ticks: { font: { size: 9 }, callback: function(v) { return '¥' + v.toLocaleString(); } } }
            }
        }
    });
}
