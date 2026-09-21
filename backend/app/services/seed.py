"""Catalog upsert and first-boot history load."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.domain.catalog import RECIPES, TOOLS, recipe_specs
from app.models import ProcessEvent, Recipe, SpecLimit, Tool
from app.services.generator import build_history
from app.services.ingest import ingest_event

logger = logging.getLogger(__name__)


def seed_catalog(db: Session) -> None:
    """Insert tools, recipes, and spec limits. Tool state is left alone on rerun."""
    for spec in TOOLS:
        row = db.get(Tool, spec["id"])
        if row is None:
            db.add(
                Tool(
                    id=spec["id"],
                    name=spec["name"],
                    area=spec["area"],
                    model=spec["model"],
                    state="IDLE",
                )
            )
        else:
            row.name = spec["name"]
            row.area = spec["area"]
            row.model = spec["model"]

    for spec in RECIPES:
        row = db.get(Recipe, str(spec["id"]))
        if row is None:
            db.add(
                Recipe(
                    id=str(spec["id"]),
                    name=str(spec["name"]),
                    family=str(spec["family"]),
                    target_freq_mhz=float(spec["target_freq_mhz"]),
                    die_per_wafer=int(spec["die_per_wafer"]),
                )
            )
        else:
            row.name = str(spec["name"])
            row.family = str(spec["family"])
            row.target_freq_mhz = float(spec["target_freq_mhz"])
            row.die_per_wafer = int(spec["die_per_wafer"])

    db.flush()
    db.execute(delete(SpecLimit))
    for recipe in RECIPES:
        for limit in recipe_specs(str(recipe["id"])):
            db.add(
                SpecLimit(
                    recipe_id=str(recipe["id"]),
                    metric=str(limit["metric"]),
                    unit=str(limit["unit"]),
                    lsl=float(limit["lsl"]),
                    usl=float(limit["usl"]),
                    target=float(limit["target"]),
                )
            )
    db.commit()


def seed_history_if_empty(db: Session, as_of: datetime | None = None) -> int:
    """Project the synthetic event history when the event log is empty."""
    existing = db.scalar(select(func.count()).select_from(ProcessEvent))
    if existing:
        logger.info("event log already has %s rows; skipping history seed", existing)
        return 0
    moment = as_of or datetime.now(timezone.utc)
    events = build_history(moment)
    for event in events:
        ingest_event(db, event)
    db.commit()
    logger.info("seeded %s synthetic process events", len(events))
    return len(events)
