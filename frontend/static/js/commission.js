let currentEditTierId = null;

// ────────── Tab 切换 ──────────
function switchTab(tab) {
    document.getElementById('rulesSection').classList.toggle('hidden', tab !== 'rules');
    document.getElementById('calcSection').classList.toggle('hidden', tab !== 'calc');
    const cls = (t, a) => `px-4 py-2 text-sm rounded-lg ${t === a ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600 hover:bg-gray-300'}`;
    document.getElementById('tabRules').className = cls(tab, 'rules');
    document.getElementById('tabCalc').className = cls(tab, 'calc');
    if (tab === 'calc') {
        loadStaffList();
        // 设置默认年月
        const now = new Date();
        document.getElementById('calcYear').value = now.getFullYear();
        document.getElementById('calcMonth').value = now.getMonth(); // 0-indexed, select is 1-indexed
        // 修正：month 选择框是 1-12
        const monthSelect = document.getElementById('calcMonth');
        for (let i = 0; i < monthSelect.options.length; i++) {
            if (parseInt(monthSelect.options[i].value) === (now.getMonth() + 1)) {
                monthSelect.selectedIndex = i;
                break;
            }
        }
    }
}

// ────────── 梯度规则表单提交 ──────────
document.getElementById('tierForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const editId = document.getElementById('editTierId').value;
    const data = {
        type: document.getElementById('tierType').value,
        min_amount: parseFloat(document.getElementById('tierMin').value) || 0,
        max_amount: parseFloat(document.getElementById('tierMax').value) || 0,
        rate: parseFloat(document.getElementById('tierRate').value) || 0,
    };

    let url = '/api/commission/tiers';
    let method = 'POST';
    if (editId) {
        url = `/api/commission/tiers/${editId}`;
        method = 'PUT';
    }

    fetch(url, {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)})
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                document.getElementById('addTierModal').classList.add('hidden');
                htmx.trigger('#tierTable', 'htmx:load');
                document.getElementById('tierTable').innerHTML = '<div class="text-center py-8 text-gray-400">加载中...</div>';
                htmx.process(document.getElementById('tierTable'));
                htmx.trigger('#tierTable', 'load');
            }
        });
});

function editTier(tierId, type, minAmt, maxAmt, rate) {
    document.getElementById('editTierId').value = tierId;
    document.getElementById('tierType').value = type;
    document.getElementById('tierMin').value = minAmt;
    document.getElementById('tierMax').value = maxAmt;
    document.getElementById('tierRate').value = rate;
    document.getElementById('tierModalTitle').textContent = '编辑提成规则';
    document.getElementById('addTierModal').classList.remove('hidden');
}

// ────────── 佣金计算 ──────────
function loadStaffList() {
    const sel = document.getElementById('calcStaff');
    if (sel.options.length > 1) return;
    fetch('/api/commission/staff-list')
        .then(r => r.json())
        .then(list => {
            list.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.staff_id;
                opt.textContent = `${s.name} (${s.position || '无岗位'})`;
                sel.appendChild(opt);
            });
        });
}

function calculateCommission() {
    const staffId = document.getElementById('calcStaff').value;
    const year = document.getElementById('calcYear').value;
    const month = document.getElementById('calcMonth').value;

    if (!staffId) { alert('请选择员工'); return; }
    if (!year || !month) { alert('请选择年月'); return; }

    fetch(`/api/commission/calculate?staff_id=${staffId}&year=${year}&month=${month}`)
        .then(r => r.ok ? r.json() : r.json().then(j => { throw new Error(j.detail || '计算失败'); }))
        .then(data => {
            renderCalcResult(data);
        })
        .catch(err => {
            alert(err.message);
        });
}

function renderCalcResult(data) {
    const el = document.getElementById('calcResult');
    el.classList.remove('hidden');

    const saleDetails = data.sale.details || [];
    const saleRows = saleDetails.length > 0 ? saleDetails.map(d => `
        <tr class="border-b border-gray-50 text-sm">
            <td class="px-3 py-2 text-gray-500">${d.range}</td>
            <td class="px-3 py-2">${d.rate}%</td>
            <td class="px-3 py-2">¥${d.contrib.toFixed(2)}</td>
            <td class="px-3 py-2 font-medium">¥${d.commission.toFixed(2)}</td>
        </tr>
    `).join('') : '<tr><td colspan="4" class="px-3 py-4 text-center text-gray-400 text-sm">本月无售课记录</td></tr>';

    el.innerHTML = `
    <div class="space-y-4">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4">
            <div class="flex justify-between items-center">
                <div>
                    <span class="text-lg font-semibold text-gray-800">${data.staff.name}</span>
                    <span class="text-sm text-gray-400 ml-2">${data.staff.position || ''}</span>
                </div>
                <span class="text-sm text-gray-500">${data.period}</span>
            </div>
        </div>

        <!-- 汇总卡片 -->
        <div class="grid grid-cols-3 gap-4">
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
                <div class="text-xs text-gray-400 mb-1">售课提成</div>
                <div class="text-xl font-semibold text-blue-600">¥${data.sale.commission.toFixed(2)}</div>
                <div class="text-xs text-gray-400">${data.sale.count} 笔 / ¥${data.sale.total_amount.toFixed(2)}</div>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
                <div class="text-xs text-gray-400 mb-1">上课提成</div>
                <div class="text-xl font-semibold text-green-600">¥${data.class.commission.toFixed(2)}</div>
                <div class="text-xs text-gray-400">${data.class.count} 节 / 费率 ${data.class.rate}%</div>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
                <div class="text-xs text-gray-400 mb-1">总提成</div>
                <div class="text-xl font-semibold text-purple-600">¥${data.total_commission.toFixed(2)}</div>
            </div>
        </div>

        <!-- 售课提成明细 -->
        <div class="bg-white rounded-xl shadow-sm border border-gray-100">
            <div class="px-4 py-3 border-b border-gray-100 text-sm font-medium text-gray-700">售课提成明细（分段累进）</div>
            <table class="w-full">
                <thead class="bg-gray-50 text-left text-xs text-gray-500 uppercase">
                    <tr><th class="px-3 py-2">金额区间</th><th class="px-3 py-2">比例</th><th class="px-3 py-2">段内金额</th><th class="px-3 py-2">提成</th></tr>
                </thead>
                <tbody>${saleRows}</tbody>
            </table>
        </div>
    </div>`;
}

// re-bind HTMX events after tier table update
document.body.addEventListener('htmx:afterSwap', function(evt) {
    if (evt.detail.target?.id === 'tierTable') {
        // tier table 已更新
    }
});
