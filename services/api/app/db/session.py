from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base


settings = get_settings()
engine_options: dict[str, object] = {"pool_pre_ping": True}

if settings.database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
    if ":memory:" in settings.database_url:
        engine_options["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **engine_options)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        # SQLite declares foreign keys but does not enforce them by default.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_schema() -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
