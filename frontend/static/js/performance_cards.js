function refreshAll() {
    const period = document.getElementById('periodSelect').value;
    const category = document.getElementById('categoryFilter').value;
    const hideZero = document.getElementById('hideZeroToggle').checked;

    htmx.ajax('GET', `/api/performance/cards/stats?period=${period}`, {target: '#statsCards'});
    htmx.ajax('GET', `/api/performance/cards/by-type?period=${period}&category=${category}`, {target: '#byType'});
    htmx.ajax('GET', `/api/performance/cards/trend?period=${period}`, {target: '#trendChart'});

    let tableUrl = `/api/performance/cards/detail-table?period=${period}&category=${category}`;
    if (hideZero) tableUrl += '&hide_zero=1';
    htmx.ajax('GET', tableUrl, {target: '#cardTable'});
}

document.getElementById('periodSelect').addEventListener('change', refreshAll);
document.getElementById('categoryFilter').addEventListener('change', refreshAll);
document.getElementById('hideZeroToggle').addEventListener('change', refreshAll);
