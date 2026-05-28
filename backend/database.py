"""
数据库配置
"""
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.core.config import settings

# 默认使用 SQLite，数据文件在项目 data 目录
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = settings.DATABASE_URL or f"sqlite:///{DATA_DIR / 'gym.db'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,  # 生产环境关闭 SQL 日志
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI 依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """创建所有表（Alembic 管理后续迁移）"""
    Base.metadata.create_all(bind=engine)

    # V3.8.9 会员密码哈希字段
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE member ADD COLUMN password_hash VARCHAR(200) DEFAULT ''"))
            conn.commit()
    except Exception:
        pass  # 字段已存在

    # V3.9.1 会员卡剩余课时
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE membership_card ADD COLUMN remaining_classes INTEGER DEFAULT 0"))
            conn.commit()
    except Exception:
        pass  # 字段已存在
