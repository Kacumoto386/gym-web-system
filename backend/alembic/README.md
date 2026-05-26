# Alembic 数据库迁移

## 初始化（首次使用）

```bash
# 在工作目录（包含 alembic.ini 的目录）执行
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

## 日常操作

修改 `backend/models/models.py` 后：

```bash
# 生成迁移脚本
alembic revision --autogenerate -m "描述你的改动"

# 预览将要执行的 SQL
alembic upgrade head --sql

# 执行迁移
alembic upgrade head

# 回滚一步
alembic downgrade -1
```

## 查看状态

```bash
alembic current       # 当前版本
alembic history       # 迁移历史
```

## 注意事项

- SQLite 使用 `render_as_batch=True` 支持 ALTER TABLE
- 迁移脚本在 `versions/` 目录下
- 不要手动编辑已发布的迁移脚本
