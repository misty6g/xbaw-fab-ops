"""Event ingest and recent-event feed."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import EventBatch, EventOut, IngestBatchResult, IngestResult, EventIn
from app.services.ingest import IngestError, ingest_event
from app.services.queries import list_events

router = APIRouter()


@router.post("/events", response_model=IngestResult)
def post_event(body: EventIn, db: Session = Depends(get_db)) -> IngestResult:
    try:
        result = ingest_event(db, body)
        db.commit()
    except IngestError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@router.post("/events/batch", response_model=IngestBatchResult)
def post_batch(body: EventBatch, db: Session = Depends(get_db)) -> IngestBatchResult:
    results: list[IngestResult] = []
    try:
        for event in body.events:
            results.append(ingest_event(db, event))
        db.commit()
    except IngestError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    accepted = sum(1 for result in results if result.status == "accepted")
    return IngestBatchResult(
        accepted=accepted,
        duplicates=len(results) - accepted,
        results=results,
    )


@router.get("/events", response_model=list[EventOut])
def get_events(
    limit: int = Query(default=12, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[EventOut]:
    return list_events(db, limit)
