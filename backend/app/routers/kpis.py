"""Yield, throughput, and SPC endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.catalog import METRIC_BY_ID, RECIPE_BY_ID
from app.schemas import SpcOut, SummaryOut, YieldGroup, YieldPoint
from app.services.queries import spc, summary, yield_by_recipe, yield_trend

router = APIRouter(prefix="/kpis")


@router.get("/summary", response_model=SummaryOut)
def get_summary(
    hours: int = Query(default=168, ge=1, le=24 * 90),
    db: Session = Depends(get_db),
) -> SummaryOut:
    return summary(db, hours)


@router.get("/yield-trend", response_model=list[YieldPoint])
def get_yield_trend(
    days: int = Query(default=14, ge=2, le=60),
    db: Session = Depends(get_db),
) -> list[YieldPoint]:
    return yield_trend(db, days)


@router.get("/yield", response_model=list[YieldGroup])
def get_yield(
    group_by: str = Query(default="recipe"),
    hours: int = Query(default=168, ge=1, le=24 * 90),
    db: Session = Depends(get_db),
) -> list[YieldGroup]:
    if group_by != "recipe":
        raise HTTPException(status_code=422, detail="group_by must be recipe")
    return yield_by_recipe(db, hours)


@router.get("/spc", response_model=SpcOut)
def get_spc(
    metric: str = Query(default="piezo_thickness_nm"),
    recipe_id: str | None = Query(default=None),
    limit: int = Query(default=80, ge=10, le=300),
    db: Session = Depends(get_db),
) -> SpcOut:
    if metric not in METRIC_BY_ID:
        raise HTTPException(status_code=422, detail=f"unknown metric {metric}")
    if recipe_id is not None and recipe_id not in RECIPE_BY_ID:
        raise HTTPException(status_code=422, detail=f"unknown recipe_id {recipe_id}")
    try:
        return spc(db, metric, recipe_id, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
