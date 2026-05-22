let currentYear = window._pageData.year;
let currentMonth = window._pageData.month;

// ════════════════════════════════════════════
// 初始化
// ════════════════════════════════════════════

function init() {
    const now = new Date();
    currentYear = now.getFullYear();
    currentMonth = now.getMonth() + 1;
    loadCoachList();
    refreshCalendar();
}

function loadCoachList() {
    fetch('/api/schedule/coach-list')
        .then(r => r.json())
        .then(coaches => {
            const sel = document.getElementById('coachFilter');
            sel.innerHTML = coaches.map(c =>
                `<option value="${c.staff_id}">${c.name}${c.position ? ' ('+c.position+')' : ''}</option>`
            ).join('');
        });
}

function refreshCalendar() {
    const coachId = document.getElementById('coachFilter').value;
    const params = `year=${currentYear}&month=${currentMonth}&coach_id=${coachId}`;

    // 更新月份标签
    document.getElementById('monthLabel').textContent = `${currentYear}年${currentMonth}月`;

    // 更新统计
    const statsEl = document.getElementById('statsSection');
    statsEl.innerHTML = '<div class="text-center py-4 text-gray-400">加载中...</div>';
    htmx.ajax('GET', `/api/schedule/stats?${params}`, {target: '#statsSection'});

    // 更新月历
    const calEl = document.getElementById('calendarSection');
    calEl.innerHTML = '<div class="text-center py-8 text-gray-400">加载月历...</div>';
    htmx.ajax('GET', `/api/schedule/calendar?${params}`, {target: '#calendarSection'});

    // 隐藏详情
    document.getElementById('dayDetailSection').classList.add('hidden');
}

function navigateMonth(delta) {
    currentMonth += delta;
    if (currentMonth > 12) { currentMonth = 1; currentYear++; }
    if (currentMonth < 1) { currentMonth = 12; currentYear--; }
    refreshCalendar();
}

function goToday() {
    const now = new Date();
    currentYear = now.getFullYear();
    currentMonth = now.getMonth() + 1;
    refreshCalendar();
}

// 点击日期显示详情
function showDayDetail(dateStr) {
    const coachId = document.getElementById('coachFilter').value;
    const section = document.getElementById('dayDetailSection');
    section.classList.remove('hidden');
    section.innerHTML = '<div class="text-center py-4 text-gray-400">加载中...</div>';

    const params = new URLSearchParams({date_str: dateStr});
    if (coachId) params.set('coach_id', coachId);

    fetch(`/api/schedule/day-detail?${params.toString()}`)
        .then(r => r.text())
        .then(html => {
            section.innerHTML = html;
            section.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        });
}

// 初始化
init();
