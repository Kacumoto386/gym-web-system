function refreshAll() {
    const period = document.getElementById('periodSelect').value;
    htmx.ajax('GET', `/api/performance/sales/stats?period=${period}`, {target: '#statsCards'});
    htmx.ajax('GET', `/api/performance/sales/by-course?period=${period}`, {target: '#byCourse'});
    htmx.ajax('GET', `/api/performance/sales/trend?period=${period}`, {target: '#trendChart'});
    htmx.ajax('GET', `/api/performance/sales/by-staff?period=${period}`, {target: '#byStaff'});
    htmx.ajax('GET', `/api/performance/sales/payment-breakdown?period=${period}`, {target: '#paymentBreakdown'});
    htmx.ajax('GET', `/api/performance/sales/detail-table?period=${period}&status=all`, {target: '#saleTable'});
}

document.getElementById('periodSelect').addEventListener('change', refreshAll);

document.addEventListener('click', function(e) {
    const btn = e.target.closest('.status-filter');
    if (!btn) return;
    document.querySelectorAll('.status-filter').forEach(b => {
        const isActive = b.dataset.status === btn.dataset.status;
        b.className = isActive
            ? 'status-filter px-3 py-1.5 text-sm rounded-lg bg-blue-600 text-white'
            : 'status-filter px-3 py-1.5 text-sm rounded-lg bg-gray-200 text-gray-600 hover:bg-gray-300';
    });
    const period = document.getElementById('periodSelect')?.value || '本月';
    htmx.ajax('GET', `/api/performance/sales/detail-table?period=${period}&status=${btn.dataset.status}`, {target: '#saleTable'});
});
