// ========================
// Block 1: 筛选/排序/分页
// ========================

// 当前排序状态
var currentSortBy = 'created_at';
var currentSortDir = 'desc';
var currentPage = 1;

function sortTable(col) {
    if (currentSortBy === col) {
        currentSortDir = currentSortDir === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortBy = col;
        currentSortDir = 'desc';
    }
    currentPage = 1;
    loadTable();
}

function goPage(p) {
    currentPage = p;
    loadTable();
    document.getElementById('memberTable').scrollIntoView({behavior: 'smooth'});
}

function doSearch() {
    currentPage = 1;
    loadTable();
}

function resetFilters() {
    document.getElementById('filterQ').value = '';
    document.getElementById('filterLevel').value = '';
    document.getElementById('filterStatus').value = '';
    document.getElementById('filterSource').value = '';
    document.getElementById('filterStaff').value = '';
    document.getElementById('filterRegFrom').value = '';
    document.getElementById('filterRegTo').value = '';
    document.getElementById('filterCheckinFrom').value = '';
    document.getElementById('filterCheckinTo').value = '';
    currentSortBy = 'created_at';
    currentSortDir = 'desc';
    currentPage = 1;
    loadTable();
}

function quickDate(period) {
    var today = new Date();
    var from = document.getElementById('filterCheckinFrom');
    var to = document.getElementById('filterCheckinTo');
    to.value = today.toISOString().split('T')[0];
    if (period === 'today') {
        from.value = today.toISOString().split('T')[0];
    } else if (period === 'week') {
        var weekAgo = new Date(today);
        weekAgo.setDate(today.getDate() - 7);
        from.value = weekAgo.toISOString().split('T')[0];
    } else if (period === 'month') {
        var monthAgo = new Date(today);
        monthAgo.setMonth(today.getMonth() - 1);
        from.value = monthAgo.toISOString().split('T')[0];
    } else {
        from.value = '';
        to.value = '';
    }
    currentPage = 1;
    loadTable();
}

function loadTable() {
    var params = new URLSearchParams();
    var q = document.getElementById('filterQ').value.trim();
    var level = document.getElementById('filterLevel').value;
    var status = document.getElementById('filterStatus').value;
    var source = document.getElementById('filterSource').value;
    var staff = document.getElementById('filterStaff').value;
    var regFrom = document.getElementById('filterRegFrom').value;
    var regTo = document.getElementById('filterRegTo').value;
    var checkinFrom = document.getElementById('filterCheckinFrom').value;
    var checkinTo = document.getElementById('filterCheckinTo').value;

    if (q) params.set('q', q);
    if (level) params.set('level', level);
    if (status) params.set('status', status);
    if (source) params.set('source', source);
    if (staff) params.set('staff_id', staff);
    if (regFrom) params.set('reg_from', regFrom);
    if (regTo) params.set('reg_to', regTo);
    if (checkinFrom) params.set('checkin_from', checkinFrom);
    if (checkinTo) params.set('checkin_to', checkinTo);
    params.set('sort_by', currentSortBy);
    params.set('sort_dir', currentSortDir);
    params.set('page', currentPage);

    var url = '/api/members/table?' + params.toString();
    htmx.ajax('GET', url, {target: '#memberTable', swap: 'innerHTML'});
}

// 页面加载时填充筛选下拉
document.addEventListener('DOMContentLoaded', function() {
    fetch('/api/members/filter-options')
        .then(function(r) { return r.json(); })
        .then(function(opts) {
            var levelSel = document.getElementById('filterLevel');
            (opts.levels || []).forEach(function(v) {
                var o = document.createElement('option');
                o.value = v; o.textContent = v;
                levelSel.appendChild(o);
            });
            var statusSel = document.getElementById('filterStatus');
            (opts.statuses || []).forEach(function(v) {
                var o = document.createElement('option');
                o.value = v; o.textContent = v;
                statusSel.appendChild(o);
            });
            var sourceSel = document.getElementById('filterSource');
            (opts.sources || []).forEach(function(v) {
                var o = document.createElement('option');
                o.value = v; o.textContent = v;
                sourceSel.appendChild(o);
            });
            var staffSel = document.getElementById('filterStaff');
            (opts.staff || []).forEach(function(s) {
                var o = document.createElement('option');
                o.value = s.staff_id; o.textContent = s.name;
                staffSel.appendChild(o);
            });
        });
});

// 编辑/新增/删除后刷新统计和表格
function refreshMembersUI() {
    htmx.ajax('GET', '/api/members/stats', {target: '#memberStats', swap: 'innerHTML'});
    currentPage = 1;
    loadTable();
}

// 监听删除事件 → 刷新统计
document.body.addEventListener('htmx:afterRequest', function(evt) {
    var el = evt.detail.target;
    if (el && el.hasAttribute('hx-delete') && el.getAttribute('hx-delete').indexOf('/api/members/') === 0) {
        if (evt.detail.successful) {
            htmx.ajax('GET', '/api/members/stats', {target: '#memberStats', swap: 'innerHTML'});
        }
    }
});

// ========================
// Block 2: 编辑功能
// ========================

let currentEditMemberId = null;

function saveEditMember(event) {
    event.preventDefault();
    var memberId = currentEditMemberId || document.getElementById('edit_member_id').value;
    if (!memberId) {
        alert('未找到会员信息，请重新打开编辑窗口');
        return;
    }

    var form = document.getElementById('editForm');
    var formData = new FormData(form);
    var btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '保存中...';

    fetch('/api/members/' + memberId, {
        method: 'PUT',
        credentials: 'include',
        body: formData,
    })
    .then(function(r) {
        if (r.ok) return r.json();
        return r.json().then(function(e) { throw new Error(e.detail || '保存失败'); });
    })
    .then(function() {
        document.getElementById('editModal').classList.add('hidden');
        refreshMembersUI();
    })
    .catch(function(err) {
        alert('保存失败: ' + err.message);
    })
    .finally(function() {
        btn.disabled = false;
        btn.textContent = '保存修改';
    });
}

function openEditModal(memberId) {
    currentEditMemberId = memberId;
    // 从 JSON API 获取会员数据
    fetch('/api/members/' + memberId)
        .then(r => r.json())
        .then(data => {
            document.getElementById('edit_name').value = data.name || '';
            document.getElementById('edit_gender').value = data.gender || '男';
            document.getElementById('edit_phone').value = data.phone || '';
            document.getElementById('edit_level').value = data.level || '普通';
            document.getElementById('edit_height').value = data.height || '';
            document.getElementById('edit_weight').value = data.weight || '';
            document.getElementById('edit_source').value = data.source || '';
            document.getElementById('edit_birth_date').value = data.birth_date || '';
            updateEditAge();
            document.getElementById('edit_remark').value = data.remark || '';
            document.getElementById('edit_member_id').value = memberId;

            // 加载跟进员工列表
            var staffSelect = document.getElementById('edit_staff_id');
            staffSelect.innerHTML = '<option value="">—— 不指定 ——</option>';
            fetch('/api/staff/active')
                .then(function(r) { return r.json(); })
                .then(function(staffList) {
                    staffList.forEach(function(s) {
                        var opt = document.createElement('option');
                        opt.value = s.staff_id;
                        opt.textContent = s.name + (s.position ? ' (' + s.position + ')' : '');
                        if (s.staff_id === (data.staff_id || '')) opt.selected = true;
                        staffSelect.appendChild(opt);
                    });
                    // 如果选中的员工不在列表中，额外显示
                    if (data.staff_name && !Array.from(staffSelect.options).some(function(o) { return o.selected && o.value; })) {
                        var opt2 = document.createElement('option');
                        opt2.value = data.staff_id || '';
                        opt2.textContent = data.staff_name + ' (已离职)';
                        opt2.selected = true;
                        staffSelect.appendChild(opt2);
                    }
                    // 同步 staff_name
                    updateStaffName();
                })
                .catch(function() {
                    // 加载失败时回退
                    if (data.staff_name) {
                        var opt = document.createElement('option');
                        opt.value = data.staff_id || '';
                        opt.textContent = data.staff_name;
                        opt.selected = true;
                        staffSelect.appendChild(opt);
                    }
                    updateStaffName();
                });

            // 监听跟进员工选择变更
            staffSelect.onchange = updateStaffName;

            document.getElementById('editModal').classList.remove('hidden');

            // 加载照片
            loadPhoto(memberId);
        });
}

// 打开新增会员对话框
function openAddMemberModal() {
    var modal = document.getElementById('addModal');
    modal.classList.remove('hidden');

    // 加载跟进员工下拉列表
    var sel = document.getElementById('add_staff_id');
    if (sel.options.length <= 1) {
        fetch('/api/staff/active')
            .then(function(r) { return r.json(); })
            .then(function(staffList) {
                sel.innerHTML = '<option value="">—— 不指定 ——</option>';
                staffList.forEach(function(s) {
                    var opt = document.createElement('option');
                    opt.value = s.staff_id;
                    opt.textContent = s.name + (s.position ? ' (' + s.position + ')' : '');
                    sel.appendChild(opt);
                });
            })
            .catch(function() { /* ignore */ });
    }

    // 监听变更 → 同步 staff_name
    sel.onchange = function() {
        var nameInput = document.getElementById('add_staff_name');
        var selectedOpt = sel.options[sel.selectedIndex];
        nameInput.value = selectedOpt && selectedOpt.value ? selectedOpt.textContent.split(' (')[0] : '';
    };
}

// 跟进员工选择 → 同步 staff_name
function updateStaffName() {
    var sel = document.getElementById('edit_staff_id');
    var nameInput = document.getElementById('edit_staff_name');
    if (sel && nameInput) {
        var selectedOpt = sel.options[sel.selectedIndex];
        nameInput.value = selectedOpt && selectedOpt.value ? selectedOpt.textContent.split(' (')[0] : '';
    }
}

// 年龄计算
function calcAge(birthDateValue) {
    if (!birthDateValue) return '';
    var parts = birthDateValue.split('-');
    if (parts.length !== 3) return '';
    var bd = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    var today = new Date();
    var age = today.getFullYear() - bd.getFullYear();
    var m = today.getMonth() - bd.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < bd.getDate())) age--;
    return age >= 0 ? age + '岁' : '';
}

function updateEditAge() {
    document.getElementById('edit_age').value = calcAge(document.getElementById('edit_birth_date').value);
}

function updateAddAge() {
    document.getElementById('add_age').value = calcAge(document.getElementById('add_birth_date').value);
}

// ════════════════════════════════════════════
// 照片功能
// ════════════════════════════════════════════

function loadPhoto(memberId) {
    fetch('/api/members/' + memberId + '/photo')
        .then(r => {
            if (r.ok) return r.blob();
            throw new Error('no photo');
        })
        .then(blob => {
            const url = URL.createObjectURL(blob);
            const img = document.getElementById('photoPreview');
            img.src = url;
            img.classList.remove('hidden');
            document.getElementById('photoPlaceholder').classList.add('hidden');
            document.getElementById('deletePhotoBtn').classList.remove('hidden');
        })
        .catch(() => {
            // 无照片，显示占位
            document.getElementById('photoPreview').src = '';
            document.getElementById('photoPreview').classList.add('hidden');
            document.getElementById('photoPlaceholder').classList.remove('hidden');
            document.getElementById('deletePhotoBtn').classList.add('hidden');
        });
}

function uploadPhoto(input) {
    const file = input.files[0];
    if (!file) return;

    // 验证文件大小 (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
        alert('照片不能超过 5MB');
        input.value = '';
        return;
    }

    // 验证文件类型
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
        alert('仅支持 JPEG/PNG/WebP 格式');
        input.value = '';
        return;
    }

    const progress = document.getElementById('uploadProgress');
    progress.classList.remove('hidden');
    progress.textContent = '⏳ 上传中...';

    const formData = new FormData();
    formData.append('file', file);

    fetch('/api/members/' + currentEditMemberId + '/photo', {
        method: 'POST',
        body: formData,
    })
    .then(r => r.ok ? r.json() : r.json().then(j => { throw new Error(j.detail || '上传失败'); }))
    .then(res => {
        if (res.success) {
            progress.textContent = '✅ 上传成功';
            // 刷新照片显示
            loadPhoto(currentEditMemberId);
            setTimeout(() => progress.classList.add('hidden'), 2000);
        }
    })
    .catch(err => {
        progress.textContent = '❌ ' + err.message;
        setTimeout(() => progress.classList.add('hidden'), 3000);
    });

    input.value = '';
}

function deletePhoto() {
    if (!confirm('确认删除此会员的照片？')) return;

    const progress = document.getElementById('uploadProgress');
    progress.classList.remove('hidden');
    progress.textContent = '⏳ 删除中...';

    fetch('/api/members/' + currentEditMemberId + '/photo', {
        method: 'DELETE',
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            progress.textContent = '✅ 已删除';
            // 刷新照片显示
            document.getElementById('photoPreview').src = '';
            document.getElementById('photoPreview').classList.add('hidden');
            document.getElementById('photoPlaceholder').classList.remove('hidden');
            document.getElementById('deletePhotoBtn').classList.add('hidden');
            setTimeout(() => progress.classList.add('hidden'), 2000);
        }
    });
}

// ════════════════════════════════════════════
// 摄像头拍照
// ════════════════════════════════════════════

var cameraStream = null;

function openCamera() {
    var modal = document.getElementById('cameraModal');
    var video = document.getElementById('cameraVideo');
    var canvas = document.getElementById('cameraCanvas');
    var captureBtn = document.getElementById('cameraCaptureBtn');
    var retakeBtn = document.getElementById('cameraRetakeBtn');
    var statusEl = document.getElementById('cameraStatus');

    // 重置状态
    canvas.classList.add('hidden');
    captureBtn.classList.remove('hidden');
    retakeBtn.classList.add('hidden');
    statusEl.classList.add('hidden');
    statusEl.className = 'text-sm text-center hidden mb-3';
    video.style.display = 'block';

    modal.classList.remove('hidden');

    // 启动摄像头
    navigator.mediaDevices.getUserMedia({
        video: {
            width: { ideal: 640 },
            height: { ideal: 480 },
            facingMode: 'environment'
        },
        audio: false
    })
    .then(function(stream) {
        cameraStream = stream;
        video.srcObject = stream;
    })
    .catch(function(err) {
        statusEl.classList.remove('hidden');
        statusEl.className = 'text-sm text-center text-red-500 mb-3';
        if (err.name === 'NotAllowedError') {
            statusEl.textContent = '❌ 摄像头权限被拒绝，请在浏览器设置中允许摄像头访问';
        } else if (err.name === 'NotFoundError') {
            statusEl.textContent = '❌ 未检测到摄像头设备';
        } else {
            statusEl.textContent = '❌ 摄像头启动失败: ' + err.message;
        }
    });
}

function capturePhoto() {
    var video = document.getElementById('cameraVideo');
    var canvas = document.getElementById('cameraCanvas');
    var captureBtn = document.getElementById('cameraCaptureBtn');
    var retakeBtn = document.getElementById('cameraRetakeBtn');
    var statusEl = document.getElementById('cameraStatus');

    // canvas 匹配视频尺寸
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    // 截取当前帧
    var ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // 显示拍照结果，隐藏视频
    canvas.classList.remove('hidden');
    video.style.display = 'none';
    captureBtn.classList.add('hidden');
    retakeBtn.classList.remove('hidden');

    // 自动上传
    statusEl.classList.remove('hidden');
    statusEl.className = 'text-sm text-center text-blue-500 mb-3';
    statusEl.textContent = '⏳ 上传中...';

    canvas.toBlob(function(blob) {
        var formData = new FormData();
        formData.append('file', blob, currentEditMemberId + '.jpg');

        fetch('/api/members/' + currentEditMemberId + '/photo', {
            method: 'POST',
            body: formData,
        })
        .then(function(r) {
            return r.ok ? r.json() : r.json().then(function(j) { throw new Error(j.detail || '上传失败'); });
        })
        .then(function(res) {
            if (res.success) {
                statusEl.className = 'text-sm text-center text-green-600 mb-3';
                statusEl.textContent = '✅ 拍照上传成功！';
                // 刷新编辑弹窗的照片
                loadPhoto(currentEditMemberId);
                // 2秒后自动关闭
                setTimeout(function() {
                    closeCamera();
                }, 2000);
            }
        })
        .catch(function(err) {
            statusEl.className = 'text-sm text-center text-red-500 mb-3';
            statusEl.textContent = '❌ 上传失败: ' + err.message;
        });
    }, 'image/jpeg', 0.9);
}

function retakePhoto() {
    var video = document.getElementById('cameraVideo');
    var canvas = document.getElementById('cameraCanvas');
    var captureBtn = document.getElementById('cameraCaptureBtn');
    var retakeBtn = document.getElementById('cameraRetakeBtn');
    var statusEl = document.getElementById('cameraStatus');

    canvas.classList.add('hidden');
    video.style.display = 'block';
    captureBtn.classList.remove('hidden');
    retakeBtn.classList.add('hidden');
    statusEl.classList.add('hidden');
    statusEl.className = 'text-sm text-center hidden mb-3';
}

function closeCamera() {
    // 停止摄像头
    if (cameraStream) {
        cameraStream.getTracks().forEach(function(t) { t.stop(); });
        cameraStream = null;
    }

    var video = document.getElementById('cameraVideo');
    video.srcObject = null;
    video.style.display = 'block';

    document.getElementById('cameraModal').classList.add('hidden');
}

// ========================
// Block 3: 售卡功能
// ========================

// ── 卡产品缓存 ──
var cardProducts = [];

function openSellCardModal(memberId, memberName) {
    document.getElementById('sellCardMemberId').value = memberId;
    document.getElementById('sellCardMemberName').value = memberName;
    document.getElementById('sellCardPrice').value = '0';
    document.getElementById('sellCardStart').value = '';
    document.getElementById('sellCardResult').classList.add('hidden');
    document.getElementById('sellCardProductInfo').classList.add('hidden');

    // 加载卡产品列表
    var sel = document.getElementById('sellCardProduct');
    sel.innerHTML = '<option value="">加载中...</option>';
    sel.disabled = true;
    fetch('/api/membership-cards/products/list')
        .then(function(r) { return r.json(); })
        .then(function(prods) {
            cardProducts = prods;
            sel.innerHTML = '<option value="">— 请选择 —</option>';
            prods.forEach(function(p) {
                var label = p.name || p.card_id;
                sel.innerHTML += '<option value="' + p.card_id + '">' + label + ' (' + p.card_type + ' ¥' + p.price + ')</option>';
            });
            sel.disabled = false;
        });
    document.getElementById('sellCardModal').classList.remove('hidden');
}

function onSellCardProductChange() {
    var pid = document.getElementById('sellCardProduct').value;
    var infoEl = document.getElementById('sellCardProductInfo');
    var priceEl = document.getElementById('sellCardPrice');
    if (!pid) { infoEl.classList.add('hidden'); return; }

    var p = cardProducts.find(function(x) { return x.card_id === pid; });
    if (!p) { infoEl.classList.add('hidden'); return; }

    document.getElementById('sellCardTypeDisplay').textContent = p.card_type;
    document.getElementById('sellCardDurationDisplay').textContent = p.duration_days > 0 ? p.duration_days + '天' : '无期限';
    if (p.card_type === '次卡') {
        document.getElementById('sellCardClassesDisplay').innerHTML = '次数：' + p.total_classes + '次';
    } else {
        document.getElementById('sellCardClassesDisplay').innerHTML = '';
    }

    // 自动填入售价（可改）
    priceEl.value = p.price;

    infoEl.classList.remove('hidden');
}

function submitSellCard() {
    var pid = document.getElementById('sellCardProduct').value;
    if (!pid) { alert('请选择卡产品'); return; }

    var btn = document.querySelector('#sellCardModal .bg-green-600');
    var resultEl = document.getElementById('sellCardResult');
    btn.disabled = true;
    btn.textContent = '保存中...';
    resultEl.classList.add('hidden');

    var params = new URLSearchParams();
    params.set('member_id', document.getElementById('sellCardMemberId').value);
    params.set('member_name', document.getElementById('sellCardMemberName').value);
    params.set('product_id', pid);
    params.set('price', document.getElementById('sellCardPrice').value || '0');
    params.set('start_date', document.getElementById('sellCardStart').value || '');

    fetch('/api/membership-cards/sell', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params.toString()
    })
    .then(function(r) {
        if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || '售卡失败'); });
        return r.json();
    })
    .then(function() {
        resultEl.classList.remove('hidden');
        resultEl.className = 'text-sm text-center py-2 rounded-lg bg-green-50 text-green-700';
        resultEl.textContent = '✅ ' + document.getElementById('sellCardMemberName').value + ' 售卡成功！';
        // 修复：恢复按钮状态 + 改用 htmx.ajax 刷新
        btn.disabled = false;
        btn.textContent = '💳 确认售卡';
        refreshMembersUI();
        setTimeout(function() {
            document.getElementById('sellCardModal').classList.add('hidden');
        }, 1500);
    })
    .catch(function(e) {
        resultEl.classList.remove('hidden');
        resultEl.className = 'text-sm text-center py-2 rounded-lg bg-red-50 text-red-700';
        resultEl.textContent = '❌ ' + e.message;
        btn.disabled = false;
        btn.textContent = '💳 确认售卡';
    });
}
