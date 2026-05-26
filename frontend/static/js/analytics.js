// ── 数据分析看板 ──
var _currentMonths = 12;
var _charts = {};

// 8 个图表端点
var _endpoints = [
    {id: 'revenueTrendChart', url: '/api/analytics/revenue-trend', type: 'line'},
    {id: 'revenueCompositionChart', url: '/api/analytics/revenue-composition', type: 'doughnut'},
    {id: 'expenseTrendChart', url: '/api/analytics/expense-trend', type: 'line'},
    {id: 'incomeVsExpenseChart', url: '/api/analytics/income-vs-expense', type: 'bar'},
    {id: 'memberGrowthChart', url: '/api/analytics/member-growth', type: 'bar'},
    {id: 'peakHoursChart', url: '/api/analytics/peak-hours', type: 'bar'},
    {id: 'topCoursesChart', url: '/api/analytics/top-courses', type: 'horizontalBar'},
    {id: 'paymentMethodsChart', url: '/api/analytics/payment-methods', type: 'doughnut'},
];

function switchRange(months) {
    _currentMonths = months;
    document.querySelectorAll('[id^="range"]').forEach(function(b) {
        b.className = 'px-3 py-1.5 rounded text-sm bg-gray-200 text-gray-600 hover:bg-gray-300';
    });
    document.getElementById('range' + months + 'm').className = 'px-3 py-1.5 rounded text-sm font-medium bg-blue-600 text-white';
    loadAllCharts();
}

function destroyAll() {
    Object.keys(_charts).forEach(function(id) {
        if (_charts[id]) { _charts[id].destroy(); _charts[id] = null; }
    });
}

function renderChart(canvasId, data, type) {
    var canvas = document.getElementById(canvasId);
    if (!canvas || !data || !data.labels) return;
    var ctx = canvas.getContext('2d');

    var isHorizontal = type === 'horizontalBar';
    var isDoughnut = type === 'doughnut';
    var isBar = type === 'bar' || isHorizontal;
    var isLine = type === 'line';

    var chartType = isHorizontal ? 'bar' : (isDoughnut ? 'doughnut' : type);

    var options = {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: isHorizontal ? 'y' : 'x',
        plugins: {
            legend: { display: isDoughnut, position: 'bottom', labels: { boxWidth: 12, padding: 8, font: { size: 10 } } },
        },
        scales: isDoughnut ? {} : {
            x: { ticks: { font: { size: 9 }, maxRotation: 45 } },
            y: { beginAtZero: true, ticks: { font: { size: 9 } } }
        },
    };

    _charts[canvasId] = new Chart(ctx, {
        type: chartType,
        data: data,
        options: options,
    });
}

function loadAllCharts() {
    destroyAll();

    // 月份相关端点需要 months 参数
    var monthEndpoints = ['revenue-trend', 'expense-trend', 'income-vs-expense', 'member-growth'];

    var promises = _endpoints.map(function(ep) {
        var url = ep.url;
        if (_currentMonths && monthEndpoints.some(function(p) { return url.indexOf(p) >= 0; })) {
            url += '?months=' + _currentMonths;
        }
        return fetch(url).then(function(r) { return r.json(); }).then(function(data) {
            if (data && data.labels) renderChart(ep.id, data, ep.type);
        }).catch(function(e) {
            console.warn('Chart load error for ' + ep.id + ':', e);
        });
    });

    Promise.all(promises);
}

// 页面加载完成后渲染
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadAllCharts);
} else {
    loadAllCharts();
}
