"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.routers import api
from app.services.ingest import ingest_event
from app.services.seed import seed_catalog, seed_history_if_empty
from app.services.simulator import LiveSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def init_db() -> None:
    # Import models so metadata is populated before create_all.
    import app.models  # noqa: F401

    # Compose DNS for the database hostname can lag the first connection.
    deadline = time.monotonic() + 30
    while True:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            break
        except Exception as exc:
            engine.dispose()
            if time.monotonic() >= deadline:
                raise
            logger.warning("waiting for database: %s", exc)
            time.sleep(1)

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_catalog(db)
        if get_settings().seed_on_startup:
            seed_history_if_empty(db)


async def _simulator_loop(stop: asyncio.Event) -> None:
    settings = get_settings()
    simulator = LiveSimulator()
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.simulator_interval_seconds)
            return
        except TimeoutError:
            pass
        try:
            with SessionLocal() as db:
                ingest_event(db, simulator.next_event(datetime.now(timezone.utc)))
                db.commit()
        except Exception:
            logger.exception("live simulator tick failed")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    stop = asyncio.Event()
    task: asyncio.Task | None = None
    if get_settings().simulator_enabled:
        task = asyncio.create_task(_simulator_loop(stop))
        logger.info("live simulator enabled")
    yield
    stop.set()
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="XBAW Fab Ops",
        summary="MES-lite for a fictional RF BAW filter line.",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api)
    return application


app = create_app()
