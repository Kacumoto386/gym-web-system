function doSearch() {
    var type = document.getElementById('typeFilter').value;
    var tab = document.getElementById('tabFilter').value;
    var q = document.getElementById('searchInput').value;
    var renewable = document.getElementById('renewableOnly').checked;
    var url = '/api/alerts/table?tab=' + encodeURIComponent(tab) + '&alert_type=' + encodeURIComponent(type) + '&q=' + encodeURIComponent(q) + '&renewable_only=' + (renewable ? '1' : '0');
    htmx.ajax('GET', url, {target: '#alertContent', swap: 'innerHTML'});
}

function resetFilters() {
    document.getElementById('typeFilter').value = '';
    document.getElementById('tabFilter').value = 'all';
    document.getElementById('searchInput').value = '';
    document.getElementById('renewableOnly').checked = false;
    htmx.ajax('GET', '/api/alerts/table', {target: '#alertContent', swap: 'innerHTML'});
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && document.activeElement === document.getElementById('searchInput')) {
        doSearch();
    }
});
