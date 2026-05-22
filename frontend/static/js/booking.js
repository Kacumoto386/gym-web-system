let coachesCache = [];
let searchTimer = null;

// ===== 初始化 =====

function init() {
    loadCoaches();
}

function loadCoursesForMember(memberId) {
    const sel = document.getElementById('addCourse');
    sel.innerHTML = '<option value="">加载中...</option>';
    fetch('/api/booking/member-courses?member_id=' + encodeURIComponent(memberId))
        .then(r => r.json())
        .then(data => {
            const courses = data.courses || [];
            if (courses.length === 0) {
                sel.innerHTML = '<option value="">该会员暂无已购课程</option>';
                return;
            }
            sel.innerHTML = '<option value="">-- 选择课程 --</option>' +
                courses.map(function(c) {
                    var label = c.expired ? c.course_name + ' (已过期)' : c.course_name + ' (剩余 ' + c.total_remaining + ' 课时)';
                    return '<option value="' + c.course_id + '" data-name="' + c.course_name + '" data-expired="' + c.expired + '">' + label + '</option>';
                }).join('');
        })
        .catch(function() {
            sel.innerHTML = '<option value="">加载失败</option>';
        });
}

function loadCoaches() {
    fetch('/api/booking/coaches')
        .then(r => r.json())
        .then(data => {
            coachesCache = data || [];
            const sel = document.getElementById('addCoach');
            sel.innerHTML = '<option value="">-- 选择教练 --</option>' +
                coachesCache.map(c => `<option value="${c.staff_id}" data-name="${c.name || ''}">${c.name}${c.position ? ' ('+c.position+')' : ''}</option>`).join('');
        });
}

// ===== 会员搜索 =====

function searchMember(keyword) {
    clearTimeout(searchTimer);
    var resultsEl = document.getElementById('memberSearchResults');
    if (!keyword || keyword.trim().length < 1) {
        resultsEl.classList.add('hidden');
        return;
    }
    searchTimer = setTimeout(function() {
        fetch('/api/members/search-json?q=' + encodeURIComponent(keyword.trim()))
            .then(function(r) { return r.json(); })
            .then(function(members) {
                if (!members || members.length === 0) {
                    resultsEl.innerHTML = '<div class="px-3 py-2 text-sm text-gray-400">未找到会员</div>';
                    resultsEl.classList.remove('hidden');
                    return;
                }
                resultsEl.innerHTML = members.map(function(m) {
                    return '<div class="px-3 py-2 hover:bg-blue-50 cursor-pointer text-sm border-b border-gray-50 flex justify-between items-center" onclick="selectBookingMember(\'' + m.member_id + '\',\'' + (m.name || '').replace(/'/g, "\\'") + '\',\'' + (m.phone || '').replace(/'/g, "\\'") + '\')">' +
                        '<div><span class="font-medium">' + (m.name || '') + '</span><span class="text-gray-400 ml-2">' + (m.phone || '') + '</span></div>' +
                        '<span class="text-xs text-gray-400">' + (m.member_id || '') + '</span>' +
                    '</div>';
                }).join('');
                resultsEl.classList.remove('hidden');
            });
    }, 200);
}

function selectBookingMember(id, name, phone) {
    document.getElementById('memberSearchInput').value = name + ' (' + phone + ')';
    document.getElementById('memberSearchResults').classList.add('hidden');
    document.getElementById('selectedMemberId').value = id;
    document.getElementById('selectedMemberName').value = name;
    document.getElementById('selectedMemberPhone').value = phone;
    document.getElementById('clearMemberBtn').classList.remove('hidden');
    onMemberChange();
}

function clearMemberSelection() {
    document.getElementById('memberSearchInput').value = '';
    document.getElementById('selectedMemberId').value = '';
    document.getElementById('selectedMemberName').value = '';
    document.getElementById('selectedMemberPhone').value = '';
    document.getElementById('memberSearchResults').classList.add('hidden');
    document.getElementById('clearMemberBtn').classList.add('hidden');
    onMemberChange();
}

function onMemberChange() {
    var memberId = document.getElementById('selectedMemberId').value;
    var courseSel = document.getElementById('addCourse');
    courseSel.value = '';
    if (memberId) {
        loadCoursesForMember(memberId);
    } else {
        courseSel.innerHTML = '<option value="">-- 请先选择会员 --</option>';
    }
}
function onCourseChange() {}
function onCoachChange() {}

// ===== 筛选 =====

function refreshTable() {
    const dateFrom = document.getElementById('filterDateFrom').value;
    const dateTo = document.getElementById('filterDateTo').value;
    const status = document.getElementById('filterStatus').value;
    const params = new URLSearchParams();
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);
    if (status) params.set('status', status);

    const el = document.getElementById('bookingTable');
    el.innerHTML = '<div class="text-center py-8 text-gray-400">加载中...</div>';
    htmx.ajax('GET', `/api/booking/table?${params.toString()}`, {target: '#bookingTable'});
}

function todayFilter() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('filterDateFrom').value = today;
    document.getElementById('filterDateTo').value = today;
    refreshTable();
}

// ===== 新增预约对话框 =====

function openAddBooking() {
    document.getElementById('addBookingModal').classList.remove('hidden');
    document.getElementById('addDate').value = new Date().toISOString().split('T')[0];
    document.getElementById('addBookingError').classList.add('hidden');
    // 重置会员搜索
    clearMemberSelection();
    document.getElementById('memberSearchInput').value = '';
    // 重置课程下拉（等待选择会员）
    document.getElementById('addCourse').innerHTML = '<option value="">-- 请先选择会员 --</option>';
    // 重新加载数据确保最新
    loadCoaches();
}

function closeAddBooking() {
    document.getElementById('addBookingModal').classList.add('hidden');
}

function submitBooking() {
    const date = document.getElementById('addDate').value;
    const memberId = document.getElementById('selectedMemberId').value;
    const memberName = document.getElementById('selectedMemberName').value;
    const memberPhone = document.getElementById('selectedMemberPhone').value;
    const startTime = document.getElementById('addStartTime').value;
    const endTime = document.getElementById('addEndTime').value;
    const courseSel = document.getElementById('addCourse');
    const courseId = courseSel.value;
    const courseName = courseSel.options[courseSel.selectedIndex]?.dataset?.name || '';
    const coachSel = document.getElementById('addCoach');
    const coachId = coachSel.value;
    const coachName = coachSel.options[coachSel.selectedIndex]?.dataset?.name || '';
    const location = document.getElementById('addLocation').value;

    // 验证
    if (!date || !memberId || !courseId) {
        showError('请填写必填项（日期、会员、课程）');
        return;
    }
    if (startTime && endTime && startTime >= endTime) {
        showError('结束时间必须晚于开始时间');
        return;
    }
    const formData = new URLSearchParams();
    formData.set('booking_date', date);
    formData.set('member_id', memberId);
    formData.set('member_name', memberName);
    formData.set('member_phone', memberPhone);
    formData.set('start_time', startTime);
    formData.set('end_time', endTime);
    formData.set('course_id', courseId);
    formData.set('course_name', courseName);
    formData.set('coach_id', coachId);
    formData.set('coach_name', coachName);
    formData.set('location', location);

    fetch('/api/booking/create', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: formData.toString()
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            closeAddBooking();
            refreshTable();
        } else {
            showError(data.detail || data.message || '保存失败');
        }
    })
    .catch(e => showError('请求失败: ' + e));
}

function showError(msg) {
    const el = document.getElementById('addBookingError');
    el.textContent = msg;
    el.classList.remove('hidden');
}

// ===== 操作按钮（由表格片段触发）=====

function bookingCheckin(bookingId) {
    if (!confirm('确认该会员已到场签到？')) return;
    fetch(`/api/booking/${bookingId}/checkin`, {method: 'POST'})
        .then(r => r.json())
        .then(data => {
            if (data.status === 'ok') {
                refreshTable();
            } else {
                alert('签到失败: ' + (data.detail || '未知错误'));
            }
        })
        .catch(e => alert('请求失败: ' + e));
}

function cancelBooking(bookingId) {
    if (!confirm('确认取消该预约？')) return;
    fetch(`/api/booking/${bookingId}/cancel`, {method: 'POST'})
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                refreshTable();
            } else {
                alert('取消失败: ' + (data.detail || '未知错误'));
            }
        })
        .catch(e => alert('请求失败: ' + e));
}

function completeBooking(bookingId) {
    if (!confirm('确认标记为已完成？')) return;
    fetch(`/api/booking/${bookingId}/complete`, {method: 'POST'})
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                refreshTable();
            } else {
                alert('操作失败: ' + (data.detail || '未知错误'));
            }
        })
        .catch(e => alert('请求失败: ' + e));
}

// 首页快速签到用
function homeCheckinBooking(bookingId) {
    fetch(`/api/booking/${bookingId}/checkin`, {method: 'POST'})
        .then(r => r.json())
        .then(data => {
            if (data.status === 'ok') {
                htmx.trigger('#todayBookings', 'load');
            } else {
                alert('签到失败: ' + (data.detail || '未知错误'));
            }
        })
        .catch(e => alert('请求失败: ' + e));
}

// ===== 查看详情 =====

function viewBooking(bookingId) {
    var modal = document.getElementById('viewBookingModal');
    var content = document.getElementById('viewBookingContent');
    content.innerHTML = '<div class="text-center py-8 text-gray-400 text-sm">加载中...</div>';
    modal.classList.remove('hidden');

    fetch('/api/booking/' + bookingId)
        .then(r => r.json())
        .then(function(d) {
            content.innerHTML =
                '<div class="grid grid-cols-2 gap-x-6 gap-y-4 text-sm">' +
                '  <div><span class="text-xs text-gray-400">预约编号</span><br><span class="text-gray-700">' + (d.booking_id || '-') + '</span></div>' +
                '  <div><span class="text-xs text-gray-400">创建时间</span><br><span class="text-gray-700">' + (d.created_at || '-') + '</span></div>' +
                '  <div><span class="text-xs text-gray-400">预约日期</span><br><span class="text-gray-700">' + (d.booking_date || '-') + '</span></div>' +
                '  <div><span class="text-xs text-gray-400">时间范围</span><br><span class="text-gray-700">' + (d.start_time || '-') + ' ~ ' + (d.end_time || '-') + '</span></div>' +
                '  <div><span class="text-xs text-gray-400">会员姓名</span><br><span class="text-gray-700">' + (d.member_name || '-') + '</span></div>' +
                '  <div><span class="text-xs text-gray-400">会员电话</span><br><span class="text-gray-700">' + (d.member_phone || '-') + '</span></div>' +
                '  <div><span class="text-xs text-gray-400">课程名称</span><br><span class="text-gray-700">' + (d.course_name || '-') + '</span></div>' +
                '  <div><span class="text-xs text-gray-400">课程编号</span><br><span class="text-gray-700">' + (d.course_id || '-') + '</span></div>' +
                '  <div><span class="text-xs text-gray-400">教练姓名</span><br><span class="text-gray-700">' + (d.coach_name || '-') + '</span></div>' +
                '  <div><span class="text-xs text-gray-400">上课地点</span><br><span class="text-gray-700">' + (d.location || '-') + '</span></div>' +
                '  <div><span class="text-xs text-gray-400">预约状态</span><br><span class="text-gray-700">' + (d.status || '-') + '</span></div>' +
                '  <div><span class="text-xs text-gray-400">签到人数</span><br><span class="text-gray-700">' + (d.sign_in_count || 0) + ' 人</span></div>' +
                '  <div><span class="text-xs text-gray-400">手环编号</span><br><span class="text-gray-700">' + (d.wristband_id || '-') + '</span></div>' +
                '  <div><span class="text-xs text-gray-400">门店编号</span><br><span class="text-gray-700">' + (d.store_id || '-') + '</span></div>' +
                '</div>';
        })
        .catch(function() {
            content.innerHTML = '<div class="text-center py-8 text-red-400 text-sm">加载失败</div>';
        });
}

function closeViewBooking() {
    document.getElementById('viewBookingModal').classList.add('hidden');
}

// 初始化
document.addEventListener('DOMContentLoaded', init);
