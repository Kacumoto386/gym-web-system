// 切换 Tab 时刷新已售课程包数据
document.addEventListener('DOMContentLoaded', function() {
    // 调试：检查已售课程包数据是否在 DOM 中
    const area = document.getElementById('memberPackageTableArea');
    if (area) {
        const htmlLen = area.innerHTML.length;
        const hasData = area.innerHTML.indexOf('鼠小弟') >= 0;
        const hasTable = area.innerHTML.indexOf('<table') >= 0;
        console.log('memberPackageTableArea:', htmlLen, 'chars, hasData:', hasData, 'hasTable:', hasTable);
        // 在页面上显示调试信息
        const debug = document.createElement('div');
        debug.style.cssText = 'position:fixed;bottom:10px;right:10px;background:#333;color:#0f0;padding:8px 12px;border-radius:6px;font-size:12px;z-index:9999;';
        debug.textContent = '已售:' + htmlLen + 'ch ' + (hasData ? '✅' : '❌') + ' ' + (hasTable ? '表格' : '⛔');
        document.body.appendChild(debug);
    } else {
        console.error('memberPackageTableArea NOT FOUND!');
    }
});

let editingProductId = null;

// ═══════════════════════════
// Tab 切换
// ═══════════════════════════
function switchTab(tab) {
    // 强制显示/隐藏 Tab 内容
    document.getElementById('tabProductsContent').style.display = (tab === 'products' ? '' : 'none');
    document.getElementById('tabMemberContent').style.display = (tab === 'member' ? '' : 'none');
    document.getElementById('tabMonthlyPassContent').style.display = (tab === 'monthlypass' ? '' : 'none');
    // Tab 按钮样式
    ['tabProducts','tabMember','tabMonthlyPass'].forEach(id => {
        const btn = document.getElementById(id);
        const isActive = (id === 'tab' + tab.charAt(0).toUpperCase() + tab.slice(1));
        btn.classList.toggle('text-blue-600', isActive);
        btn.classList.toggle('border-blue-600', isActive);
        btn.classList.toggle('text-gray-500', !isActive);
        btn.classList.toggle('border-transparent', !isActive);
    });
    if (tab === 'member') {
        // 数据已在服务端渲染好，不需要额外请求
    }
    if (tab === 'products') {
        // 使用 fetch 而非 HTMX 避免任何缓存问题
        fetch('/api/packages/products/table?_t=' + Date.now())
            .then(r => r.text())
            .then(html => {
                document.getElementById('productTableArea').innerHTML = html;
            });
    }
}

// ═══════════════════════════
// 产品管理
// ═══════════════════════════
function openAddProduct() {
    editingProductId = null;
    document.getElementById('productModalTitle').textContent = '新建课程包';
    document.getElementById('productSaveBtn').textContent = '保存';
    document.getElementById('productForm').setAttribute('hx-post', '/api/packages/products');
    document.getElementById('productForm').reset();
    document.getElementById('productModal').classList.remove('hidden');
    setTimeout(() => loadCoursePicker(), 100);
}

function openEditProduct(packageId) {
    editingProductId = packageId;
    document.getElementById('productModalTitle').textContent = '编辑课程包';
    document.getElementById('productSaveBtn').textContent = '保存修改';
    document.getElementById('productForm').setAttribute('hx-put', '/api/packages/products/' + packageId);

    fetch('/api/packages/products/' + packageId)
        .then(r => r.json())
        .then(d => {
            document.querySelector('input[name="package_name"]').value = d.package_name || '';
            document.querySelector('select[name="package_type"]').value = d.package_type || '计次打包';
            document.querySelector('input[name="total_count"]').value = d.total_count || 0;
            document.querySelector('input[name="standard_price"]').value = d.standard_price || 0;
            document.querySelector('input[name="discount_price"]').value = d.discount_price || 0;
            document.querySelector('input[name="valid_days"]').value = d.valid_days || 30;
            document.querySelector('textarea[name="remark"]').value = d.remark || '';
            document.getElementById('productModal').classList.remove('hidden');
            loadCoursePickerWithSelection((d.included_courses || '').split(','));
        });
}

function closeProductModal() {
    document.getElementById('productModal').classList.add('hidden');
}

// 不限次数 ↔ 计次打包：切换时禁用/启用次数输入
function toggleCountField(sel) {
    var field = document.getElementById('countField');
    var input = field.querySelector('input[name="total_count"]');
    if (sel.value === '不限次数') {
        input.disabled = true;
        input.value = 0;
        field.classList.add('opacity-40');
    } else {
        input.disabled = false;
        field.classList.remove('opacity-40');
    }
}

function toggleProductStatus(packageId) {
    fetch('/api/packages/products/' + packageId + '/toggle-status', { method: 'POST' })
        .then(r => r.json())
        .then(() => htmx.ajax('GET', '/api/packages/products/table?_t=' + Date.now(), { target: '#productTableArea', swap: 'innerHTML' }));
}

// ═══════════════════════════
// 已售课程包搜索
// ═══════════════════════════
function searchMemberPackages() {
    const kw = document.getElementById('mpKeyword').value;
    const st = document.getElementById('mpStatus').value;
    const params = [];
    if (kw) params.push('keyword=' + encodeURIComponent(kw));
    if (st) params.push('status=' + encodeURIComponent(st));
    params.push('_t=' + Date.now());
    htmx.ajax('GET', '/api/packages/member-packages?' + params.join('&'), { target: '#memberPackageTableArea' });
}

// ═══════════════════════════
// 课程多选卡片
// ═══════════════════════════
let allCourses = [];

function loadCoursePicker() {
    fetch('/api/courses?status=上架')
        .then(r => r.json())
        .then(courses => {
            allCourses = courses;
            renderCoursePicker(allCourses);
        })
        .catch(() => document.getElementById('courseSelectContainer').innerHTML = '<div class="text-red-400 text-sm py-2">加载课程失败</div>');
}

function renderCoursePicker(courses) {
    const preselect = window._preselectCourseIds || [];
    const container = document.getElementById('courseSelectContainer');
    let html = '<div class="grid grid-cols-2 sm:grid-cols-3 gap-1.5 max-h-48 overflow-y-auto p-1.5 border rounded-lg bg-gray-50/50">';
    courses.forEach(c => {
        const checked = preselect.includes(c.course_id) ? 'checked' : '';
        const typeTag = getCourseTypeTag(c);
        html += `
            <label class="flex items-center gap-2 px-2.5 py-1.5 rounded cursor-pointer transition-colors
                          ${checked ? 'bg-blue-100 border border-blue-300' : 'bg-white border border-gray-200 hover:bg-gray-100'}">
                <input type="checkbox" name="included_courses" value="${c.course_id}"
                       onchange="toggleCourseCard(this)" ${checked}>
                <span class="text-sm font-medium truncate">${c.name || c.course_id || ''}</span>
                ${typeTag}
            </label>`;
    });
    html += '</div><p class="text-xs text-gray-400 mt-1">✓ 勾选的课程将包含在课程包中</p>';
    container.innerHTML = html;
    window._preselectCourseIds = null;
}

function getCourseTypeTag(c) {
    const ct = (c.course_type || '').trim();
    if (ct.includes('私教') || ct.includes('小班')) return '<span class="text-xs text-orange-500 shrink-0">私教</span>';
    if (ct.includes('团课') || ct.includes('大班')) return '<span class="text-xs text-purple-500 shrink-0">团课</span>';
    return '';
}

function toggleCourseCard(cb) {
    const label = cb.closest('label');
    if (cb.checked) {
        label.classList.remove('bg-white', 'border-gray-200', 'hover:bg-gray-100');
        label.classList.add('bg-blue-100', 'border-blue-300');
    } else {
        label.classList.remove('bg-blue-100', 'border-blue-300');
        label.classList.add('bg-white', 'border-gray-200', 'hover:bg-gray-100');
    }
}

function loadCoursePickerWithSelection(selectedIds) {
    fetch('/api/courses?status=上架')
        .then(r => r.json())
        .then(courses => {
            allCourses = courses;
            window._preselectCourseIds = selectedIds.filter(id => id);
            renderCoursePicker(allCourses);
        });
}

// ═══════════════════════════
// 添加课程弹窗
// ═══════════════════════════
function openAddCourse(packageId, packageName) {
    const overlay = document.createElement('div');
    overlay.id = 'addCourseOverlay';
    overlay.className = 'fixed inset-0 bg-black/40 z-50 flex items-center justify-center';
    overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };

    fetch('/api/courses?status=上架')
        .then(r => r.json())
        .then(courses => {
            const opts = courses.map(c =>
                `<option value="${c.course_id}">${c.name || c.course_id} (${c.course_type || ''})</option>`
            ).join('');
            overlay.innerHTML = `
                <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6" onclick="event.stopPropagation()">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-base font-semibold">＋ 添加课程</h3>
                        <button onclick="document.getElementById('addCourseOverlay').remove()"
                                class="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
                    </div>
                    <p class="text-sm text-gray-500 mb-3">为「${packageName}」添加课程</p>
                    <form hx-post="/api/packages/products/${packageId}/courses"
                          hx-target="#productTableArea"
                          hx-on::after-request="document.getElementById('addCourseOverlay').remove()">
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-1">选择课程</label>
                            <select name="course_id" class="w-full px-3 py-2.5 border rounded-lg text-sm">
                                ${opts}
                            </select>
                        </div>
                        <div class="flex justify-end gap-3">
                            <button type="button" onclick="document.getElementById('addCourseOverlay').remove()"
                                    class="px-4 py-2 text-sm text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200">取消</button>
                            <button type="submit"
                                    class="px-4 py-2 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700">添加</button>
                        </div>
                    </form>
                </div>`;
            document.body.appendChild(overlay);
        });
}

// 初始化：替换 htmx 加载为 JS 加载
// 页面初始化
document.addEventListener('DOMContentLoaded', function() {
    loadCoursePicker();
});

// 提交前把 checkbox 拼成逗号字符串
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('productForm');
    if (form) {
        form.addEventListener('htmx:configRequest', function(evt) {
            const checks = document.querySelectorAll('#courseSelectContainer input[name="included_courses"]:checked');
            const ids = Array.from(checks).map(cb => cb.value);
            const params = evt.detail.parameters;
            if (params.hasOwnProperty('included_courses')) delete params['included_courses'];
            if (ids.length > 0) params['included_courses'] = ids.join(',');
        });
    }
});

// ═══════════════════════════
// 包月管理 CRUD
// ═══════════════════════════
let mpMemberSearchTimer = null;
let mpSelectedMemberId = '';
let mpSelectedMemberName = '';

function searchMemberMP() {
    clearTimeout(mpMemberSearchTimer);
    const q = document.getElementById('mpMemberSearch').value.trim();
    if (!q) {
        document.getElementById('mpMemberResults').classList.add('hidden');
        mpSelectedMemberId = '';
        mpSelectedMemberName = '';
        document.getElementById('mpMemberName').value = '';
        return;
    }
    mpMemberSearchTimer = setTimeout(() => {
        fetch('/api/members/search-json?q=' + encodeURIComponent(q))
            .then(r => r.json())
            .then(list => {
                const el = document.getElementById('mpMemberResults');
                if (!list || list.length === 0) {
                    el.classList.add('hidden');
                    return;
                }
                let html = '';
                list.forEach(m => {
                    html += '<div class="px-3 py-2 hover:bg-blue-50 cursor-pointer border-b text-sm" onclick="selectMemberMP(\'' + m.member_id + '\',\'' + m.name.replace(/'/g, "\\'") + '\')">'
                        + '<span class="font-medium">' + m.name + '</span> '
                        + '<span class="text-gray-400 text-xs">' + (m.phone || '') + ' ' + (m.card_type || '') + '</span>'
                        + '</div>';
                });
                el.innerHTML = html;
                el.classList.remove('hidden');
            });
    }, 200);
}

function selectMemberMP(id, name) {
    mpSelectedMemberId = id;
    mpSelectedMemberName = name;
    document.getElementById('mpMemberSearch').value = id;
    document.getElementById('mpMemberName').value = name;
    document.getElementById('mpMemberResults').classList.add('hidden');
}

function openAddMonthlyPass() {
    mpSelectedMemberId = '';
    mpSelectedMemberName = '';
    document.getElementById('mpEditPassId').value = '';
    document.getElementById('mpModalTitle').textContent = '新建包月';
    document.getElementById('mpMemberSearch').value = '';
    document.getElementById('mpMemberName').value = '';
    document.getElementById('mpPassName').value = '';
    document.getElementById('mpPassType').value = 'group';
    document.getElementById('mpPrice').value = 0;
    document.getElementById('mpCourseNames').value = '';
    document.getElementById('mpValidFrom').value = '';
    document.getElementById('mpValidUntil').value = '';
    document.getElementById('mpPurchaseDate').value = new Date().toISOString().split('T')[0];
    document.getElementById('mpStatus').value = '正常';
    document.getElementById('mpRemark').value = '';
    document.getElementById('monthlyPassModal').classList.remove('hidden');
}

function closeMonthlyPassModal() {
    document.getElementById('monthlyPassModal').classList.add('hidden');
}

function openEditMonthlyPass(passId) {
    document.getElementById('mpEditPassId').value = passId;
    document.getElementById('mpModalTitle').textContent = '编辑包月';

    fetch('/api/packages/monthly-passes/' + passId)
        .then(r => {
            if (!r.ok) throw new Error('获取数据失败');
            return r.json();
        })
        .then(d => {
            mpSelectedMemberId = d.member_id || '';
            mpSelectedMemberName = d.member_name || '';
            document.getElementById('mpMemberSearch').value = d.member_id || '';
            document.getElementById('mpMemberName').value = d.member_name || '';
            document.getElementById('mpPassName').value = d.pass_name || '';
            document.getElementById('mpPassType').value = d.pass_type || 'group';
            document.getElementById('mpPrice').value = d.price || 0;
            document.getElementById('mpCourseNames').value = d.course_names || '';
            document.getElementById('mpValidFrom').value = d.valid_from || '';
            document.getElementById('mpValidUntil').value = d.valid_until || '';
            document.getElementById('mpPurchaseDate').value = d.purchase_date || new Date().toISOString().split('T')[0];
            document.getElementById('mpStatus').value = d.status || '正常';
            document.getElementById('mpRemark').value = d.remark || '';
            document.getElementById('monthlyPassModal').classList.remove('hidden');
        })
        .catch(err => alert(err.message));
}

function saveMonthlyPass() {
    const passId = document.getElementById('mpEditPassId').value;
    const isEdit = !!passId;
    const memberSearch = document.getElementById('mpMemberSearch').value.trim();

    if (!mpSelectedMemberId && memberSearch) {
        mpSelectedMemberId = memberSearch;
    }
    if (!mpSelectedMemberId) {
        alert('请选择会员');
        return;
    }
    const passName = document.getElementById('mpPassName').value.trim();
    if (!passName) {
        alert('请输入名称');
        return;
    }

    const data = {
        member_id: mpSelectedMemberId,
        member_name: mpSelectedMemberName || document.getElementById('mpMemberName').value || mpSelectedMemberId,
        pass_name: passName,
        pass_type: document.getElementById('mpPassType').value,
        price: parseFloat(document.getElementById('mpPrice').value) || 0,
        course_names: document.getElementById('mpCourseNames').value.trim(),
        included_courses: '',
        valid_from: document.getElementById('mpValidFrom').value,
        valid_until: document.getElementById('mpValidUntil').value,
        purchase_date: document.getElementById('mpPurchaseDate').value,
        status: document.getElementById('mpStatus').value,
        remark: document.getElementById('mpRemark').value
    };

    const url = isEdit ? '/api/packages/monthly-passes/' + passId : '/api/packages/monthly-passes';
    const method = isEdit ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(r => {
        if (!r.ok) return r.json().then(j => { throw new Error(j.detail || '保存失败'); });
        return r.json();
    })
    .then(result => {
        closeMonthlyPassModal();
        // Refresh table
        fetch('/api/packages/monthly-passes/table?_t=' + Date.now())
            .then(r => r.text())
            .then(html => { document.getElementById('monthlyPassTable').innerHTML = html; });
    })
    .catch(err => alert(err.message));
}