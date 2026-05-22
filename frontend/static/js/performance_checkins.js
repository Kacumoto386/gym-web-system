// 联动时间筛选
document.getElementById('periodSelect')?.addEventListener('change', function() {
    const period = this.value;
    htmx.ajax('GET', `/api/performance/checkins/stats?period=${period}`, {target: '#statsCards'});
    htmx.ajax('GET', `/api/performance/checkins/by-type?period=${period}`, {target: '#byType'});
    htmx.ajax('GET', `/api/performance/checkins/by-hour?period=${period}`, {target: '#byHour'});
    htmx.ajax('GET', `/api/performance/checkins/table?period=${period}`, {target: '#checkinTable'});
});
