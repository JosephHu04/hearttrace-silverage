from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, create_schema, engine
from app.routers import admin_accounts, admin_risks, auth, conversations, emergencies, family, notifications
from app.schemas import HealthOut


settings = get_settings()


def validate_runtime_settings() -> None:
    if settings.environment.lower() != "production":
        return
    if settings.enable_demo_login or settings.seed_demo_data:
        raise RuntimeError("生产环境必须关闭演示登录与演示数据")
    if settings.jwt_secret == "development-only-change-me-32-bytes-minimum" or len(settings.jwt_secret) < 32:
        raise RuntimeError("生产环境必须配置至少 32 字符的独立 JWT_SECRET")


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_settings()
    if settings.environment.lower() == "production":
        from pathlib import Path
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        api_dir = Path(__file__).resolve().parents[1]
        config = Config(str(api_dir / "alembic.ini"))
        config.set_main_option("script_location", str(api_dir / "migrations"))
        with engine.connect() as connection:
            current = set(MigrationContext.configure(connection).get_current_heads())
        if current != set(ScriptDirectory.from_config(config).get_heads()):
            raise RuntimeError("生产数据库未迁移到当前版本，请先执行 alembic upgrade head")
    else:
        create_schema()
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed_demo_data(db)
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="老人端、家属端和管理端共享的业务事实来源。",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.include_router(auth.router, prefix=settings.api_prefix)
    application.include_router(admin_accounts.router, prefix=settings.api_prefix)
    application.include_router(admin_risks.router, prefix=settings.api_prefix)
    application.include_router(family.router, prefix=settings.api_prefix)
    application.include_router(emergencies.router, prefix=settings.api_prefix)
    application.include_router(conversations.router, prefix=settings.api_prefix)
    application.include_router(notifications.router, prefix=settings.api_prefix)

    @application.get(f"{settings.api_prefix}/health", response_model=HealthOut, tags=["system"])
    def health() -> HealthOut:
        return HealthOut(status="ok", service="core-api")

    @application.get(f"{settings.api_prefix}/ready", response_model=HealthOut, tags=["system"])
    def ready() -> HealthOut:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="数据库暂时不可用") from exc
        return HealthOut(status="ok", service="core-api")

    return application


app = create_app()
