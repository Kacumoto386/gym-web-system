// ═══════════════════════════════════════════
// 编辑课程
// ═══════════════════════════════════════════
function openEditCourse(courseId) {
    fetch('/api/courses/' + courseId)
        .then(r => r.json())
        .then(data => {
            document.getElementById('edit_name').value = data.name || '';
            document.getElementById('edit_course_type').value = data.course_type || '私教课';
            document.getElementById('edit_sport_type').value = data.sport_type || '';
            document.getElementById('edit_standard_hours').value = data.standard_hours || 1;
            document.getElementById('edit_standard_price').value = data.standard_price || 0;
            document.getElementById('edit_discount_price').value = data.discount_price || 0;
            document.getElementById('edit_valid_days').value = data.valid_days || 0;
            document.getElementById('edit_max_bookings').value = data.max_bookings || 0;
            document.getElementById('edit_coach').value = data.coach || '';
            document.getElementById('edit_location').value = data.location || '';
            document.getElementById('edit_description').value = data.description || '';
            document.getElementById('edit_remark').value = data.remark || '';
            document.getElementById('editForm').setAttribute('hx-put', '/api/courses/' + courseId);
            document.getElementById('editModal').classList.remove('hidden');
        });
}

// ═══════════════════════════════════════════
// 上架/下架切换
// ═══════════════════════════════════════════
function toggleStatus(courseId) {
    fetch('/api/courses/' + courseId + '/toggle-status', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            refreshAll();
        });
}

// ═══════════════════════════════════════════
// 批量操作
// ═══════════════════════════════════════════
function toggleSelectAll(el) {
    document.querySelectorAll('.batch-check').forEach(cb => cb.checked = el.checked);
    updateBatchButtons();
}

function updateBatchButtons() {
    const checked = document.querySelectorAll('.batch-check:checked');
    const count = checked.length;
    const ids = Array.from(checked).map(cb => cb.value);

    document.getElementById('batchOnlineBtn').classList.toggle('hidden', count === 0);
    document.getElementById('batchOfflineBtn').classList.toggle('hidden', count === 0);
    document.getElementById('batchDeleteBtn').classList.toggle('hidden', count === 0);
    document.getElementById('batchCount').classList.toggle('hidden', count === 0);
    if (count > 0) document.getElementById('batchCount').textContent = `已选 ${count} 项`;
}

function batchAction(action) {
    const checked = document.querySelectorAll('.batch-check:checked');
    const ids = Array.from(checked).map(cb => cb.value);
    if (ids.length === 0) return;

    const msg = action === 'delete' ? `确认删除选中的 ${ids.length} 个课程？` : null;
    if (msg && !confirm(msg)) return;

    fetch('/api/courses/batch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ course_ids: ids, action: action })
    })
    .then(r => r.json())
    .then(data => {
        refreshAll();
    });
}

// 监听复选框变化
document.addEventListener('change', function(e) {
    if (e.target.classList.contains('batch-check')) updateBatchButtons();
});

// ═══════════════════════════════════════════
// 行点击展开详情
// ═══════════════════════════════════════════
document.addEventListener('click', function(e) {
    const row = e.target.closest('.hover\\:bg-gray-50.border-b.group');
    if (!row || e.target.closest('button') || e.target.closest('.status-badge') || e.target.closest('input')) return;

    const detailId = row.getAttribute('id') ? null : null;
    // Find the corresponding detail row (next sibling)
    const detailRow = row.nextElementSibling;
    if (detailRow && detailRow.id && detailRow.id.startsWith('detail-')) {
        detailRow.classList.toggle('hidden');
    }
});

// ═══════════════════════════════════════════
// 刷新
// ═══════════════════════════════════════════
function refreshAll() {
    htmx.trigger('#courseCards', 'load');
    htmx.trigger('#courseTable', 'load');
}
