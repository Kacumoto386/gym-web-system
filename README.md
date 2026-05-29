# 鼠小弟健身管理系统

基于 FastAPI + Jinja2/HTMX + SQLAlchemy 的全栈健身管理系统，支持 Web 后台管理 + 微信小程序双端（会员端 + 员工端）。

> 当前版本：**V3.9.1** | 会员小程序 M1.0.1 | 员工小程序 S1.0.1

---

## 系统截图

<img width="2552" alt="仪表盘" src="https://github.com/user-attachments/assets/4afef2f4-8a04-4242-b61f-fd85d3869972" />

---

## 功能概览

### Web 管理后台

| 模块 | 功能 |
|------|------|
| 会员管理 | 会员档案 / 会籍卡 / 剩余课时 / 签到记录 / 体测记录 / 预警提醒 |
| 员工管理 | 员工档案 / 排班 / 佣金提成（梯度规则） |
| 卡种/课程 | 卡种管理 / 课程管理 / 课程包 / 卡种导入（Excel） |
| 销售管理 | 售卡 / 售课 / 产品销售 / 合同管理 |
| 签到核销 | 每日签到 / 核销记录 |
| 财务报表 | 收支管理 / 支出审核 / 预算管理 / 利润表 / 资产价值 |
| 数据看板 | 多维度数据分析图表 / 营业统计 |
| 数据导入 | 模板下载 / Excel 上传解析 / 异步执行 / 进度跟踪 / 导入历史 |
| AI 助手 | 智能问答 / 数据查询（基于 DeepSeek API） |
| 系统配置 | 功能开关（features.yaml）/ 操作日志 / 导入导出 |

### 会员小程序（微信小程序）

面向健身会员，提供自助服务：

| 功能 | 说明 |
|------|------|
| 登录注册 | 手机号验证码登录 / 密码登录 / 微信授权登录 |
| 首页仪表盘 | 今日签到 / 会籍卡状态 / 剩余课时 / 储值余额概览 |
| 会籍卡 | 查看会籍卡详情 / 有效期 / 剩余课时 / 购买记录 |
| 签到 | 每日签到打卡 / 签到日历 / 签到统计 |
| 储值充值 | 查看余额 / 在线充值 / 充值记录 |
| 体测记录 | 查看历史体测数据（身高/体重/体脂率等） |
| 上课记录 | 查看课程历史 / 上课时间 / 教练评价 |
| 预约管理 | 预约课程 / 查看预约 / 取消预约 |
| 在线购买 | 购买卡种 / 购买课程包 / 订单管理 |
| 消息提醒 | 会籍到期提醒 / 课时不足提醒 / 系统通知 |

### 员工小程序（微信小程序）

面向健身房员工，提供移动办公：

| 功能 | 说明 |
|------|------|
| 员工登录 | 账号密码登录 / JWT 认证 |
| 首页 | 今日签到数 / 快捷搜索会员 / 功能导航 |
| 会员查询 | 搜索会员 / 查看详情 / 会籍卡信息 |
| 卡种销售 | 卡种列表 / 售卡开卡 / 自动记录销售业绩 |
| 课程销售 | 课程列表 / 售卖课程包 |
| 预约管理 | 查看预约 / 创建预约 / 教练排期 |
| 签到核销 | 会员签到 / 核销记录 / 签到统计 |
| 上课记录 | 登记上课 / 查看记录 / 消耗课时 |
| 业绩统计 | 售卡业绩 / 售课业绩 / 佣金提成概览 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | Python FastAPI |
| ORM | SQLAlchemy 2.0 |
| 数据库 | SQLite（开发）/ 可扩展至 MySQL |
| Web 前端 | Jinja2 模板 + HTMX + 原生 CSS |
| 小程序前端 | 微信小程序原生框架（WXML/WXSS/JS） |
| 认证 | JWT（双通道：Cookie + Bearer） |
| 密码 | bcrypt |
| 支付 | 微信支付（预开发阶段 mock） |
| AI | DeepSeek API 集成 |

---

## 项目结构

```
gym-web-system/
├── backend/                    # FastAPI 后端
│   ├── app.py                 # 应用入口 + 路由注册
│   ├── database.py            # SQLAlchemy 引擎 / 会话 / 迁移
│   ├── features.yaml          # 功能开关配置
│   ├── feature_registry.py    # 功能注册器
│   ├── models/
│   │   └── models.py          # 全部 ORM 模型
│   ├── routers/               # Web 后台 API 路由
│   ├── services/              # 业务逻辑层
│   ├── miniapp/               # 小程序后端
│   │   ├── common.py          # 统一响应格式
│   │   ├── auth.py            # JWT 验证中间件
│   │   ├── member/            # 会员小程序 9 个模块
│   │   └── staff/             # 员工小程序 7 个模块
│   ├── migrations/            # 数据库迁移脚本
│   └── alembic/               # Alembic 配置
├── frontend/                   # Web 前端
│   ├── templates/             # Jinja2/HTMX 页面模板
│   ├── static/                # CSS / JS / 图片
│   └── ...
├── miniapp-member/             # 会员小程序（微信原生）
│   ├── pages/                 # 10 个页面
│   ├── utils/api.js           # 小程序 API 封装
│   └── app.js / app.json      # 全局配置
├── miniapp-staff/              # 员工小程序（微信原生）
│   ├── pages/                 # 9 个页面
│   ├── utils/api.js           # 小程序 API 封装
│   └── app.js / app.json      # 全局配置
├── data/                       # SQLite 数据库文件 + 上传数据
├── docs/                       # 开发日志 / 维护日志 / 设计方案
├── requirements.txt            # Python 依赖
└── start.bat                   # Windows 一键启动
```

---

## 快速部署

### 环境要求

- Python 3.10+
- pip

### 安装与启动

```bash
# 1. 克隆仓库
git clone https://github.com/Kacumoto386/gym-web-system.git
cd gym-web-system

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化数据库（首次启动会自动创建表和管理员账号）
#    默认管理员: admin / admin123

# 4. 启动服务
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8080

# 5. 访问系统
#    Web 后台: http://localhost:8080
#    会员小程序 API: http://localhost:8080/api/miniapp/member
#    员工小程序 API: http://localhost:8080/api/miniapp/staff
```

### Windows 一键启动

直接双击 `start.bat`，自动检测端口、安装依赖、初始化管理员账号。

### 功能开关

编辑 `backend/features.yaml` 可启用/禁用各功能模块：

```yaml
miniapp_member: true    # 会员小程序
miniapp_staff: true     # 员工小程序
member: true            # 会员管理
staff: true             # 员工管理
finance: true           # 财务管理
analytics: true         # 数据分析
# ... 更多模块
```

---

## 小程序使用说明

### 会员小程序

会员小程序位于 `miniapp-member/` 目录，使用微信开发者工具打开：

1. 在微信开发者工具中导入 `miniapp-member/` 目录
2. 修改 `utils/api.js` 中的 `apiBaseUrl` 为实际服务器地址
3. 开发阶段可设置 `app.js` 中跳过微信登录（使用手机号验证码模式）
4. 后端 `/api/miniapp/member` 端点已全部验证通过

### 员工小程序

员工小程序位于 `miniapp-staff/` 目录：

1. 在微信开发者工具中导入 `miniapp-staff/` 目录
2. 修改 `utils/api.js` 中的 `apiBaseUrl` 为实际服务器地址
3. 员工使用系统账号密码登录（`username` + `password`）
4. 后端 `/api/miniapp/staff` 端点已全部验证通过

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| V3.9.1 | 2026-05-27 | 员工小程序 S1.0.1 + 会员小程序 M1.0.1 双端正式发布 |
| V3.9.0 | 2026-05-27 | 会员小程序预开发 + 员工小程序后端修复 |
| V3.8.9 | 2026-05-26 | 看板图表修复 + HTMX 删除刷新 + 小程序预开发 |
| V3.8.8 | 2026-05-26 | 功能配置清单系统 + 会员录入显示修复 |
| V3.8.7 | 2026-05-25 | 财务报表（支出审核/预算管理/利润表）+ 数据分析看板 |
| V3.8.5-6 | 2026-05-22 | 会籍卡导入卡种字段 + 实收金额/销售员手机号 |
| V3.8.3-4 | 2026-05-19 | 数据导入增强 + 导入结果下载 |
| V3.8.2 | 2026-05-18 | 数据导入模块（模板下载/上传解析/异步执行） |
| V3.8.1 | 2026-05-17 | 会员充值模块增强 |
| V3.8.0 | 2026-05-16 | AI 助手 + 批量余额查询 |

---

## 许可证

MIT
