from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "心迹银龄核心业务 API"
    environment: str = "development"
    api_prefix: str = "/api"
    database_url: str = "sqlite+pysqlite:///./hearttrace.db"
    jwt_secret: str = "development-only-change-me-32-bytes-minimum"
    jwt_algorithm: str = "HS256"
    jwt_exp_minutes: int = 60
    seed_demo_data: bool = True
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
