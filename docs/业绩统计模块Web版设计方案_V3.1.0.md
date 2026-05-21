# 业绩统计模块 Web 版设计方案

## V3.1.0 | 2026-05-08

---

## 一、概述

### 1.1 改造目标
在现有网页版（V3.0.1）基础上，新增完整的**业绩统计模块**，包含 5 个子页面，覆盖单机版 V2.15.1 全部功能。

### 1.2 设计原则
- 延续现有 HTMX + Tailwind CSS 风格（零 JS 优先）
- 统计计算结果由后端生成 HTML 片段返回（避免前端复杂运算）
- 所有页面支持时间筛选（今日/本周/本月/全部）
- 新增导航入口：单独"业绩统计"菜单，下辖 5 个子页面

### 1.3 依赖数据源

| 数据表 | 字段 | 用途 |
|--------|------|------|
| `sale` | sale_date, actual_amount, end_date | 售课统计、到期计算 |
| `lesson_package` | total_hours, used_hours, remaining_hours, status, price | 课程包业绩 |
| `membership_card` | card_type, price, status, start_date, end_date | 会籍卡业绩 |
| `checkin` | checkin_date, checkin_time, checkin_type | 进场统计 |

---

## 二、页面设计

### 2.1 导航结构

在导航栏新增菜单组：
```
数据分析
├── 📊 业绩总览    → /performance
├── 💳 售课业绩     → /performance/sales
├── 📦 课程包业绩   → /performance/packages
├── 🎫 会籍卡业绩   → /performance/cards
└── 🏃 会员进场     → /performance/checkins
```

### 2.2 页面 1：业绩总览看板 `/performance`

#### 布局
```
┌──────────────────────────────────────────────────┐
│ 📊 业绩总览                         时间筛选：[▼]│
├────────────┬───────────┬───────────┬────────────┤
│ 💰 本月售课  │ 📦 课程包  │ 🎫 会籍卡  │ 🏃 进场人次│
│ ¥99,800    │ ¥45,000   │ ¥18,000   │ 126 人     │
│ 较上月 +12%  │ 成交 45 笔 │ 售出 28 张 │ 日均 4.2人 │
├────────────┴───────────┴───────────┴────────────┤
│ 趋势 / 详细数据入口                               │
└──────────────────────────────────────────────────┘
```

#### API 端点

```python
GET /api/performance/overview?period=本月
→ {
    sale_month_total: 99800,        # 本月售课总额
    sale_month_count: 23,           # 本月售课笔数
    sale_prev_month_total: 89000,   # 上月对比
    
    package_total: 45000,           # 课程包总额（全部有效）
    package_count: 19,              # 课程包总数
    package_active_count: 15,       # 有效课程包数
    
    card_total: 18000,              # 会籍卡总额（全部有效）
    card_count: 8,                  # 会籍卡总数
    card_active_count: 6,           # 有效卡数
    
    checkin_total: 126,             # 总进场人次
    checkin_today: 8,               # 今日进场人次
    checkin_avg_daily: 4.2,         # 日均进场
    
    labels: ["1日","2日",...],      # 趋势图数据
    sale_daily: [3200,4500,...],
    checkin_daily: [3,5,...],
}
```

**实现方式**：后端从 4 张表分别聚合，返回 JSON → 前端用 HTML 片段渲染卡片。

#### 时间筛选

| 选项 | 筛选条件 |
|------|---------|
| 今日 | sale_date = today |
| 本周 | sale_date >= 本周一 |
| 本月 | sale_date >= 本月1日 |
| 上月 | sale_date BETWEEN 上月1日 AND 上月最后一日 |
| 本年 | sale_date >= 本年1月1日 |
| 全部 | 无筛选 |

> 课程包和会籍卡业绩不严格依赖时间筛选（统计"当前有效"数据为主），但可展示趋势

---

### 2.3 页面 2：售课业绩 `/performance/sales`

#### 布局

```
┌──────────────────────────────────────────────────┐
│ 💳 售课业绩                         时间筛选：[▼]   │
├────────────┬──────────────┬──────────────────────┤
│ 售课总额     │ 售课笔数      │ 本月日均               │                        
│ ¥99,800    │ 23 笔        │ ¥3,327/日              │
├────────────┴──────────────┴──────────────────────┤
│ 售课明细（到期时间展示）                           │
├──────┬──────┬────────┬──────┬──────┬──────┬──────┤
│ 编号  │ 会员  │ 课程   │ 金额  │ 到期日 │ 剩余  │ 状态  │
├──────┼──────┼────────┼──────┼──────┼──────┼──────┤
│ S001 │ 张三 │ 私教课 │ 2700 │ 07-01 │ 54天  │ 🟢正常│
│ S002 │ 李四 │ 康复  │ 2800 │ 05-10 │ 2天   │ 🟠即将 │
│ S003 │ 王五 │ 瑜伽  │ 99   │ 04-15 │ -23天 │ 🔴过期│
└──────┴──────┴────────┴──────┴──────┴──────┴──────┘
```

#### 到期状态逻辑

| 条件 | 标签 | 颜色 |
|------|------|------|
| 剩余天数 < 0 | 已过期 | 🔴 红色（bg-red-100 text-red-700） |
| 剩余天数 ≤ 7 | 即将到期 | 🟠 橙色（bg-orange-100 text-orange-700） |
| 剩余天数 > 7 | 正常 | 🟢 绿色（bg-green-100 text-green-700） |
| end_date 为空 | — | 灰色（无标签） |

#### API 端点

```python
GET /api/performance/sales?period=本月&status=all
→ {
    total_amount: 99800,        # 合计金额
    total_count: 23,            # 笔数
    daily_avg: 3327,            # 日均
    expired_amount: 1200,       # 已过期金额
    expiring_amount: 3500,      # 即将到期金额
    sales: [
        {
            sale_id, member_name, course_name,
            actual_amount, sale_date, end_date,
            remaining_days, status  # "正常"|"即将到期"|"已过期"|""
        },
        ...
    ]
}
```

#### 实现方式
- 后端 SQLAlchemy 查询 sale 表
- 日期筛选在 SQL 层完成
- 到期状态在 Python 层计算（`(end_date - date.today()).days`）
- 返回 HTML 片段，包含统计卡片 + 表格

---

### 2.4 页面 3：课程包业绩 `/performance/packages`

#### 布局

```
┌──────────────────────────────────────────────────┐
│ 📦 课程包业绩                                     │
├────────────┬──────────────┬──────────────────────┤
│ 📊 已售包数  │ 💰 总金额     │ 📈 平均单价            │
│ 19 个      │ ¥45,000      │ ¥2,368               │
├────────────┼──────────────┼──────────────────────┤
│ 📚 课时统计  │ 🟢 有效       │ 🔴 已用完              │
│ 190 课时   │ 15 个(78.9%)  │ 4 个(21.1%)           │
├────────────┴──────────────┴──────────────────────┤
│ 课程包明细（点击表头排序）                         │
├──────┬──────┬────┬────┬────┬────┬──────┬────────┤
│ 编号  │ 会员 │ 课程│总课时│已用│剩余 │状态   │ 有效期 │
├──────┼──────┼────┼────┼────┼────┼──────┼────────┤
│ PK01 │ 张三 │ 普拉提│10 │ 0 │ 10 │🟢有效 │ 05-06 │
│ PK02 │ 李四 │ 康复  │10 │ 0 │ 10 │🟢有效 │ 05-06 │
└──────┴──────┴────┴────┴────┴────┴──────┴────────┘
```

#### API 端点

```python
GET /api/performance/packages
→ {
    total_count: 19,                # 已售包数
    total_amount: 45000,            # 总金额（无 price 字段时从 sale 关联）
    avg_price: 2368,                # 平均单价
    total_hours: 190,               # 总课时数
    used_hours: 30,                 # 已消耗课时
    remaining_hours: 160,           # 剩余课时
    active_count: 15,               # 有效包数
    expired_count: 4,               # 已用完/过期包数
    packages: [
        {
            package_id, member_name, course_name,
            total_hours, used_hours, remaining_hours,
            ratio,  # 消耗率 = used_hours/total_hours
            status, valid_until
        },
        ...
    ]
}
```

#### 排序功能
- 点击表头排序（纯前端 JS 实现，复用可排序组件）
- 排序规则：文本→字典序，数字→数值，日期→ISO 字符串

---

### 2.5 页面 4：会籍卡业绩 `/performance/cards`

#### 布局

```
┌──────────────────────────────────────────────────┐
│ 🎫 会籍卡业绩                   时间筛选：[▼]       │
├────────────┬──────────────┬──────────────────────┤
│ 📊 总售卡数  │ 💰 总金额     │ 📈 平均单价            │
│ 28 张      │ ¥118,099     │ ¥4,218               │
├──────┬──────┴──────┬──────┴──────────────────────┤
│ 类型  │ 售出数量    │ 销售额                      │
├──────┼─────────────┼────────────────────────────┤
│ 次卡  │ 12 张       │ ¥36,000                    │
│ 期限卡│ 10 张       │ ¥60,000                    │
│ 现金卡│ 6 张        │ ¥22,099                    │
├──────┴─────────────┴────────────────────────────┤
│ 会籍卡明细（按卡类型分组展示）                     │
└──────────────────────────────────────────────────┘
```

#### API 端点

```python
GET /api/performance/cards?period=全部
→ {
    total_count: 8,                 # 总卡数量
    total_amount: 118099,           # 总金额
    avg_price: 4218,                # 平均单价
    active_count: 6,                # 有效卡数
    expired_count: 2,               # 已过期卡数
    by_type: [                       # 按类型分组
        {card_type: "次卡", count: 3, amount: 36000},
        {card_type: "期限卡", count: 3, amount: 60000},
        {card_type: "现金卡", count: 2, amount: 22099},
    ],
    cards: [
        {
            card_id, member_name, card_type,
            price, start_date, end_date,
            duration_days, status
        },
        ...
    ]
}
```

---

### 2.6 页面 5：会员进场统计 `/performance/checkins`

#### 布局

```
┌──────────────────────────────────────────────────┐
│ 🏃 会员进场统计                   时间筛选：[▼]     │
├────────────┬──────────────┬──────────────────────┤
│ 📊 总进场    │ 📅 有进场天数  │ 📈 日均进场            │
│ 126 人次   │ 18 天        │ 7.0 人/日             │
├────────────┼──────────────┼──────────────────────┤
│ 🏆 单日最高  │ 📅 日期       │                      │
│ 15 人次    │ 2026-05-01   │                      │
├──────┬──────┴──────┬──────┴──────────────────────┤
│ 方式  │ 人次        │ 占比                        │
├──────┼─────────────┼────────────────────────────┤
│ 次卡  │ 45          │ 35.7%                      │
│ 现金卡│ 30          │ 23.8%                      │
│ 期限卡│ 25          │ 19.8%                      │
│ 临时  │ 26          │ 20.7%                      │
├──────┴─────────────┴────────────────────────────┤
│ 时段分布：早晨(6-9):10 ██      8%               │
│           上午(9-12):35 █████████  28%          │
│           下午(12-17):50 █████████████  40%     │
│           晚上(17-22):31 ████████  25%          │
└──────────────────────────────────────────────────┘
```

#### API 端点

```python
GET /api/performance/checkins?period=本月
→ {
    total: 126,                 # 总进场人次
    active_days: 18,            # 有进场的天数
    daily_avg: 7.0,             # 日均进场
    peak_day: "2026-05-01",    # 单日最高
    peak_count: 15,             # 单日最高人次
    
    by_type: [                   # 按进场方式
        {type: "次卡", count: 45},
        {type: "现金卡", count: 30},
        {type: "期限卡", count: 25},
        {type: "临时", count: 26},
    ],
    
    by_hour: [                  # 按时段
        {period: "清晨(6-9)", count: 10},
        {period: "上午(9-12)", count: 35},
        {period: "下午(12-17)", count: 50},
        {period: "晚上(17-22)", count: 31},
    ],
    
    daily: [                    # 每日趋势
        {date: "2026-05-01", count: 15},
        ...
    ]
}
```

#### 时段统计逻辑

```python
def get_period(hour: int) -> str:
    if 6 <= hour < 9: return "清晨(6-9)"
    if 9 <= hour < 12: return "上午(9-12)"
    if 12 <= hour < 17: return "下午(12-17)"
    if 17 <= hour < 22: return "晚上(17-22)"
    return "其他"
```

---

## 三、变更清单

### 3.1 新增文件

| # | 文件 | 说明 |
|:-:|------|------|
| 1 | `backend/routers/performance.py` | 5 个统计 API + 统计卡片 HTML 片段 |
| 2 | `frontend/templates/performance.html` | 业绩总览看板页面 |
| 3 | `frontend/templates/performance_sales.html` | 售课业绩页面 |
| 4 | `frontend/templates/performance_packages.html` | 课程包业绩页面 |
| 5 | `frontend/templates/performance_cards.html` | 会籍卡业绩页面 |
| 6 | `frontend/templates/performance_checkins.html` | 会员进场统计页面 |

### 3.2 修改文件

| # | 文件 | 说明 |
|:-:|------|------|
| 1 | `backend/app.py` | 注册 5 个页面路由 + performance 路由模块 + 导航栏新增"数据分析"菜单 |

### 3.3 删除文件
- 无

---

## 四、后端 API 完整清单

| 端点 | 方法 | 输入 | 返回 |
|------|------|------|------|
| `/performance` | GET | — | 业绩总览页面 |
| `/performance/sales` | GET | — | 售课业绩页面 |
| `/performance/packages` | GET | — | 课程包业绩页面 |
| `/performance/cards` | GET | — | 会籍卡业绩页面 |
| `/performance/checkins` | GET | — | 会员进场统计页面 |
| `/api/performance/overview?period=` | GET | period | JSON |
| `/api/performance/overview/cards` | GET | period | HTML 片段（4张卡片） |
| `/api/performance/sales?period=&status=` | GET | period, status | JSON |
| `/api/performance/sales/table` | GET | period, status | HTML 片段（表格） |
| `/api/performance/sales/stats` | GET | period | HTML 片段（统计卡片） |
| `/api/performance/packages` | GET | — | JSON |
| `/api/performance/packages/table` | GET | — | HTML 片段 |
| `/api/performance/packages/stats` | GET | — | HTML 片段 |
| `/api/performance/cards?period=` | GET | period | JSON |
| `/api/performance/cards/table` | GET | period | HTML 片段 |
| `/api/performance/cards/stats` | GET | period | HTML 片段 |
| `/api/performance/checkins?period=` | GET | period | JSON |
| `/api/performance/checkins/table` | GET | period | HTML 片段 |
| `/api/performance/checkins/stats` | GET | period | HTML 片段 |

---

## 五、performance.py 路由文件实现概要

### 5.1 代码结构

```python
"""业绩统计 API 路由"""
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.models.models import Sale, LessonPackage, MembershipCard, Checkin

router = APIRouter(prefix="/api/performance", tags=["业绩统计"])

# ── 辅助函数 ──

def get_date_range(period: str, today: date = None):
    """根据 period 返回 (start_date, end_date)"""
    today = today or date.today()
    if period == "今日":
        return (today, today)
    elif period == "本周":
        start = today - timedelta(days=today.weekday())
        return (start, today)
    elif period == "本月":
        return (today.replace(day=1), today)
    elif period == "上月":
        first = today.replace(day=1)
        last_month_end = first - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return (last_month_start, last_month_end)
    elif period == "本年":
        return (today.replace(month=1, day=1), today)
    else:  # "全部"
        return (None, None)


def calc_remaining_days(end_date):
    """计算剩余天数，返回状态"""
    if not end_date:
        return (None, "")
    remaining = (end_date - date.today()).days
    if remaining < 0:
        return (remaining, "已过期")
    elif remaining <= 7:
        return (remaining, "即将到期")
    return (remaining, "正常")


# ── HTML 构建辅助函数 ──

def _build_stats_cards_html(cards: list) -> str:
    """生成统计卡片 HTML"""
    html = '<div class="grid grid-cols-2 md:grid-cols-4 gap-4">'
    for card in cards:
        html += f'''
        <div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
            <div class="text-xs text-gray-400 uppercase tracking-wide">{card["label"]}</div>
            <div class="text-3xl font-bold text-gray-800 mt-1">{card["value"]}</div>
            <div class="text-xs text-gray-500 mt-1">{card.get("sub", "")}</div>
        </div>'''
    html += '</div>'
    return html


# ── 业绩总览 ──

@router.get("/overview/cards", response_class=HTMLResponse)
def overview_cards(period: str = Query("本月"), db: Session = Depends(get_db)):
    """业绩总览 4 张统计卡片"""
    start, end = get_date_range(period)
    # 各表独立查询...
    pass


@router.get("/overview")
def overview(period: str = Query("本月"), db: Session = Depends(get_db)):
    """业绩总览 JSON"""
    pass


# ── 售课业绩 ──

@router.get("/sales/stats", response_class=HTMLResponse)
def sale_stats(period: str = Query("本月"), db: Session = Depends(get_db)):
    """售课统计卡片"""
    pass


@router.get("/sales/table", response_class=HTMLResponse)
def sale_table(period: str = Query("本月"), status: str = Query("全部"), db: Session = Depends(get_db)):
    """售课表格（含到期状态）"""
    pass


@router.get("/sales")
def sale_list(period: str = Query("本月"), status: str = Query("全部"), db: Session = Depends(get_db)):
    """售课业绩 JSON"""
    pass


# ── 课程包业绩 ──

@router.get("/packages/stats", response_class=HTMLResponse)
def package_stats(db: Session = Depends(get_db)):
    """课程包统计卡片"""
    pass


@router.get("/packages/table", response_class=HTMLResponse)
def package_table(db: Session = Depends(get_db)):
    """课程包表格（可排序）"""
    pass


@router.get("/packages")
def package_list(db: Session = Depends(get_db)):
    """课程包业绩 JSON"""
    pass


# ── 会籍卡业绩 ──

@router.get("/cards/stats", response_class=HTMLResponse)
def card_stats(period: str = Query("全部"), db: Session = Depends(get_db)):
    """会籍卡统计卡片"""
    pass


@router.get("/cards/table", response_class=HTMLResponse)
def card_table(period: str = Query("全部"), db: Session = Depends(get_db)):
    """会籍卡表格"""
    pass


@router.get("/cards")
def card_list(period: str = Query("全部"), db: Session = Depends(get_db)):
    """会籍卡业绩 JSON"""
    pass


# ── 会员进场统计 ──

@router.get("/checkins/stats", response_class=HTMLResponse)
def checkin_stats(period: str = Query("本月"), db: Session = Depends(get_db)):
    """进场统计卡片"""
    pass


@router.get("/checkins/table", response_class=HTMLResponse)
def checkin_table(period: str = Query("本月"), db: Session = Depends(get_db)):
    """进场表格"""
    pass


@router.get("/checkins")
def checkin_list(period: str = Query("本月"), db: Session = Depends(get_db)):
    """进场统计 JSON"""
    pass
```

### 5.2 关键 SQL 查询示例

```python
# 售课按月统计
month_amount = db.query(func.sum(Sale.actual_amount)).filter(
    Sale.sale_date >= start,
    Sale.sale_date <= end
).scalar() or 0

# 会籍卡按类型分组统计
by_type = db.query(
    MembershipCard.card_type,
    func.count(MembershipCard.id),
    func.sum(MembershipCard.price)
).group_by(MembershipCard.card_type).all()

# 进场按时段统计
from sqlalchemy import case
hour_cases = [
    (func.cast(func.substr(Checkin.checkin_time, 1, 2), Integer) < 9, "清晨"),
    # ...
]
```

---

## 六、页面模板设计要点

### 6.1 业绩总览模板 (`performance.html`)

```html
{% extends "base.html" %}
{% block content %}
<div class="flex items-center justify-between mb-6">
    <h2 class="text-xl font-semibold">📊 业绩总览</h2>
    <select id="periodSelect" class="px-3 py-2 border rounded-lg text-sm"
            hx-get="/api/performance/overview/cards" hx-trigger="change"
            hx-target="#statsCards" hx-params="period">
        <option value="今日">今日</option>
        <option value="本周">本周</option>
        <option value="本月" selected>本月</option>
        <option value="上年">上月</option>
        <option value="本年">本年</option>
        <option value="全部">全部</option>
    </select>
</div>

<div id="statsCards" hx-get="/api/performance/overview/cards" hx-trigger="load">
    <div class="text-center py-8 text-gray-400">加载中...</div>
</div>
{% endblock %}
```

### 6.2 其余 4 个页面
类似结构，差异在于：
- **售课业绩**：增加状态筛选下拉（全部/正常/即将到期/已过期）
- **课程包业绩**：完整表格 + 排序 JS
- **会籍卡业绩**：按类型分组展示 + 明细
- **进场统计**：时段分布用 CSS 进度条展示占比

---

## 七、工作量估算

| 任务 | 文件数 | 预计行数 | 估算时间 |
|------|:-----:|:--------:|:--------:|
| performance.py 路由文件 | 1 | ~300 行 | 30 分钟 |
| 5 个模板文件 | 5 | ~400 行 | 30 分钟 |
| app.py 路由注册 + 导航栏 | 1 | ~30 行 | 5 分钟 |
| 验证测试 | — | — | 10 分钟 |
| **合计** | **7** | **~730 行** | **~75 分钟** |

---

## 八、不做的事情（明确排除）

- ❌ 不引入图表库（趋势图用纯文本 / HTML 进度条展示）
- ❌ 不改动现有数据库结构（全部基于现有字段）
- ❌ 不新增数据库表（统计结果实时计算）
- ❌ 不涉及 Excel 数据导出（已有独立的 `/export` 功能）
- ❌ 不涉及打印/PDF 功能
- ❌ 不修改现有的 sale/lesson_package/membership_card/checkin 路由
