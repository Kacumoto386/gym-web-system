// ── 会员充值弹窗 ──
var selectedMember = null;
var searchTimer = null;

function openAddModal() {
    document.getElementById('addModal').classList.remove('hidden');
    selectedMember = null;
    document.getElementById('memberId').value = '';
    document.getElementById('memberName').value = '';
    document.getElementById('memberSearch').value = '';
    document.getElementById('memberDropdown').classList.add('hidden');
    document.getElementById('memberError').classList.add('hidden');
    var today = new Date().toISOString().split('T')[0];
    document.querySelector('#addModal input[name="recharge_date"]').value = today;
    loadActiveStaff();
}

function loadActiveStaff() {
    var sel = document.getElementById('operatorSelect');
    sel.innerHTML = '<option value="">请选择</option>';
    fetch('/api/staff/search-json?q=')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            data.filter(function(s) { return s.status === '在职'; }).forEach(function(s) {
                var opt = document.createElement('option');
                opt.value = s.name;
                opt.textContent = s.name;
                sel.appendChild(opt);
            });
        })
        .catch(function() {});
}

function searchMember(q) {
    clearTimeout(searchTimer);
    document.getElementById('memberId').value = '';
    document.getElementById('memberName').value = '';
    selectedMember = null;

    q = q.trim();
    if (!q) {
        document.getElementById('memberDropdown').classList.add('hidden');
        return;
    }

    searchTimer = setTimeout(function() {
        fetch('/api/members/search-json?q=' + encodeURIComponent(q))
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var dd = document.getElementById('memberDropdown');
                if (!data || data.length === 0) {
                    dd.innerHTML = '<div class="px-3 py-2 text-sm text-gray-400">未找到匹配会员</div>';
                    dd.classList.remove('hidden');
                    return;
                }
                dd.innerHTML = data.map(function(m) {
                    return '<div class="px-3 py-2 text-sm hover:bg-blue-50 cursor-pointer border-b flex justify-between items-center" ' +
                        'onclick="selectMember(\'' + m.member_id + '\', \'' + m.name.replace(/'/g, "\\'") + '\', \'' + (m.phone || '').replace(/'/g, "\\'") + '\')">' +
                        '<span>' + m.name + '</span>' +
                        '<span class="text-gray-400 text-xs">' + (m.phone || '') + ' ' + m.member_id + '</span>' +
                        '</div>';
                }).join('');
                dd.classList.remove('hidden');
            });
    }, 300);
}

function selectMember(id, name, phone) {
    document.getElementById('memberId').value = id;
    document.getElementById('memberName').value = name;
    document.getElementById('memberSearch').value = name + ' (' + phone + ' ' + id + ')';
    document.getElementById('memberDropdown').classList.add('hidden');
    selectedMember = id;
    document.getElementById('memberError').classList.add('hidden');
}

function validateRechargeForm() {
    if (!selectedMember) {
        document.getElementById('memberError').classList.remove('hidden');
        document.getElementById('memberSearch').focus();
        return false;
    }
    return true;
}

document.addEventListener('click', function(e) {
    var dd = document.getElementById('memberDropdown');
    if (dd && !e.target.closest('.col-span-2')) {
        dd.classList.add('hidden');
    }
});
