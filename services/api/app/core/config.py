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
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ]
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_companion_model: str = "qwen3.8-flash"
    dashscope_companion_timeout_seconds: float = 8.0
    companion_history_limit: int = 16
    elder_default_location: str = "澳门"
    elder_default_latitude: float = 22.1987
    elder_default_longitude: float = 113.5439

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
