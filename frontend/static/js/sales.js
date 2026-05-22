// ═══════════════════════════════════════
// 缓存数据
// ═══════════════════════════════════════
let coursesCache = [];
let memberSearchTimer = null;
let memberSelected = null;
let courseSelected = null;
let staffSelected = null;

// ═══════════════════════════════════════
// 对话框
// ═══════════════════════════════════════
function openAddModal() {
    document.getElementById('addModal').classList.remove('hidden');
    clearForm();
    loadMembers();
    loadCourses();
    loadStaff();
}

function closeAddModal() {
    document.getElementById('addModal').classList.add('hidden');
}

function clearForm() {
    memberSelected = null;
    courseSelected = null;
    staffSelected = null;
    document.getElementById('searchMember').value = '';
    document.getElementById('searchCourse').value = '';
    document.getElementById('searchStaff').value = '';
    document.getElementById('memberInfo').innerHTML = '<span class="text-gray-400">未选择</span>';
    document.getElementById('courseInfo').innerHTML = '<span class="text-gray-400">未选择</span>';
    document.getElementById('staffInfo').innerHTML = '<span class="text-gray-400">未选择</span>';
    document.getElementById('fldMemberId').value = '';
    document.getElementById('fldMemberName').value = '';
    document.getElementById('fldMemberPhone').value = '';
    document.getElementById('fldCourseId').value = '';
    document.getElementById('fldCourseName').value = '';
    document.getElementById('fldUnitPrice').value = '0';
    document.getElementById('fldStaffId').value = '';
    document.getElementById('fldStaffName').value = '';
    document.getElementById('fldStartDate').value = new Date().toISOString().split('T')[0];
    document.getElementById('fldEndDate').value = '';
    document.getElementById('formError').classList.add('hidden');
    hideMemberDropdown();
    hideCourseDropdown();
    hideStaffDropdown();
}

// ═══════════════════════════════════════
// 加载数据
// ═══════════════════════════════════════
function loadMembers() {
    // 打开弹窗时先加载最近 10 个会员作为快速选择
    fetch('/api/members/search-json?q=')
        .then(r => r.json())
        .then(data => { showMemberList(data || []); })
        .catch(() => {});
}

function loadCourses() {
    fetch('/api/courses/search-json?q=')
        .then(r => r.json())
        .then(data => { coursesCache = data || []; filterCourses(); })
        .catch(() => {});
}

function loadStaff() {
    fetch('/api/staff/search-json?q=')
        .then(r => r.json())
        .then(data => { staffCache = data || []; filterStaff(); })
        .catch(() => {});
}

// ═══════════════════════════════════════
// 会员搜索下拉
// ═══════════════════════════════════════
function showMemberList(members) {
    const dd = document.getElementById('memberDropdown');
    if (!members || members.length === 0) {
        dd.innerHTML = '<div class="px-3 py-2 text-sm text-gray-400">未找到匹配会员</div>';
    } else {
        dd.innerHTML = members.map(m =>
            `<div class="px-3 py-2 text-sm hover:bg-blue-50 cursor-pointer border-b border-gray-50 last:border-0 flex justify-between"
                  onmousedown="selectMember('${m.member_id}', '${(m.name || '').replace(/'/g, "\\'")}', '${(m.phone || '').replace(/'/g, "\\'")}', this)">
                <span>${m.name || '-'}</span>
                <span class="text-gray-400 text-xs ml-2">${m.member_id || ''} ${m.phone ? '· ' + m.phone : ''}</span>
            </div>`
        ).join('');
    }
    dd.classList.remove('hidden');
}

function filterMembers() {
    const q = document.getElementById('searchMember').value.trim();
    clearTimeout(memberSearchTimer);
    if (!q) {
        // 空关键词：快速显示最近 10 个
        fetch('/api/members/search-json?q=')
            .then(r => r.json())
            .then(data => showMemberList(data || []))
            .catch(() => {});
        return;
    }
    memberSearchTimer = setTimeout(function() {
        fetch('/api/members/search-json?q=' + encodeURIComponent(q))
            .then(r => r.json())
            .then(data => showMemberList(data || []))
            .catch(() => {});
    }, 200);
}

function showMemberDropdown() {
    const dd = document.getElementById('memberDropdown');
    if (!dd.classList.contains('hidden')) return;
    filterMembers();
    dd.classList.remove('hidden');
}

function hideMemberDropdown() {
    setTimeout(() => document.getElementById('memberDropdown').classList.add('hidden'), 200);
}

function selectMember(id, name, phone, el) {
    memberSelected = { id, name, phone };
    document.getElementById('fldMemberId').value = id;
    document.getElementById('fldMemberName').value = name;
    document.getElementById('fldMemberPhone').value = phone;
    document.getElementById('memberInfo').innerHTML =
        `<span class="text-gray-700">${name}</span><span class="text-gray-400 text-xs ml-2">${id} · ${phone}</span>`;
    document.getElementById('searchMember').value = name;
    document.getElementById('memberDropdown').classList.add('hidden');
}

function clearMember() {
    memberSelected = null;
    document.getElementById('fldMemberId').value = '';
    document.getElementById('fldMemberName').value = '';
    document.getElementById('fldMemberPhone').value = '';
    document.getElementById('memberInfo').innerHTML = '<span class="text-gray-400">未选择</span>';
    document.getElementById('searchMember').value = '';
    filterMembers();
}

// ═══════════════════════════════════════
// 课程搜索下拉
// ═══════════════════════════════════════
function filterCourses() {
    const q = document.getElementById('searchCourse').value.trim().toLowerCase();
    const list = q ? coursesCache.filter(c =>
        (c.name || '').toLowerCase().includes(q) ||
        (c.course_id || '').toLowerCase().includes(q)
    ) : coursesCache;

    const dd = document.getElementById('courseDropdown');
    if (list.length === 0) {
        dd.innerHTML = '<div class="px-3 py-2 text-sm text-gray-400">未找到匹配课程</div>';
    } else {
        dd.innerHTML = list.map(c =>
            `<div class="px-3 py-2 text-sm hover:bg-blue-50 cursor-pointer border-b border-gray-50 last:border-0 flex justify-between"
                  onmousedown="selectCourse('${c.course_id}', '${(c.name || '').replace(/'/g, "\\'")}', ${c.standard_price || 0}, ${c.valid_days || 0}, this)">
                <span>${c.name || '-'}</span>
                <span class="text-gray-400 text-xs ml-2">${c.course_type || ''} · ¥${c.standard_price || 0}${c.valid_days ? ' · ' + c.valid_days + '天' : ''}</span>
            </div>`
        ).join('');
    }
    dd.classList.remove('hidden');
}

function showCourseDropdown() {
    const dd = document.getElementById('courseDropdown');
    if (!dd.classList.contains('hidden')) return;
    filterCourses();
    dd.classList.remove('hidden');
}

function hideCourseDropdown() {
    setTimeout(() => document.getElementById('courseDropdown').classList.add('hidden'), 200);
}

function selectCourse(id, name, price, validDays, el) {
    courseSelected = { id, name, price, validDays };
    document.getElementById('fldCourseId').value = id;
    document.getElementById('fldCourseName').value = name;
    document.getElementById('fldUnitPrice').value = price;
    document.getElementById('courseInfo').innerHTML =
        `<span class="text-gray-700">${name}</span><span class="text-gray-400 text-xs ml-2">${id} · ¥${price}</span>`;
    document.getElementById('searchCourse').value = name;
    document.getElementById('courseDropdown').classList.add('hidden');
    // 自动计算到期日期
    if (validDays > 0) {
        var startVal = document.getElementById('fldStartDate').value;
        if (startVal) {
            var d = new Date(startVal);
            d.setDate(d.getDate() + validDays);
            document.getElementById('fldEndDate').value = d.toISOString().split('T')[0];
        }
    }
}

function autoCalcEndDate() {
    if (!courseSelected || !courseSelected.validDays) return;
    var startVal = document.getElementById('fldStartDate').value;
    if (startVal) {
        var d = new Date(startVal);
        d.setDate(d.getDate() + courseSelected.validDays);
        document.getElementById('fldEndDate').value = d.toISOString().split('T')[0];
    }
}

function clearCourse() {
    courseSelected = null;
    document.getElementById('fldCourseId').value = '';
    document.getElementById('fldCourseName').value = '';
    document.getElementById('fldUnitPrice').value = '0';
    document.getElementById('courseInfo').innerHTML = '<span class="text-gray-400">未选择</span>';
    document.getElementById('searchCourse').value = '';
    filterCourses();
}

// ═══════════════════════════════════════
// 员工搜索下拉
// ═══════════════════════════════════════
let staffCache = [];

function filterStaff() {
    const q = document.getElementById('searchStaff').value.trim().toLowerCase();
    const list = q ? staffCache.filter(s =>
        (s.name || '').toLowerCase().includes(q) ||
        (s.staff_id || '').toLowerCase().includes(q) ||
        (s.phone || '').includes(q)
    ) : staffCache;

    const dd = document.getElementById('staffDropdown');
    if (list.length === 0) {
        dd.innerHTML = '<div class="px-3 py-2 text-sm text-gray-400">未找到匹配员工</div>';
    } else {
        dd.innerHTML = list.map(s =>
            `<div class="px-3 py-2 text-sm hover:bg-blue-50 cursor-pointer border-b border-gray-50 last:border-0 flex justify-between"
                  onmousedown="selectStaff('${s.staff_id}', '${(s.name || '').replace(/'/g, "\\'")}', '${(s.position || '').replace(/'/g, "\\'")}', this)">
                <span>${s.name || '-'}</span>
                <span class="text-gray-400 text-xs ml-2">${s.staff_id || ''} · ${s.position || ''}</span>
            </div>`
        ).join('');
    }
    dd.classList.remove('hidden');
}

function showStaffDropdown() {
    const dd = document.getElementById('staffDropdown');
    if (!dd.classList.contains('hidden')) return;
    filterStaff();
    dd.classList.remove('hidden');
}

function hideStaffDropdown() {
    setTimeout(() => document.getElementById('staffDropdown').classList.add('hidden'), 200);
}

function selectStaff(id, name, position, el) {
    staffSelected = { id, name, position };
    document.getElementById('fldStaffId').value = id;
    document.getElementById('fldStaffName').value = name;
    document.getElementById('staffInfo').innerHTML =
        `<span class="text-gray-700">${name}</span><span class="text-gray-400 text-xs ml-2">${id} · ${position}</span>`;
    document.getElementById('searchStaff').value = name;
    document.getElementById('staffDropdown').classList.add('hidden');
}

function clearStaff() {
    staffSelected = null;
    document.getElementById('fldStaffId').value = '';
    document.getElementById('fldStaffName').value = '';
    document.getElementById('staffInfo').innerHTML = '<span class="text-gray-400">未选择</span>';
    document.getElementById('searchStaff').value = '';
    filterStaff();
}

// ═══════════════════════════════════════
// 提交
// ═══════════════════════════════════════
function submitSale() {
    const form = document.getElementById('saleForm');

    const data = {};
    const fields = form.querySelectorAll('input[name], select[name]');
    fields.forEach(el => {
        const name = el.getAttribute('name');
        if (name) data[name] = el.value;
    });

    // 数字类型转换
    data.bought_hours = parseInt(data.bought_hours) || 1;
    data.bonus_hours = parseInt(data.bonus_hours) || 0;
    data.actual_amount = parseFloat(data.actual_amount) || 0;
    data.unit_price = parseFloat(data.unit_price) || 0;

    // 日期空值转 null
    Object.keys(data).forEach(k => {
        if (data[k] === '' && (k.endsWith('_date') || k === 'start_date' || k === 'end_date')) {
            data[k] = null;
        }
    });

    fetch('/api/sales', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(result => {
        if (result.id || result.sale_id) {
            closeAddModal();
            const el = document.getElementById('saleTable');
            el.innerHTML = '<div class="text-center py-8 text-gray-400">加载中...</div>';
            htmx.ajax('GET', '/api/sales/table', {target: '#saleTable'});
        } else {
            showError(result.detail || result.message || '保存失败');
        }
    })
    .catch(e => showError('请求失败: ' + e));
}

function showError(msg) {
    const el = document.getElementById('formError');
    el.textContent = msg;
    el.classList.remove('hidden');
}

// ═══════════════════════════════════════
// 编辑售课
// ═══════════════════════════════════════

let currentEditSaleId = null;
let editMemberSelected = null;
let editCourseSelected = null;
let editStaffSelected = null;
let editCoursesCache = [];
let editStaffCache = [];
let editMemberSearchTimer = null;

function openEditSale(saleId) {
    currentEditSaleId = saleId;
    clearEditForm();

    fetch('/api/sales/' + saleId)
        .then(function(r) {
            if (!r.ok) throw new Error('获取售课记录失败');
            return r.json();
        })
        .then(function(data) {
            // 会员
            editMemberSelected = { id: data.member_id, name: data.member_name, phone: data.member_phone };
            document.getElementById('editFldMemberId').value = data.member_id || '';
            document.getElementById('editFldMemberName').value = data.member_name || '';
            document.getElementById('editFldMemberPhone').value = data.member_phone || '';
            document.getElementById('editMemberInfo').innerHTML = data.member_name
                ? '<span class="text-gray-700">' + data.member_name + '</span><span class="text-gray-400 text-xs ml-2">' + (data.member_id || '') + ' · ' + (data.member_phone || '') + '</span>'
                : '<span class="text-gray-400">未选择</span>';
            document.getElementById('editSearchMember').value = data.member_name || '';

            // 课程
            editCourseSelected = { id: data.course_id, name: data.course_name, price: data.unit_price };
            document.getElementById('editFldCourseId').value = data.course_id || '';
            document.getElementById('editFldCourseName').value = data.course_name || '';
            document.getElementById('editFldUnitPrice').value = data.unit_price || 0;
            document.getElementById('editCourseInfo').innerHTML = data.course_name
                ? '<span class="text-gray-700">' + data.course_name + '</span><span class="text-gray-400 text-xs ml-2">' + (data.course_id || '') + ' · ¥' + (data.unit_price || 0) + '</span>'
                : '<span class="text-gray-400">未选择</span>';
            document.getElementById('editSearchCourse').value = data.course_name || '';

            // 数值字段
            document.getElementById('editBoughtHours').value = data.bought_hours || 0;
            document.getElementById('editBonusHours').value = data.bonus_hours || 0;
            document.getElementById('editActualAmount').value = data.actual_amount || 0;

            // 下拉选择
            document.getElementById('editPaymentMethod').value = data.payment_method || '';
            document.getElementById('editPaymentStatus').value = data.payment_status || '已付清';

            // 日期
            document.getElementById('editFldStartDate').value = data.start_date || '';
            document.getElementById('editFldEndDate').value = data.end_date || '';

            // 员工
            editStaffSelected = { id: data.staff_id, name: data.staff_name };
            document.getElementById('editFldStaffId').value = data.staff_id || '';
            document.getElementById('editFldStaffName').value = data.staff_name || '';
            document.getElementById('editStaffInfo').innerHTML = data.staff_name
                ? '<span class="text-gray-700">' + data.staff_name + '</span><span class="text-gray-400 text-xs ml-2">' + (data.staff_id || '') + '</span>'
                : '<span class="text-gray-400">未选择</span>';
            document.getElementById('editSearchStaff').value = data.staff_name || '';

            // 加载搜索缓存
            loadEditMembers();
            loadEditCourses();
            loadEditStaff();

            document.getElementById('editModal').classList.remove('hidden');
        })
        .catch(function(e) {
            showEditError('加载售课记录失败: ' + e.message);
        });
}

function closeEditModal() {
    document.getElementById('editModal').classList.add('hidden');
    currentEditSaleId = null;
    editMemberSelected = null;
    editCourseSelected = null;
    editStaffSelected = null;
}

function clearEditForm() {
    editMemberSelected = null;
    editCourseSelected = null;
    editStaffSelected = null;
    document.getElementById('editSearchMember').value = '';
    document.getElementById('editSearchCourse').value = '';
    document.getElementById('editSearchStaff').value = '';
    document.getElementById('editMemberInfo').innerHTML = '<span class="text-gray-400">未选择</span>';
    document.getElementById('editCourseInfo').innerHTML = '<span class="text-gray-400">未选择</span>';
    document.getElementById('editStaffInfo').innerHTML = '<span class="text-gray-400">未选择</span>';
    document.getElementById('editFldMemberId').value = '';
    document.getElementById('editFldMemberName').value = '';
    document.getElementById('editFldMemberPhone').value = '';
    document.getElementById('editFldCourseId').value = '';
    document.getElementById('editFldCourseName').value = '';
    document.getElementById('editFldUnitPrice').value = '0';
    document.getElementById('editFldStaffId').value = '';
    document.getElementById('editFldStaffName').value = '';
    document.getElementById('editFldStartDate').value = '';
    document.getElementById('editFldEndDate').value = '';
    document.getElementById('editFormError').classList.add('hidden');
    hideEditMemberDropdown();
    hideEditCourseDropdown();
    hideEditStaffDropdown();
}

function loadEditMembers() {
    fetch('/api/members/search-json?q=')
        .then(function(r) { return r.json(); })
        .then(function(data) { showEditMemberList(data || []); })
        .catch(function() {});
}

function loadEditCourses() {
    fetch('/api/courses/search-json?q=')
        .then(function(r) { return r.json(); })
        .then(function(data) { editCoursesCache = data || []; filterEditCourses(); })
        .catch(function() {});
}

function loadEditStaff() {
    fetch('/api/staff/search-json?q=')
        .then(function(r) { return r.json(); })
        .then(function(data) { editStaffCache = data || []; filterEditStaff(); })
        .catch(function() {});
}

// 会员搜索
function showEditMemberList(members) {
    var dd = document.getElementById('editMemberDropdown');
    if (!members || members.length === 0) {
        dd.innerHTML = '<div class="px-3 py-2 text-sm text-gray-400">未找到匹配会员</div>';
    } else {
        dd.innerHTML = members.map(function(m) {
            return '<div class="px-3 py-2 text-sm hover:bg-blue-50 cursor-pointer border-b border-gray-50 last:border-0 flex justify-between"'
                + ' onmousedown="selectEditMember(\'' + m.member_id + '\', \'' + (m.name || '').replace(/'/g, "\\'") + '\', \'' + (m.phone || '').replace(/'/g, "\\'") + '\', this)">'
                + '<span>' + (m.name || '-') + '</span>'
                + '<span class="text-gray-400 text-xs ml-2">' + (m.member_id || '') + (m.phone ? ' · ' + m.phone : '') + '</span>'
                + '</div>';
        }).join('');
    }
    dd.classList.remove('hidden');
}

function filterEditMembers() {
    var q = document.getElementById('editSearchMember').value.trim();
    clearTimeout(editMemberSearchTimer);
    if (!q) {
        fetch('/api/members/search-json?q=')
            .then(function(r) { return r.json(); })
            .then(function(data) { showEditMemberList(data || []); })
            .catch(function() {});
        return;
    }
    editMemberSearchTimer = setTimeout(function() {
        fetch('/api/members/search-json?q=' + encodeURIComponent(q))
            .then(function(r) { return r.json(); })
            .then(function(data) { showEditMemberList(data || []); })
            .catch(function() {});
    }, 200);
}

function showEditMemberDropdown() {
    var dd = document.getElementById('editMemberDropdown');
    if (!dd.classList.contains('hidden')) return;
    filterEditMembers();
    dd.classList.remove('hidden');
}

function hideEditMemberDropdown() {
    setTimeout(function() { document.getElementById('editMemberDropdown').classList.add('hidden'); }, 200);
}

function selectEditMember(id, name, phone, el) {
    editMemberSelected = { id: id, name: name, phone: phone };
    document.getElementById('editFldMemberId').value = id;
    document.getElementById('editFldMemberName').value = name;
    document.getElementById('editFldMemberPhone').value = phone;
    document.getElementById('editMemberInfo').innerHTML =
        '<span class="text-gray-700">' + name + '</span><span class="text-gray-400 text-xs ml-2">' + id + ' · ' + phone + '</span>';
    document.getElementById('editSearchMember').value = name;
    document.getElementById('editMemberDropdown').classList.add('hidden');
}

function clearEditMember() {
    editMemberSelected = null;
    document.getElementById('editFldMemberId').value = '';
    document.getElementById('editFldMemberName').value = '';
    document.getElementById('editFldMemberPhone').value = '';
    document.getElementById('editMemberInfo').innerHTML = '<span class="text-gray-400">未选择</span>';
    document.getElementById('editSearchMember').value = '';
    filterEditMembers();
}

// 课程搜索
function filterEditCourses() {
    var q = document.getElementById('editSearchCourse').value.trim().toLowerCase();
    var list = q
        ? editCoursesCache.filter(function(c) { return (c.name || '').toLowerCase().includes(q) || (c.course_id || '').toLowerCase().includes(q); })
        : editCoursesCache;
    var dd = document.getElementById('editCourseDropdown');
    if (list.length === 0) {
        dd.innerHTML = '<div class="px-3 py-2 text-sm text-gray-400">未找到匹配课程</div>';
    } else {
        dd.innerHTML = list.map(function(c) {
            return '<div class="px-3 py-2 text-sm hover:bg-blue-50 cursor-pointer border-b border-gray-50 last:border-0 flex justify-between"'
                + ' onmousedown="selectEditCourse(\'' + c.course_id + '\', \'' + (c.name || '').replace(/'/g, "\\'") + '\', ' + (c.standard_price || 0) + ', ' + (c.valid_days || 0) + ', this)">'
                + '<span>' + (c.name || '-') + '</span>'
                + '<span class="text-gray-400 text-xs ml-2">' + (c.course_type || '') + ' · ¥' + (c.standard_price || 0) + (c.valid_days ? ' · ' + c.valid_days + '天' : '') + '</span>'
                + '</div>';
        }).join('');
    }
    dd.classList.remove('hidden');
}

function showEditCourseDropdown() {
    var dd = document.getElementById('editCourseDropdown');
    if (!dd.classList.contains('hidden')) return;
    filterEditCourses();
    dd.classList.remove('hidden');
}

function hideEditCourseDropdown() {
    setTimeout(function() { document.getElementById('editCourseDropdown').classList.add('hidden'); }, 200);
}

function selectEditCourse(id, name, price, validDays, el) {
    editCourseSelected = { id: id, name: name, price: price, validDays: validDays };
    document.getElementById('editFldCourseId').value = id;
    document.getElementById('editFldCourseName').value = name;
    document.getElementById('editFldUnitPrice').value = price;
    document.getElementById('editCourseInfo').innerHTML =
        '<span class="text-gray-700">' + name + '</span><span class="text-gray-400 text-xs ml-2">' + id + ' · ¥' + price + '</span>';
    document.getElementById('editSearchCourse').value = name;
    document.getElementById('editCourseDropdown').classList.add('hidden');
    if (validDays > 0) {
        var startVal = document.getElementById('editFldStartDate').value;
        if (startVal) {
            var d = new Date(startVal);
            d.setDate(d.getDate() + validDays);
            document.getElementById('editFldEndDate').value = d.toISOString().split('T')[0];
        }
    }
}

function clearEditCourse() {
    editCourseSelected = null;
    document.getElementById('editFldCourseId').value = '';
    document.getElementById('editFldCourseName').value = '';
    document.getElementById('editFldUnitPrice').value = '0';
    document.getElementById('editCourseInfo').innerHTML = '<span class="text-gray-400">未选择</span>';
    document.getElementById('editSearchCourse').value = '';
    filterEditCourses();
}

// 员工搜索
function filterEditStaff() {
    var q = document.getElementById('editSearchStaff').value.trim().toLowerCase();
    var list = q
        ? editStaffCache.filter(function(s) { return (s.name || '').toLowerCase().includes(q) || (s.staff_id || '').toLowerCase().includes(q) || (s.phone || '').includes(q); })
        : editStaffCache;
    var dd = document.getElementById('editStaffDropdown');
    if (list.length === 0) {
        dd.innerHTML = '<div class="px-3 py-2 text-sm text-gray-400">未找到匹配员工</div>';
    } else {
        dd.innerHTML = list.map(function(s) {
            return '<div class="px-3 py-2 text-sm hover:bg-blue-50 cursor-pointer border-b border-gray-50 last:border-0 flex justify-between"'
                + ' onmousedown="selectEditStaff(\'' + s.staff_id + '\', \'' + (s.name || '').replace(/'/g, "\\'") + '\', \'' + (s.position || '').replace(/'/g, "\\'") + '\', this)">'
                + '<span>' + (s.name || '-') + '</span>'
                + '<span class="text-gray-400 text-xs ml-2">' + (s.staff_id || '') + ' · ' + (s.position || '') + '</span>'
                + '</div>';
        }).join('');
    }
    dd.classList.remove('hidden');
}

function showEditStaffDropdown() {
    var dd = document.getElementById('editStaffDropdown');
    if (!dd.classList.contains('hidden')) return;
    filterEditStaff();
    dd.classList.remove('hidden');
}

function hideEditStaffDropdown() {
    setTimeout(function() { document.getElementById('editStaffDropdown').classList.add('hidden'); }, 200);
}

function selectEditStaff(id, name, position, el) {
    editStaffSelected = { id: id, name: name, position: position };
    document.getElementById('editFldStaffId').value = id;
    document.getElementById('editFldStaffName').value = name;
    document.getElementById('editStaffInfo').innerHTML =
        '<span class="text-gray-700">' + name + '</span><span class="text-gray-400 text-xs ml-2">' + id + ' · ' + position + '</span>';
    document.getElementById('editSearchStaff').value = name;
    document.getElementById('editStaffDropdown').classList.add('hidden');
}

function clearEditStaff() {
    editStaffSelected = null;
    document.getElementById('editFldStaffId').value = '';
    document.getElementById('editFldStaffName').value = '';
    document.getElementById('editStaffInfo').innerHTML = '<span class="text-gray-400">未选择</span>';
    document.getElementById('editSearchStaff').value = '';
    filterEditStaff();
}

// 提交编辑
function submitEditSale() {
    if (!currentEditSaleId) {
        showEditError('未找到售课记录，请重新打开编辑窗口');
        return;
    }

    var form = document.getElementById('editSaleForm');
    var data = {};
    var fields = form.querySelectorAll('input[name], select[name]');
    fields.forEach(function(el) {
        var name = el.getAttribute('name');
        if (name) data[name] = el.value;
    });

    // 数字类型转换
    data.bought_hours = parseInt(data.bought_hours) || 0;
    data.bonus_hours = parseInt(data.bonus_hours) || 0;
    data.actual_amount = parseFloat(data.actual_amount) || 0;
    data.unit_price = parseFloat(data.unit_price) || 0;

    // 日期空值转 null
    Object.keys(data).forEach(function(k) {
        if (data[k] === '' && (k.endsWith('_date') || k === 'start_date' || k === 'end_date')) {
            data[k] = null;
        }
    });

    var btn = form.querySelector('button[onclick="submitEditSale()"]');
    if (btn) { btn.disabled = true; btn.textContent = '保存中...'; }

    fetch('/api/sales/' + currentEditSaleId, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(function(r) {
        if (r.ok) return r.json();
        return r.json().then(function(e) { throw new Error(e.detail || '保存失败'); });
    })
    .then(function() {
        closeEditModal();
        var el = document.getElementById('saleTable');
        el.innerHTML = '<div class="text-center py-8 text-gray-400">加载中...</div>';
        htmx.ajax('GET', '/api/sales/table', {target: '#saleTable'});
    })
    .catch(function(e) {
        showEditError('保存失败: ' + e.message);
    })
    .finally(function() {
        if (btn) { btn.disabled = false; btn.textContent = '保存修改'; }
    });
}

function showEditError(msg) {
    var el = document.getElementById('editFormError');
    el.textContent = msg;
    el.classList.remove('hidden');
}
