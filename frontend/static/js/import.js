// ── 数据导入工作流 ──
var currentTaskId = null;
var progressInterval = null;

function switchType(type) {
    document.querySelectorAll('.import-tab').forEach(function(tab) {
        var cls = tab.dataset.type === type
            ? 'bg-blue-600 text-white'
            : 'text-gray-600 hover:bg-gray-100';
        tab.className = 'import-tab px-5 py-2 rounded-md text-sm font-medium transition-colors ' + cls;
    });

    document.getElementById('downloadLink').href = '/api/import/template/' + type;
    document.getElementById('importTypeInput').value = type;

    document.getElementById('uploadForm').classList.remove('hidden');
    document.getElementById('uploadResult').innerHTML = '';
    document.getElementById('execSection').classList.add('hidden');
    document.getElementById('progressSection').classList.add('hidden');
}

function onUploadComplete(evt) {
    var resultDiv = document.getElementById('uploadResult');
    var xhr = evt.detail.xhr;

    if (!evt.detail.successful) {
        var msg = '上传失败，请检查文件格式和内容';
        try {
            var err = JSON.parse(xhr.responseText);
            msg = err.detail || msg;
        } catch(e) {}
        resultDiv.innerHTML = '<div class="mt-2 p-3 bg-red-50 text-red-600 text-sm rounded-lg">' + msg + '</div>';
        return;
    }

    try {
        var data = JSON.parse(xhr.responseText);
        resultDiv.innerHTML = '';
        showPreview(data);
    } catch(e) {
        resultDiv.innerHTML = '<div class="mt-2 p-3 bg-red-50 text-red-600 text-sm rounded-lg">响应解析失败</div>';
    }
}

function showPreview(data) {
    var section = document.getElementById('execSection');
    section.classList.remove('hidden');

    document.getElementById('previewSummary').textContent =
        '共 ' + data.total_rows + ' 行数据' + (data.error_count > 0 ? '，' + data.error_count + ' 行有错误' : '');

    var html = '<table class="w-full text-xs"><thead class="bg-gray-50 text-left text-gray-500 uppercase sticky top-0"><tr>';
    for (var ni = 0; ni < data.header_names.length; ni++) {
        html += '<th class="px-3 py-2 whitespace-nowrap">' + data.header_names[ni] + '</th>';
    }
    html += '</tr></thead><tbody>';

    for (var ri = 0; ri < data.preview.length; ri++) {
        html += '<tr class="border-b hover:bg-gray-50">';
        for (var fi = 0; fi < data.header_fields.length; fi++) {
            var val = data.preview[ri][data.header_fields[fi]];
            if (val === null || val === undefined) val = '';
            html += '<td class="px-3 py-2 whitespace-nowrap">' + String(val) + '</td>';
        }
        html += '</tr>';
    }
    html += '</tbody></table>';
    document.getElementById('previewTable').innerHTML = html;

    currentTaskId = data.task_id;
    var btn = document.getElementById('executeBtn');
    btn.disabled = false;
    btn.onclick = function() { startImport(data.task_id); };
}

function startImport(taskId) {
    var btn = document.getElementById('executeBtn');
    btn.disabled = true;
    btn.textContent = '启动中...';

    fetch('/api/import/' + taskId + '/execute', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                document.getElementById('execSection').classList.add('hidden');
                document.getElementById('progressSection').classList.remove('hidden');
                pollProgress(taskId);
            } else {
                alert('启动失败');
                btn.disabled = false;
                btn.textContent = '开始导入';
            }
        })
        .catch(function(e) {
            alert('启动失败: ' + e.message);
            btn.disabled = false;
            btn.textContent = '开始导入';
        });
}

function pollProgress(taskId) {
    if (progressInterval) clearInterval(progressInterval);

    progressInterval = setInterval(function() {
        fetch('/api/import/' + taskId + '/progress')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                updateProgress(data);
                if (data.status === 'completed' || data.status === 'failed') {
                    clearInterval(progressInterval);
                    progressInterval = null;
                    onImportComplete(data);
                }
            })
            .catch(function() {});
    }, 1500);
}

function updateProgress(data) {
    var total = data.total_rows || 1;
    var done = data.success_count + data.error_count + data.skipped_count;
    var pct = Math.min(100, Math.round(done / total * 100));

    document.getElementById('progressBar').style.width = pct + '%';
    document.getElementById('statTotal').textContent = data.total_rows;
    document.getElementById('statSuccess').textContent = data.success_count;
    document.getElementById('statError').textContent = data.error_count;
    document.getElementById('statCreated').textContent = data.created_count;
    document.getElementById('statUpdated').textContent = data.updated_count;

    if (data.errors && data.errors.length > 0) {
        document.getElementById('errorDetails').classList.remove('hidden');
        document.getElementById('errorList').innerHTML = data.errors.map(function(e) {
            return '<div class="py-0.5">第 ' + e.row + ' 行: ' + e.message + '</div>';
        }).join('');
    }
}

function onImportComplete(data) {
    document.getElementById('importComplete').classList.remove('hidden');
    if (data.status === 'failed') {
        document.getElementById('progressBar').className = 'bg-red-600 h-4 rounded-full transition-all duration-500';
    }
    htmx.ajax('GET', '/api/import/history/table', { target: '#historyTable', swap: 'innerHTML' });
}

function resetImport() {
    document.getElementById('progressSection').classList.add('hidden');
    document.getElementById('importComplete').classList.add('hidden');
    document.getElementById('uploadForm').classList.remove('hidden');
    document.getElementById('uploadResult').innerHTML = '';
    document.getElementById('progressBar').style.width = '0%';
    document.getElementById('progressBar').className = 'bg-blue-600 h-4 rounded-full transition-all duration-500';
}
