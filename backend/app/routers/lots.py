"""Lot status board."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.catalog import LOT_STATUSES
from app.schemas import LotOut
from app.services.queries import list_lots

router = APIRouter()


@router.get("/lots", response_model=list[LotOut])
def get_lots(
    status: str | None = Query(default=None),
    limit: int = Query(default=80, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[LotOut]:
    if status is not None and status not in LOT_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {', '.join(LOT_STATUSES)}")
    return list_lots(db, status, limit)
