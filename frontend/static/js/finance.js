var currentTab = 'income';
var currentPage = 1;

// ── 切换 tab ──
function switchFinanceTab(tab) {
    currentTab = tab;
    currentPage = 1;
    document.getElementById('incomeSection').classList.toggle('hidden', tab !== 'income');
    document.getElementById('expenseSection').classList.toggle('hidden', tab !== 'expense');
    document.getElementById('tabIncome').className = (tab === 'income' ? 'px-4 py-2 text-sm rounded-lg bg-green-600 text-white' : 'px-4 py-2 text-sm rounded-lg bg-gray-200 text-gray-600 hover:bg-gray-300');
    document.getElementById('tabExpense').className = (tab === 'expense' ? 'px-4 py-2 text-sm rounded-lg bg-green-600 text-white' : 'px-4 py-2 text-sm rounded-lg bg-gray-200 text-gray-600 hover:bg-gray-300');
    updateFilterCategories();
    loadFinanceTable();
}

// ── 分类下拉动态更新 ──
var incomeCategories = ['售课收入', '商品零售', '会籍卡', '私教课程', '团课收入', '储物柜租金', '其他'];
var expenseCategories = ['房租', '物业水电', '工资', '设备', '办公用品', '快递费', '打印费', '通讯费', '差旅费', '招待费', '维修费', '网络费', '保险费', '税费', '其他'];

function updateFilterCategories() {
    var sel = document.getElementById('filterCategory');
    var cats = currentTab === 'income' ? incomeCategories : expenseCategories;
    var currentVal = sel.value;
    sel.innerHTML = '<option value="">全部分类</option>';
    cats.forEach(function(c) {
        var opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        if (c === currentVal) opt.selected = true;
        sel.appendChild(opt);
    });
}
updateFilterCategories();

// ── 加载表格（带筛选 + 分页）─ ─
function loadFinanceTable() {
    var y = document.getElementById('yearFilter').value || new Date().getFullYear();
    var m = document.getElementById('monthFilter').value || (new Date().getMonth() + 1);
    var q = document.getElementById('filterQ').value;
    var cat = document.getElementById('filterCategory').value;
    var url = '/api/finance/' + currentTab + '/table?year=' + y + '&month=' + m + '&page=' + currentPage;
    if (q) url += '&q=' + encodeURIComponent(q);
    if (cat) url += '&category=' + encodeURIComponent(cat);
    fetch(url).then(function(r) { return r.text(); }).then(function(html) {
        document.getElementById(currentTab === 'income' ? 'incomeTable' : 'expenseTable').innerHTML = html;
    });
    // 刷新汇总
    document.getElementById('financeSummary').setAttribute('hx-get', '/api/finance/summary?year='+y+'&month='+m);
    htmx.trigger('#financeSummary', 'load');
}

// ── 分页 ──
function goPage(p) {
    currentPage = p;
    loadFinanceTable();
}

// ── 筛选 ──
function doSearch() {
    currentPage = 1;
    loadFinanceTable();
}
function resetFilters() {
    document.getElementById('filterQ').value = '';
    document.getElementById('filterCategory').value = '';
    currentPage = 1;
    loadFinanceTable();
}

// ── CSV 导出 ──
function exportCSV() {
    var y = document.getElementById('yearFilter').value || new Date().getFullYear();
    var m = document.getElementById('monthFilter').value || (new Date().getMonth() + 1);
    var q = document.getElementById('filterQ').value;
    var cat = document.getElementById('filterCategory').value;
    var url = '/api/finance/export?type=' + currentTab + '&year=' + y + '&month=' + m;
    if (q) url += '&q=' + encodeURIComponent(q);
    if (cat) url += '&category=' + encodeURIComponent(cat);
    window.open(url, '_blank');
}

// ── 新增收入 ──
function submitIncome() {
    const form = document.getElementById('incomeForm');
    if (!form.checkValidity()) { form.reportValidity(); return; }
    const data = Object.fromEntries(new FormData(form));
    data.amount = parseFloat(data.amount) || 0;
    fetch('/api/finance/income', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(r => {
        if (!r.ok) throw new Error('保存失败');
        document.getElementById('addIncomeModal').classList.add('hidden');
        form.reset();
        currentPage = 1;
        switchFinanceTab('income');
    }).catch(e => alert('保存失败: ' + e.message));
}

// ── 新增支出 ──
function submitExpense() {
    const form = document.getElementById('expenseForm');
    if (!form.checkValidity()) { form.reportValidity(); return; }
    const data = Object.fromEntries(new FormData(form));
    data.amount = parseFloat(data.amount) || 0;
    fetch('/api/finance/expense', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(r => {
        if (!r.ok) throw new Error('保存失败');
        document.getElementById('addExpenseModal').classList.add('hidden');
        form.reset();
        currentPage = 1;
        switchFinanceTab('expense');
    }).catch(e => alert('保存失败: ' + e.message));
}

// ── 编辑收入 ──
var editIncomeId = null;

function openEditIncome(id) {
    editIncomeId = id;
    fetch('/api/finance/income/' + id)
        .then(function(r) { if (!r.ok) throw new Error('获取失败'); return r.json(); })
        .then(function(d) {
            document.getElementById('editIncomeId').value = id;
            document.getElementById('editIncomeDate').value = d.income_date || '';
            document.getElementById('editIncomeCategory').value = d.category || '';
            document.getElementById('editIncomeAmount').value = d.amount || 0;
            document.getElementById('editIncomeSource').value = d.source || '';
            document.getElementById('editIncomePayment').value = d.payment_method || '';
            document.getElementById('editIncomeRemark').value = d.remark || '';
            document.getElementById('editIncomeModal').classList.remove('hidden');
        })
        .catch(function(e) { alert('加载失败: ' + e.message); });
}

function closeEditIncomeModal() {
    document.getElementById('editIncomeModal').classList.add('hidden');
    editIncomeId = null;
}

function submitEditIncome() {
    const form = document.getElementById('editIncomeForm');
    if (!form.checkValidity()) { form.reportValidity(); return; }
    const data = Object.fromEntries(new FormData(form));
    data.amount = parseFloat(data.amount) || 0;
    fetch('/api/finance/income/' + editIncomeId, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(r => {
        if (!r.ok) throw new Error('保存失败');
        closeEditIncomeModal();
        loadFinanceTable();
    }).catch(e => alert('保存失败: ' + e.message));
}

// ── 编辑支出 ──
var editExpenseId = null;

function openEditExpense(id) {
    editExpenseId = id;
    fetch('/api/finance/expense/' + id)
        .then(function(r) { if (!r.ok) throw new Error('获取失败'); return r.json(); })
        .then(function(d) {
            document.getElementById('editExpenseId').value = id;
            document.getElementById('editExpenseDate').value = d.expense_date || '';
            document.getElementById('editExpenseCategory').value = d.category || '';
            document.getElementById('editExpenseAmount').value = d.amount || 0;
            document.getElementById('editExpensePayee').value = d.payee || '';
            document.getElementById('editExpensePayment').value = d.payment_method || '';
            document.getElementById('editExpenseRemark').value = d.remark || '';
            document.getElementById('editExpenseModal').classList.remove('hidden');
        })
        .catch(function(e) { alert('加载失败: ' + e.message); });
}

function closeEditExpenseModal() {
    document.getElementById('editExpenseModal').classList.add('hidden');
    editExpenseId = null;
}

function submitEditExpense() {
    const form = document.getElementById('editExpenseForm');
    if (!form.checkValidity()) { form.reportValidity(); return; }
    const data = Object.fromEntries(new FormData(form));
    data.amount = parseFloat(data.amount) || 0;
    fetch('/api/finance/expense/' + editExpenseId, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(r => {
        if (!r.ok) throw new Error('保存失败');
        closeEditExpenseModal();
        loadFinanceTable();
    }).catch(e => alert('保存失败: ' + e.message));
}
