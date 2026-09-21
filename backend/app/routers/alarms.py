"""Alarm feed."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import AlarmOut
from app.services.queries import list_alarms

router = APIRouter()


@router.get("/alarms", response_model=list[AlarmOut])
def get_alarms(
    open_only: bool = Query(default=False),
    limit: int = Query(default=40, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[AlarmOut]:
    return list_alarms(db, open_only, limit)
