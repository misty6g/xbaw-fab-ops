"""HTTP routers for the fab API."""

from fastapi import APIRouter

from app.routers import alarms, events, kpis, lots, meta, tools

api = APIRouter(prefix="/api")
api.include_router(meta.router, tags=["meta"])
api.include_router(events.router, tags=["events"])
api.include_router(lots.router, tags=["lots"])
api.include_router(tools.router, tags=["tools"])
api.include_router(alarms.router, tags=["alarms"])
api.include_router(kpis.router, tags=["kpis"])
