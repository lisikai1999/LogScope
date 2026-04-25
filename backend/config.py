import os
from datetime import timedelta
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "LogScope"
    APP_VERSION: str = "1.0.0"
    
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "logscope-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./logscope.db")
    
    DEFAULT_ADMIN_USERNAME: str = os.environ.get("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin123")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
