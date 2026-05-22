// ────────── 购物车状态 ──────────
let cart = [];  // [{product_id, product_name, unit_price, quantity, total_price, product_obj}]
let products = [];
let currentMember = null;  // {member_id, member_name, balance}

// ────────── Tab 切换（5 tabs）──────────
function switchTab(tab) {
    document.getElementById('cartSection').style.display = tab === 'cart' ? '' : 'none';
    document.getElementById('productsSection').style.display = tab === 'products' ? '' : 'none';
    document.getElementById('salesSection').style.display = tab === 'sales' ? '' : 'none';
    document.getElementById('inboundsSection').style.display = tab === 'inbounds' ? '' : 'none';
    document.getElementById('analysisSection').style.display = tab === 'analysis' ? '' : 'none';
    const tabs = ['cart', 'products', 'sales', 'inbounds', 'analysis'];
    tabs.forEach(t => {
        const btn = document.getElementById('tab' + t.charAt(0).toUpperCase() + t.slice(1));
        btn.className = t === tab
            ? 'px-4 py-2 text-sm rounded-lg bg-blue-600 text-white'
            : 'px-4 py-2 text-sm rounded-lg bg-gray-200 text-gray-600 hover:bg-gray-300';
    });
    if (tab === 'cart') loadProducts();
}

// ────────── 加载商品列表 ──────────
function loadProducts() {
    fetch('/api/products?limit=200')
        .then(r => r.json())
        .then(data => {
            products = data;
            renderProductList();
        });
}

function renderProductList(filter = '') {
    const el = document.getElementById('productList');
    const filtered = filter
        ? products.filter(p => p.name.includes(filter) || (p.category || '').includes(filter) || (p.product_id || '').includes(filter))
        : products;

    if (filtered.length === 0) {
        el.innerHTML = '<div class="text-center py-8 text-gray-400 text-sm">暂无商品</div>';
        return;
    }

    el.innerHTML = filtered.map(p => {
        const inCart = cart.find(c => c.product_id === p.product_id);
        const cartQty = inCart ? inCart.quantity : 0;
        const lowStock = (p.stock || 0) <= 5 && (p.stock || 0) > 0;
        const outOfStock = (p.stock || 0) <= 0;
        return `<div class="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50 transition-colors ${outOfStock ? 'opacity-40' : ''}">
            <div class="flex-1 min-w-0">
                <div class="text-sm font-medium text-gray-800 truncate">${p.name}</div>
                <div class="flex items-center gap-2 text-xs text-gray-400">
                    <span>¥${(p.selling_price || 0).toFixed(2)}</span>
                    <span class="${lowStock ? 'text-red-400' : ''}">${p.stock || 0} ${p.unit || '个'}</span>
                </div>
            </div>
            <div class="flex items-center gap-1 ml-2">
                ${outOfStock
                    ? '<span class="text-xs text-red-400">缺货</span>'
                    : cartQty > 0
                        ? `<button class="w-6 h-6 flex items-center justify-center rounded bg-gray-100 text-gray-600 hover:bg-gray-200 text-xs" onclick="changeQty('${p.product_id}', -1)">−</button>
                           <span class="w-6 text-center text-sm font-medium">${cartQty}</span>
                           <button class="w-6 h-6 flex items-center justify-center rounded bg-blue-100 text-blue-600 hover:bg-blue-200 text-xs" onclick="changeQty('${p.product_id}', 1)">+</button>`
                        : `<button class="px-2.5 py-1 text-xs rounded bg-blue-50 text-blue-600 hover:bg-blue-100 transition-colors" onclick="changeQty('${p.product_id}', 1)">+ 加入</button>`
                }
            </div>
        </div>`;
    }).join('');
}

// ────────── 购物车操作 ──────────
function changeQty(productId, delta) {
    const p = products.find(x => x.product_id === productId);
    if (!p) return;

    const existing = cart.find(c => c.product_id === productId);
    if (existing) {
        existing.quantity += delta;
        existing.total_price = existing.quantity * existing.unit_price;
        if (existing.quantity <= 0) {
            cart = cart.filter(c => c.product_id !== productId);
        }
    } else if (delta > 0) {
        cart.push({
            product_id: p.product_id,
            product_name: p.name,
            unit_price: parseFloat(p.selling_price || 0),
            quantity: 1,
            total_price: parseFloat(p.selling_price || 0),
            stock: p.stock || 0
        });
    }

    renderProductList(document.getElementById('productSearch')?.value || '');
    renderCart();
}

function renderCart() {
    const el = document.getElementById('cartItems');
    const countEl = document.getElementById('cartCount');
    const subtotalEl = document.getElementById('cartSubtotal');

    countEl.textContent = `${cart.length} 件`;

    if (cart.length === 0) {
        el.innerHTML = '<div class="text-center py-8 text-gray-400 text-sm">购物车为空</div>';
        subtotalEl.textContent = '¥0.00';
        document.getElementById('checkoutBtn').disabled = true;
        return;
    }

    const total = cart.reduce((s, c) => s + c.total_price, 0);
    subtotalEl.textContent = `¥${total.toFixed(2)}`;
    document.getElementById('checkoutBtn').disabled = false;

    el.innerHTML = cart.map(c => `<div class="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50">
        <div class="flex-1 min-w-0">
            <div class="text-sm text-gray-800 truncate">${c.product_name}</div>
            <div class="text-xs text-gray-400">¥${c.unit_price.toFixed(2)} x ${c.quantity}</div>
        </div>
        <div class="flex items-center gap-2">
            <span class="text-sm font-medium text-gray-800">¥${c.total_price.toFixed(2)}</span>
            <button class="text-red-400 hover:text-red-600 text-xs" onclick="removeFromCart('${c.product_id}')">✕</button>
        </div>
    </div>`).join('');
}

function removeFromCart(productId) {
    cart = cart.filter(c => c.product_id !== productId);
    renderProductList(document.getElementById('productSearch')?.value || '');
    renderCart();
}

function filterProducts() {
    renderProductList(document.getElementById('productSearch')?.value || '');
}

// ────────── 会员查询 ──────────
let memberLookupTimer = null;

function lookupMember() {
    clearTimeout(memberLookupTimer);
    const id = document.getElementById('checkoutMemberId').value.trim();
    if (!id) {
        document.getElementById('checkoutMemberName').value = '';
        document.getElementById('balanceInfo').classList.add('hidden');
        currentMember = null;
        return;
    }
    memberLookupTimer = setTimeout(() => {
        fetch(`/api/members/${id}`)
            .then(r => r.ok ? r.json() : null)
            .then(m => {
                if (m) {
                    document.getElementById('checkoutMemberName').value = m.name;
                    document.getElementById('balanceInfo').classList.remove('hidden');
                    document.getElementById('balanceInfo').textContent = `💰 储值余额: ¥${(m.balance || 0).toFixed(2)}`;
                    currentMember = m;
                } else {
                    document.getElementById('checkoutMemberName').value = '未找到';
                    document.getElementById('balanceInfo').classList.add('hidden');
                    currentMember = null;
                }
            });
    }, 300);
}

// ────────── 提交购物车 ──────────
function submitCart() {
    if (cart.length === 0) return;

    const memberId = document.getElementById('checkoutMemberId').value.trim();
    const memberName = document.getElementById('checkoutMemberName').value;
    const useBalance = document.getElementById('useBalance').checked;
    const paymentMethod = document.getElementById('paymentMethod').value;
    const operator = document.getElementById('checkoutOperator').value.trim();

    if (useBalance && !memberId) {
        alert('请先选择会员');
        return;
    }

    const body = {
        items: cart.map(c => ({
            product_id: c.product_id,
            product_name: c.product_name,
            quantity: c.quantity,
            unit_price: c.unit_price,
            total_price: c.total_price
        })),
        member_id: memberId,
        member_name: memberName === '未找到' ? '' : memberName,
        payment_method: paymentMethod,
        use_balance: useBalance,
        operator: operator,
        remark: ''
    };

    document.getElementById('checkoutBtn').disabled = true;
    document.getElementById('checkoutBtn').textContent = '⏳ 提交中...';

    fetch('/api/product-sales/batch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body)
    })
        .then(r => r.json().then(j => ({ok: r.ok, data: j})))
        .then(({ok, data}) => {
            if (!ok) {
                alert(data.detail || '提交失败');
                document.getElementById('checkoutBtn').disabled = false;
                document.getElementById('checkoutBtn').textContent = '🛒 确认结账';
                return;
            }
            cart = [];
            renderCart();
            renderProductList(document.getElementById('productSearch')?.value || '');
            document.getElementById('checkoutMemberId').value = '';
            document.getElementById('checkoutMemberName').value = '';
            document.getElementById('balanceInfo').classList.add('hidden');
            document.getElementById('useBalance').checked = false;
            document.getElementById('checkoutOperator').value = '';
            currentMember = null;

            alert(`✅ ${data.message}`);

            document.getElementById('checkoutBtn').disabled = false;
            document.getElementById('checkoutBtn').textContent = '🛒 确认结账';
        })
        .catch(err => {
            alert('网络错误: ' + err.message);
            document.getElementById('checkoutBtn').disabled = false;
            document.getElementById('checkoutBtn').textContent = '🛒 确认结账';
        });
}

// ────────── 新增商品 ──────────
function closeAddProduct() {
    document.getElementById('addProductModal').classList.add('hidden');
}

function saveNewProduct(event) {
    event.preventDefault();
    const form = document.getElementById('addProductForm');
    const data = {
        name: form.querySelector('[name="name"]').value,
        category: form.querySelector('[name="category"]').value,
        cost_price: parseFloat(form.querySelector('[name="cost_price"]').value) || 0,
        selling_price: parseFloat(form.querySelector('[name="selling_price"]').value) || 0,
        stock: parseInt(form.querySelector('[name="stock"]').value) || 0,
        min_stock: parseInt(form.querySelector('[name="min_stock"]').value) || 0,
        unit: form.querySelector('[name="unit"]').value || '个',
        supplier: form.querySelector('[name="supplier"]').value,
        remark: ''
    };
    fetch('/api/products', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(r => {
        if (!r.ok) throw new Error('保存失败');
        closeAddProduct();
        form.reset();
        refreshProductTable();
        loadProducts();
    })
    .catch(err => alert(err.message));
    return false;
}

// ────────── 编辑商品 ──────────
function openEditProduct(productId) {
    fetch('/api/products?limit=500')
        .then(r => r.json())
        .then(list => {
            const p = list.find(x => x.product_id === productId);
            if (!p) { alert('商品不存在'); return; }
            document.getElementById('editProductId').value = p.product_id;
            document.getElementById('editName').value = p.name;
            document.getElementById('editCategory').value = p.category || '';
            document.getElementById('editCostPrice').value = p.cost_price || 0;
            document.getElementById('editSellingPrice').value = p.selling_price || 0;
            document.getElementById('editStock').value = p.stock || 0;
            document.getElementById('editMinStock').value = p.min_stock || 0;
            document.getElementById('editUnit').value = p.unit || '个';
            document.getElementById('editSupplier').value = p.supplier || '';
            document.getElementById('editProductModal').classList.remove('hidden');
        });
}

function closeEditProduct() {
    document.getElementById('editProductModal').classList.add('hidden');
}

function saveEditProduct() {
    const productId = document.getElementById('editProductId').value;
    const data = {
        name: document.getElementById('editName').value,
        category: document.getElementById('editCategory').value,
        cost_price: parseFloat(document.getElementById('editCostPrice').value) || 0,
        selling_price: parseFloat(document.getElementById('editSellingPrice').value) || 0,
        stock: parseInt(document.getElementById('editStock').value) || 0,
        min_stock: parseInt(document.getElementById('editMinStock').value) || 0,
        unit: document.getElementById('editUnit').value || '个',
        supplier: document.getElementById('editSupplier').value,
        remark: ''
    };
    fetch('/api/products/' + productId, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(r => {
        if (!r.ok) throw new Error('保存失败');
        closeEditProduct();
        refreshProductTable();
        loadProducts();
    })
    .catch(err => alert(err.message));
}

// ────────── 库存盘点 ──────────
function openAdjustStock(productId) {
    fetch('/api/products?limit=500')
        .then(r => r.json())
        .then(list => {
            const p = list.find(x => x.product_id === productId);
            if (!p) { alert('商品不存在'); return; }
            document.getElementById('adjustProductId').value = p.product_id;
            document.getElementById('adjustProductName').textContent = p.name;
            document.getElementById('adjustCurrentStock').textContent = (p.stock || 0) + ' ' + (p.unit || '个');
            document.getElementById('adjustNewStock').value = p.stock || 0;
            document.getElementById('adjustReason').value = '';
            document.getElementById('adjustStockModal').classList.remove('hidden');
        });
}

function closeAdjustStock() {
    document.getElementById('adjustStockModal').classList.add('hidden');
}

function saveAdjustStock() {
    const productId = document.getElementById('adjustProductId').value;
    const newStock = parseInt(document.getElementById('adjustNewStock').value) || 0;
    const reason = document.getElementById('adjustReason').value;

    fetch('/api/products/' + productId + '/adjust-stock?new_stock=' + newStock + '&reason=' + encodeURIComponent(reason), {
        method: 'PUT'
    })
    .then(r => {
        if (!r.ok) throw new Error('调整失败');
        closeAdjustStock();
        refreshProductTable();
        loadProducts();
    })
    .catch(err => alert(err.message));
}

// ────────── 进货入库 ──────────
function openAddInbound() {
    fetch('/api/products/inbounds/form-options')
        .then(r => r.text())
        .then(html => {
            document.getElementById('inboundProductSelect').innerHTML = html;
            const today = new Date().toISOString().split('T')[0];
            document.getElementById('inboundDate').value = today;
            document.getElementById('inboundQty').value = 1;
            document.getElementById('inboundUnitCost').value = 0;
            document.getElementById('inboundSupplier').value = '';
            document.getElementById('inboundOperator').value = '';
            document.getElementById('inboundRemark').value = '';
            // Auto-fill supplier and cost when product changes
            const sel = document.getElementById('inboundProduct');
            sel.addEventListener('change', function() {
                const opt = this.options[this.selectedIndex];
                if (opt && opt.value) {
                    document.getElementById('inboundSupplier').value = opt.dataset.supplier || '';
                    if (parseFloat(opt.dataset.cost) > 0) {
                        document.getElementById('inboundUnitCost').value = opt.dataset.cost;
                    }
                }
            });
            document.getElementById('addInboundModal').classList.remove('hidden');
        });
}

function closeAddInbound() {
    document.getElementById('addInboundModal').classList.add('hidden');
}

function saveInbound() {
    const select = document.getElementById('inboundProduct');
    const productId = select.value;
    if (!productId) { alert('请选择商品'); return; }

    const data = {
        product_id: productId,
        quantity: parseInt(document.getElementById('inboundQty').value) || 1,
        unit_cost: parseFloat(document.getElementById('inboundUnitCost').value) || 0,
        supplier: document.getElementById('inboundSupplier').value,
        inbound_date: document.getElementById('inboundDate').value,
        operator: document.getElementById('inboundOperator').value,
        remark: document.getElementById('inboundRemark').value
    };

    fetch('/api/products/inbounds', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    })
    .then(r => {
        if (!r.ok) return r.json().then(j => { throw new Error(j.detail || '入库失败'); });
        return r.json();
    })
    .then(result => {
        closeAddInbound();
        alert('✅ ' + result.message);
        refreshInboundTable();
        loadProducts();
    })
    .catch(err => alert(err.message));
}

// ────────── 通用刷新 ──────────
function refreshProductTable() {
    fetch('/api/products/table')
        .then(r => r.text())
        .then(html => { document.getElementById('productTable').innerHTML = html; });
}

function refreshInboundTable() {
    fetch('/api/products/inbounds/table')
        .then(r => r.text())
        .then(html => { document.getElementById('inboundTable').innerHTML = html; });
}

// ────────── 加载完成时自动加载商品 ──────────
document.addEventListener('DOMContentLoaded', () => {
    loadProducts();
});