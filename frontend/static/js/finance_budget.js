// ── 预算管理 ──
var _budgetType = 'expense';
var _currentType = 'expense';
var incomeCategories = ['售课收入', '商品零售', '会籍卡', '私教课程', '团课收入', '储物柜租金', '其他'];
var expenseCategories = ['房租', '物业水电', '工资', '设备', '办公用品', '快递费', '打印费', '通讯费', '差旅费', '招待费', '维修费', '网络费', '保险费', '税费', '其他'];

// 初始化月份
(function() {
    var m = document.getElementById('budgetMonth');
    var d = new Date();
    m.value = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
})();

function switchType(type) {
    _budgetType = type;
    _currentType = type;
    document.getElementById('tabExpense').className = (type === 'expense' ? 'px-3 py-1.5 rounded text-sm font-medium bg-blue-600 text-white' : 'px-3 py-1.5 rounded text-sm bg-gray-200 text-gray-600 hover:bg-gray-300');
    document.getElementById('tabIncome').className = (type === 'income' ? 'px-3 py-1.5 rounded text-sm font-medium bg-blue-600 text-white' : 'px-3 py-1.5 rounded text-sm bg-gray-200 text-gray-600 hover:bg-gray-300');
    loadBudget();
}

function loadBudget() {
    var month = document.getElementById('budgetMonth').value;
    // 概览
    fetch('/api/finance-budget/overview?month=' + encodeURIComponent(month))
        .then(function(r) { return r.text(); })
        .then(function(html) { document.getElementById('budgetOverview').innerHTML = html; });
    // 表格
    fetch('/api/finance-budget/table?month=' + encodeURIComponent(month) + '&type=' + encodeURIComponent(_currentType))
        .then(function(r) { return r.text(); })
        .then(function(html) { document.getElementById('budgetTable').innerHTML = html; });
}

function openAddBudget() {
    document.getElementById('budgetModalTitle').textContent = '添加预算';
    document.getElementById('editBudgetId').value = '';
    document.getElementById('budgetAmount').value = '';
    document.getElementById('budgetNote').value = '';
    // 填充类别下拉
    var sel = document.getElementById('budgetCategory');
    var cats = _budgetType === 'income' ? incomeCategories : expenseCategories;
    sel.innerHTML = '';
    cats.forEach(function(c) {
        var opt = document.createElement('option');
        opt.value = c; opt.textContent = c;
        sel.appendChild(opt);
    });
    document.getElementById('budgetModal').classList.remove('hidden');
}

function closeBudgetModal() {
    document.getElementById('budgetModal').classList.add('hidden');
}

function submitBudget() {
    var editId = document.getElementById('editBudgetId').value;
    var data = {
        month: document.getElementById('budgetMonth').value,
        category: document.getElementById('budgetCategory').value,
        type: _budgetType,
        planned_amount: parseFloat(document.getElementById('budgetAmount').value) || 0,
        note: document.getElementById('budgetNote').value.trim(),
    };
    if (!data.month || !data.category) return;

    var url = editId ? '/api/finance-budget/' + editId : '/api/finance-budget/create';
    var method = editId ? 'PUT' : 'POST';

    fetch(url, {
        method: method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data),
    }).then(function(r) { return r.json(); }).then(function(res) {
        if (res.success) {
            closeBudgetModal();
            loadBudget();
        }
    });
}

function editBudget(id) {
    // 因为预算没有单条 GET 端点，用表格数据填充
    document.getElementById('budgetModalTitle').textContent = '编辑预算';
    document.getElementById('editBudgetId').value = id;
    // 从表格行获取数据
    var row = document.querySelector('button[onclick*="' + id + '"]').closest('tr');
    if (!row) return;
    var cells = row.querySelectorAll('td');
    // cells: 0=编号, 1=类别, 2=预算金额, 3=实际金额, 4=执行率, 5=备注, 6=操作
    var category = cells[1].textContent.trim();
    var amount = cells[2].textContent.trim();
    var note = cells[5].textContent.trim();

    // 填充类别下拉
    var sel = document.getElementById('budgetCategory');
    var cats = _budgetType === 'income' ? incomeCategories : expenseCategories;
    sel.innerHTML = '';
    cats.forEach(function(c) {
        var opt = document.createElement('option');
        opt.value = c; opt.textContent = c;
        if (c === category) opt.selected = true;
        sel.appendChild(opt);
    });
    document.getElementById('budgetAmount').value = parseFloat(amount) || 0;
    document.getElementById('budgetNote').value = note;
    document.getElementById('budgetModal').classList.remove('hidden');
}

function deleteBudget(id) {
    if (!confirm('确认删除此预算条目？')) return;
    fetch('/api/finance-budget/' + id, {method: 'DELETE'})
        .then(function(r) { return r.json(); })
        .then(function(res) {
            if (res.success) loadBudget();
        });
}
