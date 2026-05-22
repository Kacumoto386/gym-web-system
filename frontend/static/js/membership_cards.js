// ── Tab 切换 ──
function switchCardTab(tab) {
    document.getElementById('tabProducts').className = 'px-4 py-2 text-sm font-medium -mb-px ' + (tab === 'products' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 hover:text-gray-700');
    document.getElementById('tabSold').className = 'px-4 py-2 text-sm font-medium -mb-px ' + (tab === 'sold' ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 hover:text-gray-700');
    document.getElementById('cardProductTab').classList.toggle('hidden', tab !== 'products');
    document.getElementById('cardSoldTab').classList.toggle('hidden', tab !== 'sold');
}

// ── 新增产品：卡类型联动 ──
function onProdTypeChange() {
    var t = document.getElementById('prodType').value;
    var cls = document.getElementById('prodClassesRow');
    var bonus = document.getElementById('prodBonusRow');
    var face = document.getElementById('prodFaceValueRow');
    if (t === '次卡') {
        cls.classList.remove('hidden');
        bonus.classList.remove('hidden');
        face.classList.add('hidden');
    } else if (t === '期限卡') {
        cls.classList.add('hidden');
        bonus.classList.add('hidden');
        face.classList.add('hidden');
        document.getElementById('prodClasses').value = '0';
        document.getElementById('prodBonus').value = '0';
        document.getElementById('prodFaceValue').value = '0';
    } else { // 现金卡
        cls.classList.add('hidden');
        bonus.classList.add('hidden');
        face.classList.remove('hidden');
        document.getElementById('prodClasses').value = '0';
        document.getElementById('prodBonus').value = '0';
    }
}

// ── 新增产品：提交（修复：用精确ID选择器避免querySelector匹配到多个bg-blue-600）──
function submitProduct() {
    var btn = document.getElementById('prodSaveBtn');
    var resultEl = document.getElementById('prodResult');
    btn.disabled = true; btn.textContent = '保存中...'; resultEl.classList.add('hidden');

    var params = new URLSearchParams();
    params.set('card_type', document.getElementById('prodType').value);
    params.set('name', document.getElementById('prodName').value);
    params.set('duration_days', document.getElementById('prodDuration').value || '0');
    params.set('total_classes', document.getElementById('prodClasses').value || '0');
    params.set('bonus_classes', document.getElementById('prodBonus').value || '0');
    params.set('face_value', document.getElementById('prodFaceValue').value || '0');
    params.set('price', document.getElementById('prodPrice').value || '0');

    fetch('/api/membership-cards/products', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params.toString()
    })
    .then(function(r) {
        if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || '保存失败'); });
        return r.json();
    })
    .then(function() {
        resultEl.classList.remove('hidden');
        resultEl.className = 'text-sm text-center py-2 rounded-lg bg-green-50 text-green-700';
        resultEl.textContent = '✅ 卡产品创建成功！';
        // 用 htmx.ajax 手动重新加载，避免 trigger('load') 不可靠
        htmx.ajax('GET', '/api/membership-cards/products/table', { target: '#cardProductTable' });
        setTimeout(function() { document.getElementById('addProductModal').classList.add('hidden'); }, 1500);
        btn.disabled = false; btn.textContent = '保存';
    })
    .catch(function(e) {
        resultEl.classList.remove('hidden');
        resultEl.className = 'text-sm text-center py-2 rounded-lg bg-red-50 text-red-700';
        // 如果因为fetch网络错误（页面跳转/刷新），catch里不显示
        resultEl.textContent = '❌ ' + e.message;
        btn.disabled = false; btn.textContent = '保存';
    });
}

// ── 售卡：加载会员列表 + 卡产品 ──
function openSellModal() {
    document.getElementById('sellCardModal').classList.remove('hidden');
    document.getElementById('sellResult').classList.add('hidden');
    document.getElementById('sellProductInfo').classList.add('hidden');
    document.getElementById('sellEndDateRow').classList.add('hidden');
    document.getElementById('sellPriceRow').classList.add('hidden');

    // 设置今天的日期为默认开卡日期
    var today = new Date().toISOString().split('T')[0];
    document.getElementById('sellStartDate').value = today;

    // 加载会员
    fetch('/api/members/with-cards')
    .then(function(r) { return r.json(); })
    .then(function(data) {
        var sel = document.getElementById('sellMember');
        sel.innerHTML = '<option value="">请选择会员</option>';
        data.forEach(function(m) {
            sel.innerHTML += '<option value="' + m.member_id + '|' + m.name + '">' + m.member_id + ' - ' + m.name + '</option>';
        });
    });

    // 加载卡产品
    loadSellProducts();
}

function loadSellProducts() {
    fetch('/api/membership-cards/products/list')
    .then(function(r) { return r.json(); })
    .then(function(data) {
        var sel = document.getElementById('sellProduct');
        sel.innerHTML = '<option value="">请选择卡产品</option>';
        data.forEach(function(p) {
            var label = '[' + p.card_type + '] ' + p.name;
            if (p.card_type === '次卡') {
                label += ' (' + p.total_classes + '次';
                if (p.bonus_classes > 0) label += '+赠' + p.bonus_classes;
                label += ')';
            } else if (p.card_type === '现金卡') {
                label += ' 面值¥' + p.face_value + ' 储值¥' + p.price;
            } else {
                label += ' ' + p.duration_days + '天';
            }
            sel.innerHTML += '<option value="' + p.card_id + '"' +
                ' data-type="' + p.card_type + '"' +
                ' data-days="' + p.duration_days + '"' +
                ' data-price="' + p.price + '"' +
                ' data-classes="' + p.total_classes + '"' +
                ' data-bonus="' + p.bonus_classes + '"' +
                ' data-face="' + p.face_value + '">' + label + '</option>';
        });
    });
}

// ── 售卡：选择卡产品后更新信息 ──
function onSellProductChange() {
    var sel = document.getElementById('sellProduct');
    var opt = sel.options[sel.selectedIndex];
    var info = document.getElementById('sellProductInfo');
    var endRow = document.getElementById('sellEndDateRow');
    var priceRow = document.getElementById('sellPriceRow');

    if (!opt || !opt.value) {
        info.classList.add('hidden');
        endRow.classList.add('hidden');
        priceRow.classList.add('hidden');
        return;
    }

    var type = opt.getAttribute('data-type');
    var days = parseInt(opt.getAttribute('data-days')) || 0;
    var price = parseFloat(opt.getAttribute('data-price')) || 0;
    var face = parseFloat(opt.getAttribute('data-face')) || 0;

    // 产品信息展示
    var html = '<span class="font-medium">' + opt.text + '</span>';
    if (type === '现金卡') {
        html += '<div>面值: ¥' + face.toFixed(0) + ' | 储值价: ¥' + price.toFixed(0) + '</div>';
    }
    info.innerHTML = html;
    info.classList.remove('hidden');

    // 现金卡：显示售价输入
    if (type === '现金卡') {
        priceRow.classList.remove('hidden');
        document.getElementById('sellPrice').value = price;
    } else {
        priceRow.classList.add('hidden');
    }

    // 计算截止日期
    onSellDateChange();
}

// ── 售卡：日期变更 → 计算截止日期 ──
function onSellDateChange() {
    var sel = document.getElementById('sellProduct');
    var opt = sel.options[sel.selectedIndex];
    if (!opt || !opt.value) return;

    var days = parseInt(opt.getAttribute('data-days')) || 0;
    var startVal = document.getElementById('sellStartDate').value;
    var endRow = document.getElementById('sellEndDateRow');
    var endInput = document.getElementById('sellEndDate');

    if (startVal && days > 0) {
        var start = new Date(startVal);
        start.setDate(start.getDate() + days);
        endInput.value = start.toISOString().split('T')[0];
        endRow.classList.remove('hidden');
    } else {
        endRow.classList.add('hidden');
        endInput.value = '';
    }
}

// ── 售卡：提交 ──
function submitSell() {
    var btn = document.querySelector('#sellCardModal .bg-green-600');
    var resultEl = document.getElementById('sellResult');
    btn.disabled = true; btn.textContent = '售卡中...'; resultEl.classList.add('hidden');

    var memberSel = document.getElementById('sellMember');
    var memberVal = memberSel.value;
    if (!memberVal) { resultEl.className = 'text-sm text-center py-2 rounded-lg bg-red-50 text-red-700'; resultEl.textContent = '❌ 请选择会员'; resultEl.classList.remove('hidden'); btn.disabled = false; btn.textContent = '确认售卡'; return; }
    var memberParts = memberVal.split('|');
    var memberId = memberParts[0];
    var memberName = memberParts[1];

    var prodId = document.getElementById('sellProduct').value;
    if (!prodId) { resultEl.className = 'text-sm text-center py-2 rounded-lg bg-red-50 text-red-700'; resultEl.textContent = '❌ 请选择卡产品'; resultEl.classList.remove('hidden'); btn.disabled = false; btn.textContent = '确认售卡'; return; }

    var opt = document.getElementById('sellProduct').options[document.getElementById('sellProduct').selectedIndex];
    var type = opt.getAttribute('data-type');
    var price = type === '现金卡' ? document.getElementById('sellPrice').value : opt.getAttribute('data-price');

    var params = new URLSearchParams();
    params.set('member_id', memberId);
    params.set('member_name', memberName);
    params.set('product_id', prodId);
    params.set('price', price || '0');
    params.set('start_date', document.getElementById('sellStartDate').value || '');

    fetch('/api/membership-cards/sell', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params.toString()
    })
    .then(function(r) {
        if (!r.ok) return r.json().then(function(e) { throw new Error(e.detail || '售卡失败'); });
        return r.json();
    })
    .then(function(data) {
        resultEl.classList.remove('hidden');
        resultEl.className = 'text-sm text-center py-2 rounded-lg bg-green-50 text-green-700';
        resultEl.textContent = '✅ 售卡成功！' + data.member_name + ' (' + data.card_id + ')';
        htmx.ajax('GET', '/api/membership-cards/sold/table', { target: '#cardSoldTable' });
        setTimeout(function() { document.getElementById('sellCardModal').classList.add('hidden'); }, 2000);
    })
    .catch(function(e) {
        resultEl.classList.remove('hidden');
        resultEl.className = 'text-sm text-center py-2 rounded-lg bg-red-50 text-red-700';
        resultEl.textContent = '❌ ' + e.message;
        btn.disabled = false; btn.textContent = '确认售卡';
    });
}

// ── 挂载售卡按钮到已售Tab ──
document.addEventListener('DOMContentLoaded', function() {
    var soldTab = document.getElementById('tabSold');
    soldTab.addEventListener('click', function() {
        setTimeout(function() {
            var soldBtnArea = document.querySelector('#cardSoldTab');
            if (!soldBtnArea) return;
            var existingBtn = soldBtnArea.parentElement.querySelector('.sell-card-btn');
            if (!existingBtn) {
                var btn = document.createElement('button');
                btn.className = 'sell-card-btn bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 text-sm mb-4';
                btn.textContent = '+ 售卡';
                btn.onclick = openSellModal;
                soldBtnArea.parentElement.insertBefore(btn, soldBtnArea);
            }
        }, 100);
    });
});
