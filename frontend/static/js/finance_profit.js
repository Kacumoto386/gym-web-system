// ── 利润表 ──
(function() {
    var m = document.getElementById('profitMonth');
    var d = new Date();
    m.value = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
})();

function loadProfit() {
    var monthVal = document.getElementById('profitMonth').value;
    if (!monthVal) return;
    var parts = monthVal.split('-');
    var y = parts[0], m = parts[1];

    var sections = [
        'profitSummary', 'revenueBreakdown', 'expenseBreakdown',
        'momComparison', 'yoyComparison'
    ];
    var endpoints = [
        '/api/finance-profit/summary?year=' + y + '&month=' + m,
        '/api/finance-profit/revenue-breakdown?year=' + y + '&month=' + m,
        '/api/finance-profit/expense-breakdown?year=' + y + '&month=' + m,
        '/api/finance-profit/mom-comparison?year=' + y + '&month=' + m,
        '/api/finance-profit/yoy-comparison?year=' + y + '&month=' + m,
    ];

    sections.forEach(function(id, i) {
        fetch(endpoints[i])
            .then(function(r) { return r.text(); })
            .then(function(html) { document.getElementById(id).innerHTML = html; });
    });
}

function exportProfit() {
    var monthVal = document.getElementById('profitMonth').value;
    if (!monthVal) return;
    var parts = monthVal.split('-');
    window.open('/api/finance-profit/export?year=' + parts[0] + '&month=' + parts[1], '_blank');
}
