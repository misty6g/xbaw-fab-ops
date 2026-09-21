"""SQLAlchemy engine and session factory."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine():
    url = get_settings().database_url
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        # StaticPool lets tests share one in-memory database across sessions.
        if url in {"sqlite://", "sqlite:///:memory:"} or ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


engine = _engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

if get_settings().database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
