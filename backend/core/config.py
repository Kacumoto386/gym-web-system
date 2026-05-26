from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库
    DATABASE_URL: str = "sqlite:///./gym.db"
    # JWT
    SECRET_KEY: str = "gym-management-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    # 运行模式
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    # LLM
    OPENAI_API_BASE: str = "http://localhost:11434/v1"
    OPENAI_API_KEY: str = "sk-placeholder"
    OPENAI_MODEL: str = "gpt-4o-mini"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
