"""Service metadata and health."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.catalog import AREAS, METRICS, RECIPES, STEPS, TOOLS

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "xbaw-fab-ops"}


@router.get("/meta")
def meta() -> dict:
    return {
        "name": "XBAW Fab Ops",
        "plant": "Harborline RF",
        "line": "Line 2",
        "product": "RF bulk-acoustic-wave filters (fictional demo line)",
        "disclaimer": (
            "Synthetic portfolio demo. Not affiliated with SpaceX, Starlink, "
            "or Akoustis. Tool models and spec windows are invented."
        ),
        "steps": STEPS,
        "areas": AREAS,
        "tools": TOOLS,
        "recipes": RECIPES,
        "metrics": METRICS,
    }
