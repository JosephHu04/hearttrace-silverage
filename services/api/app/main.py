from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, create_schema
from app.routers import admin_risks, auth, family
from app.schemas import HealthOut


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
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
    application.include_router(admin_risks.router, prefix=settings.api_prefix)
    application.include_router(family.router, prefix=settings.api_prefix)

    @application.get(f"{settings.api_prefix}/health", response_model=HealthOut, tags=["system"])
    def health() -> HealthOut:
        return HealthOut(status="ok", service="core-api")

    return application


app = create_app()
