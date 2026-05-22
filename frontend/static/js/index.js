// 快速签到 - 会员搜索
var quickTimer = null;
var quickMemberCards = []; // 当前搜索会员的有效会籍卡列表
var currentOperator = '';  // 当前登录用户名（从 auth/me 获取）

// 加载当前操作人
(function() {
    fetch('/auth/me', { credentials: 'same-origin' })
        .then(function(r) { return r.ok ? r.json() : null; })
        .then(function(user) { if (user) currentOperator = user.username; })
        .catch(function() { /* ignore */ });
})();
document.getElementById('quickCheckinInput').addEventListener('input', function() {
    clearTimeout(quickTimer);
    var val = this.value.trim();
    if (val.length < 2) {
        document.getElementById('quickMemberInfo').classList.add('hidden');
        document.getElementById('quickConsumeOptions').classList.add('hidden');
        document.getElementById('quickCheckinBtn').disabled = true;
        return;
    }
    quickTimer = setTimeout(function() {
        fetch('/api/members/search-json?q=' + encodeURIComponent(val), { credentials: 'same-origin' })
            .then(function(r) { return r.json(); })
            .then(function(members) {
                var infoEl = document.getElementById('quickMemberInfo');
                var optsEl = document.getElementById('quickConsumeOptions');
                var btnEl = document.getElementById('quickCheckinBtn');
                if (members.length === 0) {
                    infoEl.classList.add('hidden');
                    optsEl.classList.add('hidden');
                    btnEl.disabled = true;
                    return;
                }
                var m = members[0];

                // 查询会员的有效会籍卡（通过 with-cards 端点）
                fetch('/api/members/' + m.member_id + '/with-cards', { credentials: 'same-origin' })
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        var cards = data.cards || [];
                        var activeCards = cards.filter(function(c) { return c.status === '正常' || c.status === '有效'; });
                        quickMemberCards = activeCards;
                        var has次卡 = activeCards.some(function(c) { return c.card_type === '次卡' || (c.card_type || '').includes('次'); });
                        var has期限卡 = activeCards.some(function(c) { return c.card_type === '期限卡' || ['月卡','季卡','年卡','时卡'].includes(c.card_type); });
                        var has现金卡 = activeCards.some(function(c) { return c.card_type === '现金卡'; });

                        // 计算现金卡总额（所有正常状态的现金卡 price 之和）
                        var cashCardTotal = (cards || [])
                            .filter(function(c) { return c.card_type === '现金卡' && (c.status === '正常' || c.status === '有效'); })
                            .reduce(function(sum, c) { return sum + (parseFloat(c.price) || 0); }, 0);

                        infoEl.classList.remove('hidden');
                        var cardList = activeCards.length > 0
                            ? activeCards.map(function(c) { return c.card_type; }).join(', ')
                            : (cards.length > 0 ? cards.length + ' 张(均过期)' : '无');
                        var balParts = '余额: ¥' + (parseFloat(m.balance || 0).toFixed(2));
                        if (cashCardTotal > 0) {
                            balParts += ' · 现金卡: ¥' + cashCardTotal.toFixed(2);
                        }
                        infoEl.innerHTML = '<div class="flex items-center gap-2"><span class="font-medium">' + m.name + '</span><span class="text-gray-400">' + (m.phone || '') + '</span></div>' +
                            '<div class="text-xs text-gray-400 mt-1">会籍卡: ' + cardList + ' · 剩余: ' + (m.remaining_lessons || 0) + '次 · ' + balParts + '</div>';
                        infoEl.dataset.memberId = m.member_id;
                        infoEl.dataset.memberName = m.name;
                        infoEl.dataset.has次卡 = has次卡 ? '1' : '0';
                        infoEl.dataset.has期限卡 = has期限卡 ? '1' : '0';
                        infoEl.dataset.remainingLessons = m.remaining_lessons || 0;
                        infoEl.dataset.balance = m.balance || 0;
                        infoEl.dataset.staffName = (data.member && data.member.staff_name) || '';

                        // 生成核销选项（基于有效会籍卡实时数据）
                        var html = '';
                        var firstOption = ''; // 记录默认选中哪个
                        if (has次卡) {
                            html += '<label class="flex items-center gap-2 p-1.5 border rounded cursor-pointer hover:bg-blue-50 bg-blue-50 border-blue-200 text-xs"><input type="radio" name="quickOption" value="次卡扣次" onchange="onQuickOptionChange()"><span class="font-medium">次卡扣次</span><span class="text-gray-400 ml-auto">余' + (m.remaining_lessons || 0) + '次</span></label>';
                            html += '<div id="quickQuantityField" class="flex items-center gap-2 mt-1" style="display:none"><span class="text-xs text-gray-500">扣减:</span><input type="number" id="quickQuantityInput" value="1" min="1" max="' + (m.remaining_lessons || 1) + '" class="w-16 px-2 py-1 text-xs border rounded text-center"></div>';
                            if (!firstOption) firstOption = '次卡扣次';
                        }
                        if (parseFloat(m.balance || 0) > 0) {
                            html += '<label class="flex items-center gap-2 p-1.5 border rounded cursor-pointer hover:bg-gray-50 border-gray-200 text-xs"><input type="radio" name="quickOption" value="储值扣款" onchange="onQuickOptionChange()"><span class="font-medium">储值扣款</span><span class="text-gray-400 ml-auto">¥' + (parseFloat(m.balance || 0).toFixed(2)) + '</span></label>';
                            if (!firstOption) firstOption = '储值扣款';
                        }
                        if (has现金卡) {
                            // 计算现金卡总余额
                            var cashTotal = (activeCards || [])
                                .filter(function(c){ return c.card_type === '现金卡'; })
                                .reduce(function(s, c){ return s + (parseFloat(c.price) - parseFloat(c.consumed_amount || 0)); }, 0);
                            html += '<label class="flex items-center gap-2 p-1.5 border rounded cursor-pointer hover:bg-blue-50 bg-blue-50 border-blue-200 text-xs"><input type="radio" name="quickOption" value="现金卡扣费" onchange="onQuickOptionChange()"><span class="font-medium">现金卡扣费</span><span class="text-gray-400 ml-auto">余¥' + cashTotal.toFixed(2) + '</span></label>';
                            if (!firstOption) firstOption = '现金卡扣费';
                        }
                        if (has期限卡) {
                            html += '<label class="flex items-center gap-2 p-1.5 border rounded cursor-pointer hover:bg-gray-50 border-gray-200 text-xs"><input type="radio" name="quickOption" value="期限卡签到" onchange="onQuickOptionChange()"><span class="font-medium">期限卡签到</span><span class="text-gray-400 ml-auto">不扣费</span></label>';
                            if (!firstOption) firstOption = '期限卡签到';
                        }
                        // 无卡体验（总是可选）
                        html += '<div class="border-t border-gray-200 pt-1.5 mt-1"><label class="flex items-center gap-2 p-1.5 border border-dashed border-gray-300 rounded cursor-pointer hover:bg-yellow-50 text-xs"><input type="radio" name="quickOption" value="无卡体验" onchange="onQuickOptionChange()"><span class="font-medium text-yellow-700">无卡体验</span><span class="text-gray-400 ml-auto">仅登记</span></label></div>';

                        optsEl.classList.remove('hidden');
                        optsEl.innerHTML = html;
                        btnEl.disabled = false;

                        // 设置默认选中和显示对应输入框
                        if (firstOption) {
                            var radio = optsEl.querySelector('input[name="quickOption"][value="' + firstOption + '"]');
                            if (radio) radio.checked = true;
                            onQuickOptionChange();
                        }
                    })
                    .catch(function(e) {
                        // with-cards 失败则回退用会员基本信息
                        console.warn('with-cards failed:', e);
                        showQuickOptionsFallback(m, infoEl, optsEl, btnEl);
                    });
            })
            .catch(function(e) { console.warn('Quick search error:', e); });
    }, 300);
});

function onQuickOptionChange() {
    var opt = document.querySelector('input[name="quickOption"]:checked');
    var qf = document.getElementById('quickQuantityField');
    var af = document.getElementById('quickAmountField');
    if (qf) qf.style.display = opt && opt.value === '次卡扣次' ? 'flex' : 'none';
    if (af) af.style.display = opt && (opt.value === '储值扣款' || opt.value === '现金卡扣费') ? 'flex' : 'none';
}

function showQuickOptionsFallback(m, infoEl, optsEl, btnEl) {
    // 回退逻辑：用会员主表的 card_type
    infoEl.classList.remove('hidden');
    infoEl.innerHTML = '<div class="flex items-center gap-2"><span class="font-medium">' + m.name + '</span><span class="text-gray-400">' + (m.phone || '') + '</span></div>' +
        '<div class="text-xs text-gray-400 mt-1">卡类型: ' + (m.card_type || '无') + ' · 剩余: ' + (m.remaining_lessons || 0) + '次 · 余额: ¥' + (parseFloat(m.balance || 0).toFixed(2)) + '</div>';
    infoEl.dataset.memberId = m.member_id;
    infoEl.dataset.memberName = m.name;
    infoEl.dataset.has次卡 = '0';
    infoEl.dataset.has期限卡 = '0';
    infoEl.dataset.remainingLessons = m.remaining_lessons || 0;
    infoEl.dataset.balance = m.balance || 0;

    var ctype = m.card_type || '';
    var html = '';
    var firstOption = '';
    if (ctype === '次卡' || ctype.includes('次')) {
        html += '<label class="flex items-center gap-2 p-1.5 border rounded cursor-pointer hover:bg-blue-50 bg-blue-50 border-blue-200 text-xs"><input type="radio" name="quickOption" value="次卡扣次" onchange="onQuickOptionChange()"><span class="font-medium">次卡扣次</span><span class="text-gray-400 ml-auto">余' + (m.remaining_lessons || 0) + '次</span></label>';
        html += '<div id="quickQuantityField" class="flex items-center gap-2 mt-1" style="display:none"><span class="text-xs text-gray-500">扣减:</span><input type="number" id="quickQuantityInput" value="1" min="1" max="' + (m.remaining_lessons || 1) + '" class="w-16 px-2 py-1 text-xs border rounded text-center"></div>';
        firstOption = '次卡扣次';
    }
    if (parseFloat(m.balance || 0) > 0) {
        html += '<label class="flex items-center gap-2 p-1.5 border rounded cursor-pointer hover:bg-gray-50 border-gray-200 text-xs"><input type="radio" name="quickOption" value="储值扣款" onchange="onQuickOptionChange()"><span class="font-medium">储值扣款</span><span class="text-gray-400 ml-auto">¥' + (parseFloat(m.balance || 0).toFixed(2)) + '</span></label>';
        if (!firstOption) firstOption = '储值扣款';
    }
    if (ctype === '现金卡') {
        html += '<label class="flex items-center gap-2 p-1.5 border rounded cursor-pointer hover:bg-blue-50 bg-blue-50 border-blue-200 text-xs"><input type="radio" name="quickOption" value="现金卡扣费" onchange="onQuickOptionChange()"><span class="font-medium">现金卡扣费</span><span class="text-gray-400 ml-auto"></span></label>';
        if (!firstOption) firstOption = '现金卡扣费';
    } else if (ctype === '期限卡' || ['月卡','季卡','年卡','时卡'].includes(ctype)) {
        html += '<label class="flex items-center gap-2 p-1.5 border rounded cursor-pointer hover:bg-gray-50 border-gray-200 text-xs"><input type="radio" name="quickOption" value="期限卡签到" onchange="onQuickOptionChange()"><span class="font-medium">期限卡签到</span><span class="text-gray-400 ml-auto">不扣费</span></label>';
        if (!firstOption) firstOption = '期限卡签到';
    }
    html += '<div class="border-t border-gray-200 pt-1.5 mt-1"><label class="flex items-center gap-2 p-1.5 border border-dashed border-gray-300 rounded cursor-pointer hover:bg-yellow-50 text-xs"><input type="radio" name="quickOption" value="无卡体验" onchange="onQuickOptionChange()"><span class="font-medium text-yellow-700">无卡体验</span><span class="text-gray-400 ml-auto">仅登记</span></label></div>';

    optsEl.classList.remove('hidden');
    optsEl.innerHTML = html;
    btnEl.disabled = false;

    // 设置默认选中
    if (firstOption) {
        var radio = optsEl.querySelector('input[name="quickOption"][value="' + firstOption + '"]');
        if (radio) { radio.checked = true; onQuickOptionChange(); }
    }
}

function doQuickCheckin() {
    var infoEl = document.getElementById('quickMemberInfo');
    var btnEl = document.getElementById('quickCheckinBtn');
    var resultEl = document.getElementById('quickCheckinResult');
    var optionEl = document.querySelector('input[name="quickOption"]:checked');

    if (!optionEl) { alert('请选择核销方式'); return; }

    btnEl.disabled = true;
    btnEl.textContent = '签到中...';

    var params = new URLSearchParams();
    params.set('member_id', infoEl.dataset.memberId);
    params.set('member_name', infoEl.dataset.memberName);
    params.set('checkin_type', optionEl.value === '无卡体验' ? '体验' : '');
    params.set('card_type', optionEl.value === '无卡体验' ? '' :
        (optionEl.value === '现金卡扣费' ? '现金卡' : '快速签到'));
    params.set('consume_type', optionEl.value);
    params.set('operator', window.currentOperator || '');
    params.set('staff_followup', infoEl.dataset.staffName || '');

    // 现金卡扣费：自动传第一张有效现金卡的 ID，金额由用户输入
    if (optionEl.value === '现金卡扣费') {
        // 从 memberCards 找第一张有效的现金卡
        var firstCashCard = (window.quickMemberCards || []).find(function(c) {
            return c.card_type === '现金卡' && (c.status === '正常' || c.status === '有效') &&
                (parseFloat(c.price) - parseFloat(c.consumed_amount || 0)) >= 0;
        });
        if (firstCashCard) {
            params.set('card_id', firstCashCard.card_id);
        }
        // 金额由用户输入，不设默认值
    }

    // 自定义扣次/扣费
    var qInput = document.getElementById('quickQuantityInput');
    if (qInput && qInput.value) params.set('consume_quantity', qInput.value);
    var aInput = document.getElementById('quickAmountInput');
    if (aInput && aInput.value) params.set('consume_amount', aInput.value);

    fetch('/api/checkins', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params.toString()
    })
    .then(function(r) {
        if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || '签到失败'); });
        return r.json();
    })
    .then(function() {
        resultEl.classList.remove('hidden');
        resultEl.className = 'text-sm text-center py-2 rounded-lg bg-green-50 text-green-700';
        resultEl.textContent = '✅ ' + infoEl.dataset.memberName + ' 签到成功！';
        document.getElementById('quickRecentCheckin').textContent = infoEl.dataset.memberName + ' ' + new Date().toLocaleTimeString('zh-CN', {hour:'2-digit',minute:'2-digit'});
        document.getElementById('quickCheckinInput').value = '';
        document.getElementById('quickMemberInfo').classList.add('hidden');
        document.getElementById('quickConsumeOptions').classList.add('hidden');
        // 刷新今日进场记录
        htmx.ajax('GET', '/api/dashboard/today-checkins', {target: '#todayCheckins', swap: 'innerHTML'});
        setTimeout(function() {
            btnEl.disabled = false;
            btnEl.textContent = '✅ 确认签到';
            setTimeout(function() { resultEl.classList.add('hidden'); }, 3000);
        }, 1000);
    })
    .catch(function(e) {
        resultEl.classList.remove('hidden');
        resultEl.className = 'text-sm text-center py-2 rounded-lg bg-red-50 text-red-700';
        resultEl.textContent = '❌ ' + e.message;
        btnEl.disabled = false;
        btnEl.textContent = '✅ 确认签到';
    });
}
