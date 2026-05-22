# 🧀 鼠小弟健身管理系统 V3.6.5（网页版）

从原有桌面版（v2.16.x）迁移而来的 Web 版本，持续迭代至 V3.6.5。

## 架构

```
gym-web-system/
├── backend/           # FastAPI 后端
│   ├── app.py        # 应用入口
│   ├── database.py   # SQLAlchemy 配置
│   ├── models/       # 数据模型
│   ├── routers/      # API 路由
│   ├── services/     # 业务逻辑（适配复用 core/）
│   └── migrations/   # 数据库迁移
├── frontend/         # 前端
│   ├── templates/    # Jinja2/HTMX 模板
│   └── static/       # CSS/JS
└── requirements.txt  # 依赖
```

## 开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动后端（两种方式任选）
cd backend && uvicorn app:app --reload
# 或
uvicorn backend.app:app --reload

# 浏览器访问
http://localhost:8000

# 运行测试
python test_stability.py
```
