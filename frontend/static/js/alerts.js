function doSearch() {
    var type = document.getElementById('typeFilter').value;
    var tab = document.getElementById('tabFilter').value;
    var q = document.getElementById('searchInput').value;
    var url = '/api/alerts/table?tab=' + encodeURIComponent(tab) + '&alert_type=' + encodeURIComponent(type) + '&q=' + encodeURIComponent(q);
    htmx.ajax('GET', url, {target: '#alertContent', swap: 'innerHTML'});
}

function resetFilters() {
    document.getElementById('typeFilter').value = '';
    document.getElementById('tabFilter').value = 'all';
    document.getElementById('searchInput').value = '';
    htmx.ajax('GET', '/api/alerts/table', {target: '#alertContent', swap: 'innerHTML'});
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && document.activeElement === document.getElementById('searchInput')) {
        doSearch();
    }
});
