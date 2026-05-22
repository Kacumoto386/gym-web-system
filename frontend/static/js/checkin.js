// ════════════════════════════════════════════
// 全局状态
// ════════════════════════════════════════════

let selectedMember = null;
let memberCards = [];
let searchTimer = null;
let currentMode = 'manual';  // 'manual' or 'scan'

// ════════════════════════════════════════════
// 模式切换
// ════════════════════════════════════════════

function switchCheckinMode(mode) {
    currentMode = mode;
    document.getElementById('modeManualBtn').className = mode === 'manual'
        ? 'px-3 py-2 rounded-lg text-sm bg-blue-600 text-white'
        : 'px-3 py-2 rounded-lg text-sm bg-gray-200 text-gray-600 hover:bg-gray-300';
    document.getElementById('modeScanBtn').className = mode === 'scan'
        ? 'px-3 py-2 rounded-lg text-sm bg-blue-600 text-white'
        : 'px-3 py-2 rounded-lg text-sm bg-gray-200 text-gray-600 hover:bg-gray-300';

    // 模式切换时不清除已选会员
}

// ════════════════════════════════════════════
// 弹窗控制
// ════════════════════════════════════════════

function openCheckinModal() {
    document.getElementById('checkinModal').classList.remove('hidden');
    // 默认手动模式
    document.getElementById('manualSearchSection').classList.remove('hidden');
    document.getElementById('scanSection').classList.add('hidden');
    currentMode = 'manual';
    loadStaffList();
    loadDefaultOperator();
}

function openScanCheckinModal() {
    // 直接打开扫码模式
    document.getElementById('checkinModal').classList.remove('hidden');
    document.getElementById('manualSearchSection').classList.add('hidden');
    document.getElementById('scanSection').classList.remove('hidden');
    currentMode = 'scan';
    switchCheckinMode('scan');
    loadStaffList();
    loadDefaultOperator();
    setTimeout(() => document.getElementById('scanInput').focus(), 100);
}

function closeCheckinModal() {
    document.getElementById('checkinModal').classList.add('hidden');
    resetForm();
}

function resetForm() {
    selectedMember = null;
    memberCards = [];
    document.getElementById('memberSearchInput').value = '';
    document.getElementById('memberSearchResults').classList.add('hidden');
    document.getElementById('scanInput').value = '';
    document.getElementById('scanResult').classList.add('hidden');
    document.getElementById('selectedMemberInfo').classList.add('hidden');
    document.getElementById('selectedMemberIdInput').value = '';
    document.getElementById('selectedMemberNameInput').value = '';
    document.getElementById('cardSection').classList.add('hidden');
    document.getElementById('consumeSection').classList.add('hidden');
    document.getElementById('cardSelect').innerHTML = '<option value="">—— 不核销会籍卡 ——</option>';
    document.getElementById('deductPreview').classList.add('hidden');
    document.getElementById('checkinType').value = '核销';
    document.getElementById('cardType').value = '';
    document.getElementById('staffFollowup').value = '';
    document.getElementById('submitBtn').disabled = true;
    // 清理自定义输入框
    const oldQf = document.getElementById('consumeQuantityField');
    if (oldQf) oldQf.remove();
    const oldAf = document.getElementById('consumeAmountField');
    if (oldAf) oldAf.remove();
}

// ════════════════════════════════════════════
// 扫码/刷卡模式
// ════════════════════════════════════════════

function scanMember() {
    const input = document.getElementById('scanInput').value.trim();
    if (!input) { alert('请输入手机号或会员编号'); return; }

    const resultEl = document.getElementById('scanResult');
    resultEl.innerHTML = '<div class="text-center py-2 text-gray-400 text-sm">查询中...</div>';
    resultEl.classList.remove('hidden');

    // 直接用会员搜索 JSON 查询
    fetch(`/api/members/search-json?q=${encodeURIComponent(input)}`)
        .then(r => r.json())
        .then(members => {
            if (members.length === 0) {
                resultEl.innerHTML = '<div class="text-center py-3 text-red-500 text-sm bg-red-50 rounded-lg">未找到匹配的会员</div>';
                return;
            }
            if (members.length > 1) {
                // 多结果展示
                resultEl.innerHTML = '<div class="text-xs text-gray-500 mb-1">找到多个匹配，请点击选择：</div>' +
                    members.map(m => `<div class="px-3 py-2 hover:bg-blue-50 cursor-pointer text-sm border-b border-gray-50 flex justify-between"
                                          onclick="selectMember('${m.member_id}'); document.getElementById('scanResult').classList.add('hidden');">
                        <span>${m.name} (${m.member_id})</span>
                        <span class="text-gray-400">${m.phone || ''}</span>
                    </div>`).join('');
                return;
            }
            // 唯一匹配 → 直接选择
            selectMember(members[0].member_id);
            resultEl.classList.add('hidden');
            document.getElementById('scanInput').value = members[0].name;
        });
}

// ════════════════════════════════════════════
// 会员搜索（手动模式）
// ════════════════════════════════════════════

function searchMember(keyword) {
    clearTimeout(searchTimer);
    const resultsEl = document.getElementById('memberSearchResults');
    if (!keyword || keyword.trim().length < 1) {
        resultsEl.classList.add('hidden');
        return;
    }
    searchTimer = setTimeout(() => {
        fetch(`/api/members/search-json?q=${encodeURIComponent(keyword.trim())}`)
            .then(r => r.json())
            .then(members => {
                if (members.length === 0) {
                    resultsEl.innerHTML = '<div class="px-3 py-2 text-sm text-gray-400">未找到会员</div>';
                    resultsEl.classList.remove('hidden');
                    return;
                }
                resultsEl.innerHTML = members.map(m => {
                    const cardInfo = m.card_type ? ` · ${m.card_type}` : '';
                    return `<div class="px-3 py-2 hover:bg-blue-50 cursor-pointer text-sm border-b border-gray-50 flex justify-between items-center"
                                onclick="selectMember('${m.member_id}')">
                        <div>
                            <span class="font-medium">${m.name}</span>
                            <span class="text-gray-400 ml-2">${m.member_id}</span>
                            <span class="text-gray-400 ml-1">${m.phone || ''}</span>
                        </div>
                        <div class="text-xs text-gray-400">${m.level}${cardInfo}</div>
                    </div>`;
                }).join('');
                resultsEl.classList.remove('hidden');
            });
    }, 200);
}

function selectMember(memberId) {
    fetch(`/api/members/${memberId}/with-cards`)
        .then(r => r.json())
        .then(data => {
            selectedMember = data.member;
            memberCards = data.cards;

            document.getElementById('selectedMemberName').textContent = data.member.name;
            document.getElementById('selectedMemberId').textContent = data.member.member_id;
            document.getElementById('selectedMemberPhone').textContent = data.member.phone || '-';
            document.getElementById('selectedMemberLevel').textContent = data.member.level || '普通';
            document.getElementById('selectedMemberIdInput').value = data.member.member_id;
            document.getElementById('selectedMemberNameInput').value = data.member.name;

            const statusEl = document.getElementById('selectedMemberStatus');
            const s = data.member.status;
            if (s === '正常' || s === '有效') {
                statusEl.className = 'px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700';
                statusEl.textContent = '✓ 正常';
            } else {
                statusEl.className = 'px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700';
                statusEl.textContent = '✗ 异常';
            }

            const cardTextEl = document.getElementById('selectedMemberCard');
            if (data.cards && data.cards.length > 0) {
                const activeCards = data.cards.filter(c => c.status === '正常');
                cardTextEl.textContent = activeCards.length > 0
                    ? activeCards.map(c => c.card_type).join(', ')
                    : data.cards.length + ' 张(均过期)';
            } else {
                cardTextEl.textContent = '无';
            }

            document.getElementById('selectedMemberInfo').classList.remove('hidden');
            document.getElementById('memberSearchResults').classList.add('hidden');
            document.getElementById('memberSearchInput').value = data.member.name;

            loadCardSelect(data.cards);
            updateDeductPreview();

            // 自动选择跟进员工
            if (data.member.staff_name) {
                var followupSel = document.getElementById('staffFollowup');
                for (var i = 0; i < followupSel.options.length; i++) {
                    if (followupSel.options[i].value === data.member.staff_name) {
                        followupSel.selectedIndex = i;
                        break;
                    }
                }
            }
            updateSubmitButton();
        });
}

function clearMember() {
    selectedMember = null;
    memberCards = [];
    document.getElementById('memberSearchInput').value = '';
    document.getElementById('memberSearchResults').classList.add('hidden');
    document.getElementById('scanInput').value = '';
    document.getElementById('scanResult').classList.add('hidden');
    document.getElementById('selectedMemberInfo').classList.add('hidden');
    document.getElementById('selectedMemberIdInput').value = '';
    document.getElementById('selectedMemberNameInput').value = '';
    document.getElementById('cardSection').classList.add('hidden');
    document.getElementById('consumeSection').classList.add('hidden');
    document.getElementById('deductPreview').classList.add('hidden');
    document.getElementById('submitBtn').disabled = true;
}

// ════════════════════════════════════════════
// 会籍卡 + 核销方式联动
// ════════════════════════════════════════════

function loadCardSelect(cards) {
    const sel = document.getElementById('cardSelect');
    sel.innerHTML = '<option value="">—— 不核销会籍卡 ——</option>';

    if (!cards || cards.length === 0) {
        document.getElementById('cardSection').classList.add('hidden');
        document.getElementById('consumeSection').classList.add('hidden');
        return;
    }

    cards.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.card_id;
        const status = c.status === '正常' ? '' : ' (已过期)';
        const period = c.start_date ? `${c.start_date} ~ ${c.end_date || ''}` : '';
        opt.textContent = `${c.card_type || '未知类型'}${status} — ${period}`;
        opt.dataset.cardType = c.card_type || '';
        opt.dataset.cardStatus = c.status || '';
        sel.appendChild(opt);
    });

    document.getElementById('cardSection').classList.remove('hidden');

    // 自动选择第一张有效卡
    const activeCards = cards.filter(c => c.status === '正常');
    if (activeCards.length > 0) {
        sel.value = activeCards[0].card_id;
        onCardSelect(sel);
    }
}

function onCardSelect(sel) {
    const cardId = sel.value;
    if (!cardId) {
        // 不选会籍卡 → 显示"无卡体验"选项
        document.getElementById('consumeSection').classList.remove('hidden');
        const consumeEl = document.getElementById('consumeOptions');
        consumeEl.innerHTML = `
            <label class="flex items-center gap-2 p-2 border border-dashed border-yellow-300 rounded-lg cursor-pointer hover:bg-yellow-50 bg-yellow-50">
                <input type="radio" name="consumeOption" value="无卡体验" checked onchange="onConsumeOptionChange()">
                <div>
                    <span class="text-sm font-medium text-yellow-700">无卡体验</span>
                    <span class="text-xs text-gray-400 ml-2">不扣减任何资源，仅登记进场</span>
                </div>
            </label>`;
        document.getElementById('consumeTypeInput').value = '无卡体验';
        document.getElementById('consumeDetailInput').value = '无卡体验';
        updateDeductPreview();
        return;
    }

    const card = memberCards.find(c => c.card_id === cardId);
    if (!card) return;

    // 同步卡类型
    const typeSelect = document.getElementById('cardType');
    const typeMap = {'月卡':'月卡', '季卡':'季卡', '年卡':'年卡', '时卡':'时卡', '次卡':'次卡', '现金卡':'现金卡'};
    typeSelect.value = typeMap[card.card_type] || card.card_type || '';

    // 根据卡类型显示核销方式选项
    const consumeEl = document.getElementById('consumeOptions');
    const consumeSection = document.getElementById('consumeSection');
    consumeSection.classList.remove('hidden');

    // 先清除旧的输入框
    const oldQf = document.getElementById('consumeQuantityField');
    if (oldQf) oldQf.remove();
    const oldAf = document.getElementById('consumeAmountField');
    if (oldAf) oldAf.remove();

    const ctype = card.card_type || '';
    const m = selectedMember;

    // ─── 动态收集所有可用选项 ───
    let optionsHTML = '';

    // 1️⃣ 期限卡签到（月/季/年/时卡 或 数据库中存为"期限卡"）
    if (ctype === '期限卡' || ['月卡', '季卡', '年卡', '时卡'].includes(ctype)) {
        optionsHTML += `
            <label class="flex items-center gap-2 p-2 border rounded-lg cursor-pointer hover:bg-blue-50 bg-blue-50 border-blue-200">
                <input type="radio" name="consumeOption" value="期限卡签到" checked onchange="onConsumeOptionChange()">
                <div>
                    <span class="text-sm font-medium">期限卡签到</span>
                    <span class="text-xs text-gray-400 ml-2">不扣次/扣款，仅签到</span>
                </div>
            </label>`;
    }

    // 2️⃣ 次卡扣次（次卡/含"次"的类型）
    if (ctype === '次卡' || ctype.includes('次')) {
        optionsHTML += `
            <label class="flex items-center gap-2 p-2 border rounded-lg cursor-pointer hover:bg-gray-50 ${!optionsHTML ? 'bg-blue-50 border-blue-200' : ''}">
                <input type="radio" name="consumeOption" value="次卡扣次" ${!optionsHTML ? 'checked' : ''} onchange="onConsumeOptionChange()">
                <div>
                    <span class="text-sm font-medium">次卡扣次</span>
                    <span class="text-xs text-gray-400 ml-2">剩余: ${m.remaining_lessons || 0} 次</span>
                </div>
            </label>
            <div id="consumeQuantityField" class="mt-1 flex items-center gap-2" style="display:${!optionsHTML ? 'flex' : 'none'}">
                <span class="text-xs text-gray-500">扣减次数:</span>
                <input type="number" id="consumeQuantityInput" value="1" min="1" max="${m.remaining_lessons || 1}"
                       class="w-20 px-2 py-1 text-sm border rounded text-center"
                       onchange="updateDeductPreview()" oninput="updateDeductPreview()">
            </div>`;
    }

    // 3️⃣ 储值扣款（有余额时可用）
    const balance = parseFloat(m.balance || 0);
    if (balance > 0) {
        optionsHTML += `
            <label class="flex items-center gap-2 p-2 border rounded-lg cursor-pointer hover:bg-gray-50 ${!optionsHTML ? 'bg-blue-50 border-blue-200' : ''}">
                <input type="radio" name="consumeOption" value="储值扣款" ${!optionsHTML ? 'checked' : ''} onchange="onConsumeOptionChange()">
                <div>
                    <span class="text-sm font-medium">储值扣款</span>
                    <span class="text-xs text-gray-400 ml-2">余额: ¥${balance.toFixed(2)}</span>
                </div>
            </label>
            <div id="consumeAmountField" class="mt-1 flex items-center gap-2" style="display:${!optionsHTML ? 'flex' : 'none'}">
                <span class="text-xs text-gray-500">扣费金额:</span>
                <input type="number" id="consumeAmountInput" value="" min="0" step="0.5" placeholder="输入金额"
                       class="w-24 px-2 py-1 text-sm border rounded text-center"
                       onchange="updateDeductPreview()" oninput="updateDeductPreview()">
            </div>`;
    }

    // 4️⃣ 现金卡扣费（自定义金额，不设默认值）
    if (ctype === '现金卡') {
        const consumed = parseFloat(card.consumed_amount || 0);
        const price = parseFloat(card.price || 0);
        const remaining = Math.max(0, price - consumed);
        optionsHTML += `
            <label class="flex items-center gap-2 p-2 border rounded-lg cursor-pointer hover:bg-blue-50 bg-blue-50 border-blue-200">
                <input type="radio" name="consumeOption" value="现金卡扣费" checked onchange="onConsumeOptionChange()">
                <div>
                    <span class="text-sm font-medium">现金卡扣费</span>
                    <span class="text-xs text-gray-400 ml-2">卡内剩余 ¥${remaining.toFixed(2)}</span>
                </div>
            </label>
            <div id="consumeAmountField" class="mt-1 flex items-center gap-2" style="display:flex">
                <span class="text-xs text-gray-500">扣费金额:</span>
                <input type="number" id="consumeAmountInput" value="" min="0" step="0.5" placeholder="输入金额"
                       class="w-24 px-2 py-1 text-sm border rounded text-center"
                       onchange="updateDeductPreview()" oninput="updateDeductPreview()">
            </div>`;
    }

    // 5️⃣ 无卡体验（总是可用）
    optionsHTML += `
        <div class="border-t border-gray-200 pt-2 mt-2">
            <label class="flex items-center gap-2 p-2 border border-dashed border-gray-300 rounded-lg cursor-pointer hover:bg-yellow-50">
                <input type="radio" name="consumeOption" value="无卡体验" onchange="onConsumeOptionChange()">
                <div>
                    <span class="text-sm font-medium text-yellow-700">无卡体验</span>
                    <span class="text-xs text-gray-400 ml-2">不扣减任何资源，仅登记进场</span>
                </div>
            </label>
        </div>`;

    if (optionsHTML) {
        consumeEl.innerHTML = optionsHTML;
        onConsumeOptionChange();
    } else {
        consumeSection.classList.add('hidden');
    }
}

function onConsumeOptionChange() {
    const selected = document.querySelector('input[name="consumeOption"]:checked');
    if (!selected) return;
    document.getElementById('consumeTypeInput').value = selected.value;
    document.getElementById('consumeDetailInput').value = selected.value;
    // 显示/隐藏自定义输入框
    const qf = document.getElementById('consumeQuantityField');
    const af = document.getElementById('consumeAmountField');
    if (qf) qf.style.display = selected.value === '次卡扣次' ? 'flex' : 'none';
    // 现金卡扣费和储值扣款都显示金额输入框
    if (af) af.style.display = (selected.value === '储值扣款' || selected.value === '现金卡扣费') ? 'flex' : 'none';
    updateDeductPreview();
}

// ════════════════════════════════════════════
// 扣减预览
// ════════════════════════════════════════════

function updateDeductPreview() {
    const previewEl = document.getElementById('deductPreview');
    if (!selectedMember) { previewEl.classList.add('hidden'); return; }

    const m = selectedMember;
    const consumeOption = document.querySelector('input[name="consumeOption"]:checked');

    document.getElementById('previewValidity').textContent =
        m.start_date ? `${m.start_date} ~ ${m.end_date || '长期'}` : '-';
    document.getElementById('previewLessons').textContent = `${m.remaining_lessons || 0} 次`;
    document.getElementById('previewBalance').textContent = `¥${parseFloat(m.balance || 0).toFixed(2)}`;

    // 计算现金卡总额（所有正常状态的现金卡剩余可用金额之和）
    const cashCardTotal = (memberCards || [])
        .filter(c => c.card_type === '现金卡' && c.status === '正常')
        .reduce((sum, c) => sum + Math.max(0, (parseFloat(c.price) || 0) - (parseFloat(c.consumed_amount) || 0)), 0);
    document.getElementById('previewCashCard').textContent =
        cashCardTotal > 0 ? `¥${cashCardTotal.toFixed(2)}` : '-';

    let deductText = '-';
    if (consumeOption) {
        const val = consumeOption.value;
        if (val === '次卡扣次') {
            const n = parseInt(document.getElementById('consumeQuantityInput')?.value || '1');
            deductText = `扣除 ${n} 次`;
        } else if (val === '储值扣款') {
            const fee = parseFloat(document.getElementById('consumeAmountInput')?.value || '0');
            if (fee > 0) deductText = `扣除 ¥${fee.toFixed(2)}（填多少钱扣多少）`;
            else deductText = '请输入扣费金额';
        } else if (val === '期限卡签到') deductText = '期限卡签到（不扣次/不扣款）';
        else if (val === '现金卡扣费') {
            const sel = document.getElementById('cardSelect');
            const cardId = sel ? sel.value : '';
            const cashCard = (memberCards || []).find(c => c.card_id === cardId);
            const consumed = parseFloat(cashCard?.consumed_amount || 0);
            const price = parseFloat(cashCard?.price || 0);
            const remaining = Math.max(0, price - consumed);
            const fee = parseFloat(document.getElementById('consumeAmountInput')?.value || '0');
            if (fee > 0) {
                const after = Math.max(0, remaining - fee);
                deductText = `现金卡扣费 ¥${fee.toFixed(2)}，卡内剩余 ¥${after.toFixed(2)}`;
            } else {
                deductText = `现金卡剩余 ¥${remaining.toFixed(2)}，请输入扣费金额`;
            }
        }
        else if (val === '无卡体验') deductText = '无卡体验（不扣减任何资源）';
    }
    document.getElementById('previewDeduct').textContent = deductText;
    previewEl.classList.remove('hidden');
}

function updateSubmitButton() {
    document.getElementById('submitBtn').disabled = !selectedMember;
}

// ════════════════════════════════════════════
// 跟进员工
// ════════════════════════════════════════════

function loadStaffList() {
    const sel = document.getElementById('staffFollowup');
    if (sel.options.length > 1) return;
    fetch('/api/staff/active')
        .then(r => r.json())
        .then(staffs => {
            staffs.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.name;
                opt.textContent = `${s.name} (${s.position || '无岗位'})`;
                sel.appendChild(opt);
            });
        });
}

function loadDefaultOperator() {
    // 从 /auth/me 获取当前登录用户名，自动填入操作人
    fetch('/auth/me', { credentials: 'same-origin' })
        .then(function(r) { return r.ok ? r.json() : null; })
        .then(function(user) {
            if (user && user.username) {
                var opInput = document.querySelector('input[name="operator"]');
                if (opInput && !opInput.value) {
                    opInput.value = user.username;
                }
            }
        })
        .catch(function() { /* ignore */ });
}

// ════════════════════════════════════════════
// 提交进场（含核销逻辑）
// ════════════════════════════════════════════

function submitCheckin(event) {
    event.preventDefault();
    if (!selectedMember) { alert('请先选择会员'); return; }

    const form = document.getElementById('checkinForm');
    const formData = new FormData(form);
    const params = new URLSearchParams();

    // 取当前选中的会籍卡 ID（来自 cardSelect，而非隐藏的 card_id 输入）
    const cardSelect = document.getElementById('cardSelect');
    const selectedCardId = cardSelect ? cardSelect.value : '';

    params.set('member_id', formData.get('member_id') || '');
    params.set('member_name', formData.get('member_name') || '');
    params.set('checkin_type', '核销');
    params.set('card_type', document.getElementById('cardType').value || '');
    params.set('card_id', selectedCardId || '');
    params.set('consume_type', formData.get('consume_type') || '');
    params.set('consume_detail', formData.get('consume_detail') || '');
    params.set('operator', formData.get('operator') || '');
    params.set('staff_followup', formData.get('staff_followup') || '');

    // 自定义扣次/扣费
    const qInput = document.getElementById('consumeQuantityInput');
    if (qInput && qInput.value) params.set('consume_quantity', qInput.value);
    const aInput = document.getElementById('consumeAmountInput');
    if (aInput && aInput.value) params.set('consume_amount', aInput.value);

    fetch('/api/checkins', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params.toString()
    })
    .then(r => r.json())
    .then(res => {
        if (res.success) {
            closeCheckinModal();
            document.getElementById('checkinTable').innerHTML = '<div class="text-center py-8 text-gray-400">加载中...</div>';
            htmx.process(document.getElementById('checkinTable'));
            htmx.ajax('GET', '/api/checkins/table', {target: '#checkinTable', swap: 'innerHTML'});
        } else {
            alert(res.detail || '操作失败');
        }
    })
    .catch(err => { alert(err.message); });
}
