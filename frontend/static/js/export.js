let tables = [];  // [{key, name}]
let fieldsMap = {};  // {tableKey: [{key, name, type}]}
let selectedFields = {};  // {tableKey: [key, ...]}
let singleTableKey = '';  // current single selected table for field display

// ────────── 初始化 ──────────
document.addEventListener('DOMContentLoaded', async () => {
    const res = await fetch('/api/export/tables');
    tables = await res.json();
    renderTableGrid();
});

function renderTableGrid() {
    const grid = document.getElementById('tableGrid');
    grid.innerHTML = tables.map(t => `
        <label class="flex items-center gap-2 px-3 py-2.5 rounded-lg border cursor-pointer transition-all
                      hover:border-blue-300 bg-gray-50/50 table-checkbox-label"
               data-key="${t.key}"
               onclick="onTableToggle('${t.key}')">
            <input type="checkbox" class="table-checkbox rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                   data-key="${t.key}">
            <span class="text-sm text-gray-700 select-none">${t.name}</span>
        </label>
    `).join('');
    updateCounts();
}

// ────────── 表选择 ──────────
function onTableToggle(key) {
    const cb = document.querySelector(`.table-checkbox[data-key="${key}"]`);
    cb.checked = !cb.checked;
    const label = document.querySelector(`.table-checkbox-label[data-key="${key}"]`);
    label.classList.toggle('border-blue-400', cb.checked);
    label.classList.toggle('bg-blue-50', cb.checked);
    label.classList.toggle('bg-gray-50/50', !cb.checked);
    updateCounts();
    updateFieldSection();
}

function toggleAllTables(checked) {
    document.querySelectorAll('.table-checkbox').forEach(cb => {
        cb.checked = checked;
        const label = document.querySelector(`.table-checkbox-label[data-key="${cb.dataset.key}"]`);
        label.classList.toggle('border-blue-400', checked);
        label.classList.toggle('bg-blue-50', checked);
        label.classList.toggle('bg-gray-50/50', !checked);
    });
    updateCounts();
    updateFieldSection();
}

function getSelectedTables() {
    return Array.from(document.querySelectorAll('.table-checkbox:checked')).map(cb => cb.dataset.key);
}

function updateCounts() {
    const sel = getSelectedTables();
    document.getElementById('selectedCount').textContent = `已选 ${sel.length} 个`;
    document.getElementById('batchCount').textContent = sel.length;
    document.getElementById('btnDownloadSingle').disabled = sel.length !== 1;
    document.getElementById('btnBatchDownload').disabled = sel.length === 0;
}

// ────────── 字段选择 ──────────
async function updateFieldSection() {
    const sel = getSelectedTables();
    const section = document.getElementById('fieldSection');

    if (sel.length === 1) {
        const key = sel[0];
        singleTableKey = key;
        document.getElementById('fieldTableName').textContent = `（${tables.find(t => t.key === key)?.name || key}）`;

        // 加载字段
        if (!fieldsMap[key]) {
            try {
                const res = await fetch(`/api/export/${key}/fields`);
                fieldsMap[key] = await res.json();
            } catch (e) {
                fieldsMap[key] = [];
            }
            // 默认全选
            selectedFields[key] = fieldsMap[key].map(f => f.key);
        }

        renderFields(key);
        section.classList.remove('hidden');
    } else {
        section.classList.add('hidden');
        singleTableKey = '';
    }
}

function renderFields(key) {
    const fields = fieldsMap[key] || [];
    const sel = selectedFields[key] || [];
    const grid = document.getElementById('fieldGrid');
    grid.innerHTML = fields.map(f => `
        <label class="flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer hover:bg-white text-xs ${sel.includes(f.key) ? 'bg-white' : ''}">
            <input type="checkbox" class="field-checkbox rounded border-gray-300 text-blue-600"
                   data-key="${f.key}" ${sel.includes(f.key) ? 'checked' : ''}
                   onchange="onFieldToggle('${key}', '${f.key}')">
            <span class="truncate" title="${f.name}">${f.name}</span>
        </label>
    `).join('');
    document.getElementById('fieldCount').textContent = `${sel.length}/${fields.length} 字段`;
}

function onFieldToggle(tableKey, fieldKey) {
    if (!selectedFields[tableKey]) selectedFields[tableKey] = [];
    const idx = selectedFields[tableKey].indexOf(fieldKey);
    if (idx >= 0) selectedFields[tableKey].splice(idx, 1);
    else selectedFields[tableKey].push(fieldKey);
    const fields = fieldsMap[tableKey] || [];
    document.getElementById('fieldCount').textContent = `${selectedFields[tableKey].length}/${fields.length} 字段`;
}

function toggleAllFields(checked) {
    const key = singleTableKey;
    if (!key || !fieldsMap[key]) return;
    selectedFields[key] = checked ? fieldsMap[key].map(f => f.key) : [];
    renderFields(key);
}

// ────────── 格式 ──────────
function onFormatChange() {
    // Nothing special needed
}

function getFormat() {
    return document.querySelector('input[name="exportFormat"]:checked')?.value || 'csv';
}

// ────────── 下载 ──────────
function downloadSelected() {
    const sel = getSelectedTables();
    if (sel.length !== 1) return;
    const key = sel[0];
    const format = getFormat();
    const dateFrom = document.getElementById('filterDateFrom').value;
    const dateTo = document.getElementById('filterDateTo').value;

    // Detect date columns for this table
    const dateCols = {
        "members": "signup_date", "staff": "hire_date", "sales": "sale_date",
        "class_records": "class_date", "checkins": "checkin_date",
        "body_measurements": "measure_date", "recharges": "recharge_date",
        "membership_cards": "start_date", "product_sales": "sale_date",
        "finance_income": "income_date", "finance_expense": "expense_date",
        "operation_logs": "created_at",
    };
    const dateCol = dateCols[key] || '';

    let params = `format=${format}`;
    if (dateFrom && dateCol) params += `&date_from=${dateFrom}&date_col=${dateCol}`;
    if (dateTo && dateCol) params += `&date_to=${dateTo}`;

    // Selected fields
    const selFields = selectedFields[key];
    if (selFields && selFields.length > 0 && selFields.length < (fieldsMap[key] || []).length) {
        params += `&fields=${selFields.join(',')}`;
    }

    window.open(`/api/export/${key}?${params}`, '_blank');
}

function batchDownload() {
    const sel = getSelectedTables();
    if (sel.length === 0) return;

    const format = getFormat();
    const dateFrom = document.getElementById('filterDateFrom').value;
    const dateTo = document.getElementById('filterDateTo').value;

    const btn = document.getElementById('btnBatchDownload');
    btn.disabled = true;
    btn.textContent = '⏳ 打包中...';

    fetch('/api/export/batch', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            tables: sel,
            format: format,
            date_from: dateFrom,
            date_to: dateTo,
        })
    })
    .then(r => {
        if (!r.ok) throw new Error('导出失败');
        return r.blob();
    })
    .then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const dateStr = new Date().toISOString().split('T')[0];
        a.download = `批量导出_${dateStr}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    })
    .catch(err => alert(err.message))
    .finally(() => {
        btn.disabled = false;
        btn.innerHTML = '📦 打包下载（<span id="batchCount">' + sel.length + '</span> 个表）';
    });
}
