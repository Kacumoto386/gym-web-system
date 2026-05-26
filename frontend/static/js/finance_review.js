// ── 支出审核 ──
var _currentStatus = '待审核';
var _currentPage = 1;
var _rejectId = null;

function switchFilter(status) {
    _currentStatus = status;
    _currentPage = 1;
    // 按钮样式
    document.querySelectorAll('[id^="filter"]').forEach(function(b) {
        b.className = b.className.replace('bg-blue-600 text-white', '');
    });
    var map = {'': 'filterAll', '待审核': 'filterPending', '已通过': 'filterApproved', '已驳回': 'filterRejected'};
    var active = document.getElementById(map[status]);
    if (active) active.className = active.className + ' bg-blue-600 text-white';
    loadTable();
}

function doSearch() {
    _currentPage = 1;
    loadTable();
}

function loadTable() {
    var q = document.getElementById('searchInput').value.trim();
    fetch('/api/finance-review/table?status=' + encodeURIComponent(_currentStatus) + '&page=' + _currentPage + '&q=' + encodeURIComponent(q))
        .then(function(r) { return r.text(); })
        .then(function(html) {
            document.getElementById('reviewTable').innerHTML = html;
        });
    // 刷新统计
    fetch('/api/finance-review/stats')
        .then(function(r) { return r.text(); })
        .then(function(html) {
            document.getElementById('reviewStats').innerHTML = html;
        });
}

function goPage(p) {
    _currentPage = p;
    loadTable();
}

function approveExpense(id) {
    if (!confirm('确认通过此支出记录？')) return;
    fetch('/api/finance-review/' + id + '/approve', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
    }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.success) loadTable();
    });
}

function rejectExpense(id) {
    _rejectId = id;
    document.getElementById('rejectReason').value = '';
    document.getElementById('rejectModal').classList.remove('hidden');
}

function closeRejectModal() {
    document.getElementById('rejectModal').classList.add('hidden');
    _rejectId = null;
}

function confirmReject() {
    if (!_rejectId) return;
    var reason = document.getElementById('rejectReason').value.trim() || '未填写原因';
    fetch('/api/finance-review/' + _rejectId + '/reject', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({reason: reason}),
    }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.success) {
            closeRejectModal();
            loadTable();
        }
    });
}
