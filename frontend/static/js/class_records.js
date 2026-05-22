let currentEvalRecordId = null;
let currentEditRecordId = null;

// ═══════════════════════════════════════════
// 加载教练下拉选项
// ═══════════════════════════════════════════
document.addEventListener('DOMContentLoaded', function() {
    // Load coach options from existing records
    fetch('/api/class-records/table?limit=500')
        .then(r => r.text())
        .then(html => {
            // Extract unique coach names from table rows
            const coaches = new Set();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            doc.querySelectorAll('tbody tr:nth-child(odd)').forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 4) {
                    const coach = cells[3].textContent.trim();
                    if (coach && coach !== '-') coaches.add(coach);
                }
            });
            const sel = document.getElementById('coachFilter');
            coaches.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c;
                opt.textContent = c;
                sel.appendChild(opt);
            });
        });
});

// ═══════════════════════════════════════════
// 快速日期
// ═══════════════════════════════════════════
function setQuickDate(range) {
    const dtInput = document.getElementById('dateFilter');
    if (range === 'all') {
        dtInput.value = '';
        doSearch();
        return;
    }
    const now = new Date();
    if (range === 'today') {
        dtInput.value = now.toISOString().slice(0, 10);
    } else if (range === 'week') {
        // Get Monday of this week
        const monday = new Date(now);
        monday.setDate(now.getDate() - (now.getDay() || 7) + 1);
        // Just set to today for simplicity (backend filters single date)
        dtInput.value = now.toISOString().slice(0, 10);
    } else if (range === 'month') {
        dtInput.value = now.toISOString().slice(0, 10);
    }
    doSearch();
}

// ═══════════════════════════════════════════
// 搜索 + 重置
// ═══════════════════════════════════════════
function doSearch() {
    const kw = document.getElementById('keywordInput').value;
    const dt = document.getElementById('dateFilter').value;
    const st = document.getElementById('statusFilter').value;
    const coach = document.getElementById('coachFilter').value;

    let url = '/api/class-records/table?';
    const params = [];
    if (kw) params.push('keyword=' + encodeURIComponent(kw));
    if (dt) params.push('class_date=' + encodeURIComponent(dt));
    if (st) params.push('status=' + encodeURIComponent(st));
    if (coach) params.push('coach=' + encodeURIComponent(coach));

    htmx.ajax('GET', url + params.join('&'), { target: '#classRecordTable' });
}

function resetFilters() {
    document.getElementById('keywordInput').value = '';
    document.getElementById('dateFilter').value = '';
    document.getElementById('statusFilter').value = '';
    document.getElementById('coachFilter').value = '';
    refreshAll();
}

// ═══════════════════════════════════════════
// Enter 触发搜索
// ═══════════════════════════════════════════
document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && e.target.id === 'keywordInput') {
        doSearch();
    }
});

// ═══════════════════════════════════════════
// 行展开详情
// ═══════════════════════════════════════════
function toggleDetail(recordId) {
    const el = document.getElementById('detail-' + recordId);
    if (el) el.classList.toggle('hidden');
}

// ═══════════════════════════════════════════
// 编辑课程记录
// ═══════════════════════════════════════════
function openEditRecord(recordId) {
    currentEditRecordId = recordId;
    fetch('/api/class-records/' + recordId)
        .then(r => r.json())
        .then(d => {
            document.getElementById('edit_member_id').value = d.member_id || '';
            document.getElementById('edit_member_name').value = d.member_name || '';
            document.getElementById('edit_member_phone').value = d.member_phone || '';
            document.getElementById('edit_course_name').value = d.course_name || '';
            document.getElementById('edit_coach_name').value = d.coach_name || '';
            document.getElementById('edit_class_date').value = d.class_date || '';
            document.getElementById('edit_start_time').value = d.start_time || '';
            document.getElementById('edit_end_time').value = d.end_time || '';
            document.getElementById('edit_consumed_hours').value = d.consumed_hours || 1;
            document.getElementById('edit_status').value = d.status || '已完成';
            document.getElementById('edit_evaluation').value = d.evaluation || '';
            document.getElementById('edit_feedback').value = d.feedback || '';
            document.getElementById('edit_notes').value = d.notes || '';
            document.getElementById('editModal').classList.remove('hidden');
        });
}

function validateEditTime() {
    var start = document.getElementById('edit_start_time').value;
    var end = document.getElementById('edit_end_time').value;
    var err = document.getElementById('edit_time_error');
    if (start && end && end <= start) {
        err.classList.remove('hidden');
        return false;
    }
    err.classList.add('hidden');
    return true;
}

function submitEditRecord() {
    if (!currentEditRecordId) return;
    if (!validateEditTime()) return;
    var data = {
        member_id: document.getElementById('edit_member_id').value,
        member_name: document.getElementById('edit_member_name').value,
        member_phone: document.getElementById('edit_member_phone').value,
        course_name: document.getElementById('edit_course_name').value,
        coach_name: document.getElementById('edit_coach_name').value,
        class_date: document.getElementById('edit_class_date').value,
        start_time: document.getElementById('edit_start_time').value,
        end_time: document.getElementById('edit_end_time').value,
        consumed_hours: parseInt(document.getElementById('edit_consumed_hours').value) || 1,
        status: document.getElementById('edit_status').value,
        evaluation: document.getElementById('edit_evaluation').value,
        feedback: document.getElementById('edit_feedback').value,
        notes: document.getElementById('edit_notes').value,
    };
    fetch('/api/class-records/' + currentEditRecordId, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(function(r) {
        if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || '保存失败: ' + r.status); });
        return r.json();
    })
    .then(function() {
        document.getElementById('editModal').classList.add('hidden');
        refreshAll();
    })
    .catch(function(err) {
        alert(err.message);
    });
}

// ═══════════════════════════════════════════
// 评价弹窗
// ═══════════════════════════════════════════
function openEval(recordId, currentEval, currentFeedback) {
    currentEvalRecordId = recordId;
    document.getElementById('eval_value').value = currentEval || '好评';
    document.getElementById('eval_feedback').value = currentFeedback || '';
    document.getElementById('evalModal').classList.remove('hidden');
}

document.getElementById('evalSubmitBtn')?.addEventListener('click', function() {
    if (!currentEvalRecordId) return;
    const val = document.getElementById('eval_value').value;
    const fb = document.getElementById('eval_feedback').value;
    fetch('/api/class-records/' + currentEvalRecordId + '/evaluation', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ evaluation: val, feedback: fb })
    })
    .then(r => r.json())
    .then(data => {
        document.getElementById('evalModal').classList.add('hidden');
        refreshAll();
    });
});

// ═══════════════════════════════════════════
// 刷新
// ═══════════════════════════════════════════
function refreshAll() {
    fetch('/api/class-records/cards')
        .then(r => r.text())
        .then(html => document.getElementById('cardArea').innerHTML = html);
    fetch('/api/class-records/table')
        .then(r => r.text())
        .then(html => document.getElementById('classRecordTable').innerHTML = html);
}
