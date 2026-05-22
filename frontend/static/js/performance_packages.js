// 全局排序机制：点击表格表头 → 服务端排序
document.addEventListener('htmx:afterSettle', function(e) {
    // 给所有带有 data-table 属性的表格附加排序监听
    const tables = document.querySelectorAll('table[data-table]');
    tables.forEach(table => {
        const thead = table.querySelector('thead');
        if (!thead || thead.dataset.sortAttached) return;
        thead.dataset.sortAttached = '1';

        thead.querySelectorAll('th[data-col]').forEach(th => {
            th.addEventListener('click', function() {
                const colIdx = this.dataset.col;
                const table = this.closest('table');
                const targetId = table?.dataset?.table;
                if (!targetId) return;

                const currentDir = this.querySelector('.sort-arrow')?.dataset?.dir || '';
                const newDir = currentDir === 'asc' ? 'desc' : 'asc';

                htmx.ajax('GET', `/api/performance/packages/table?sort=${colIdx}&dir=${newDir}`, {
                    target: '#' + targetId
                });
            });
        });
    });
});
