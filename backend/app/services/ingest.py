"""Validate and project SECS/GEM-inspired events into relational tables."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.catalog import (
    FINAL_STEP,
    METRIC_UNITS,
    RECIPE_BY_ID,
    STEP_IDS,
    TOOL_BY_ID,
)
from app.models import AlarmRecord, Lot, LotMove, Measurement, ProcessEvent, Tool
from app.schemas import (
    AlarmPayload,
    EventIn,
    IngestResult,
    LotMovePayload,
    ToolStatePayload,
)


class IngestError(ValueError):
    """The event envelope parsed, but the fab rules rejected it."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def parse_payload(event: EventIn) -> ToolStatePayload | AlarmPayload | LotMovePayload:
    try:
        if event.event_type == "tool_state":
            return ToolStatePayload.model_validate(event.payload)
        if event.event_type == "alarm":
            return AlarmPayload.model_validate(event.payload)
        return LotMovePayload.model_validate(event.payload)
    except ValidationError as exc:
        message = exc.errors()[0]["msg"]
        raise IngestError(message) from exc


def _require_tool(db: Session, tool_id: str) -> Tool:
    tool = db.get(Tool, tool_id)
    if tool is None or tool_id not in TOOL_BY_ID:
        raise IngestError(f"unknown tool_id {tool_id}")
    return tool


def _apply_tool_state(db: Session, event: EventIn, payload: ToolStatePayload) -> None:
    tool = _require_tool(db, event.tool_id)
    timestamp = _aware(event.timestamp)
    if payload.recipe_id is not None and payload.recipe_id not in RECIPE_BY_ID:
        raise IngestError(f"unknown recipe_id {payload.recipe_id}")
    if tool.updated_at is None or timestamp >= _aware(tool.updated_at):
        tool.state = payload.to_state
        tool.updated_at = timestamp


def _apply_alarm(db: Session, event: EventIn, payload: AlarmPayload) -> None:
    tool = _require_tool(db, event.tool_id)
    timestamp = _aware(event.timestamp)
    key = f"{event.tool_id}:{payload.alarm_id}"
    open_alarm = db.scalar(
        select(AlarmRecord)
        .where(AlarmRecord.alarm_key == key, AlarmRecord.cleared_at.is_(None))
        .order_by(AlarmRecord.set_at.desc())
    )
    if payload.state == "set":
        if open_alarm is None:
            db.add(
                AlarmRecord(
                    alarm_key=key,
                    tool_id=tool.id,
                    lot_id=event.lot_id,
                    alarm_code=payload.alarm_code,
                    severity=payload.severity,
                    text=payload.text,
                    set_at=timestamp,
                    set_event_id=event.event_id,
                )
            )
        return

    if open_alarm is not None and timestamp >= _aware(open_alarm.set_at):
        open_alarm.cleared_at = timestamp
        open_alarm.clear_event_id = event.event_id


def _apply_lot_move(db: Session, event: EventIn, payload: LotMovePayload) -> None:
    if not event.lot_id:
        raise IngestError("lot_id is required for lot_move events")
    _require_tool(db, event.tool_id)
    if payload.step not in STEP_IDS:
        raise IngestError(f"unknown step {payload.step}")
    if payload.recipe_id not in RECIPE_BY_ID:
        raise IngestError(f"unknown recipe_id {payload.recipe_id}")
    if payload.wafers_out > payload.wafers_in:
        raise IngestError("wafers_out cannot exceed wafers_in")
    if payload.scrap_wafers > payload.wafers_in:
        raise IngestError("scrap_wafers cannot exceed wafers_in")
    if payload.good_die is not None and payload.tested_die is None:
        raise IngestError("tested_die is required when good_die is set")
    if (
        payload.good_die is not None
        and payload.tested_die is not None
        and payload.good_die > payload.tested_die
    ):
        raise IngestError("good_die cannot exceed tested_die")

    timestamp = _aware(event.timestamp)
    lot = db.get(Lot, event.lot_id)
    if lot is None:
        lot = Lot(
            id=event.lot_id,
            recipe_id=payload.recipe_id,
            wafer_count=0,
            status="QUEUED",
            good_die=0,
            tested_die=0,
            scrap_wafers=0,
        )
        db.add(lot)
        db.flush()

    move = LotMove(
        event_id=event.event_id,
        lot_id=lot.id,
        tool_id=event.tool_id,
        recipe_id=payload.recipe_id,
        step=payload.step,
        action=payload.action,
        wafers_in=payload.wafers_in,
        wafers_out=payload.wafers_out,
        scrap_wafers=payload.scrap_wafers,
        good_die=payload.good_die,
        tested_die=payload.tested_die,
        timestamp=timestamp,
    )
    db.add(move)

    for reading in payload.measurements:
        unit = reading.unit or METRIC_UNITS.get(reading.metric)
        if unit is None:
            raise IngestError(f"unit is required for metric {reading.metric}")
        db.add(
            Measurement(
                lot_id=lot.id,
                tool_id=event.tool_id,
                recipe_id=payload.recipe_id,
                step=payload.step,
                metric=reading.metric,
                wafer_slot=reading.wafer_slot,
                value=reading.value,
                unit=unit,
                timestamp=timestamp,
            )
        )

    if lot.updated_at is not None and timestamp < _aware(lot.updated_at):
        return

    lot.updated_at = timestamp
    lot.recipe_id = payload.recipe_id
    if lot.started_at is None or timestamp < _aware(lot.started_at):
        lot.started_at = timestamp
    if lot.wafer_count == 0:
        lot.wafer_count = max(payload.wafers_in, payload.wafers_out)
    lot.scrap_wafers += payload.scrap_wafers
    if payload.tested_die is not None and payload.good_die is not None:
        lot.tested_die = payload.tested_die
        lot.good_die = payload.good_die
    lot.current_step = payload.step
    lot.current_tool_id = event.tool_id

    if payload.action == "hold":
        lot.status = "HOLD"
    elif payload.action == "scrap" and payload.wafers_out == 0:
        lot.status = "SCRAPPED"
        lot.completed_at = timestamp
    elif payload.action == "track_out" and payload.step == FINAL_STEP:
        lot.status = "COMPLETE"
        lot.completed_at = timestamp
    elif lot.status != "HOLD":
        lot.status = "WIP"


def _precheck(db: Session, event: EventIn, payload: ToolStatePayload | AlarmPayload | LotMovePayload) -> None:
    """Reject unknown tools and illegal lot math before writing the event row."""
    _require_tool(db, event.tool_id)
    if isinstance(payload, ToolStatePayload):
        if payload.recipe_id is not None and payload.recipe_id not in RECIPE_BY_ID:
            raise IngestError(f"unknown recipe_id {payload.recipe_id}")
        return
    if isinstance(payload, AlarmPayload):
        return
    if not event.lot_id:
        raise IngestError("lot_id is required for lot_move events")
    if payload.step not in STEP_IDS:
        raise IngestError(f"unknown step {payload.step}")
    if payload.recipe_id not in RECIPE_BY_ID:
        raise IngestError(f"unknown recipe_id {payload.recipe_id}")
    if payload.wafers_out > payload.wafers_in:
        raise IngestError("wafers_out cannot exceed wafers_in")
    if payload.scrap_wafers > payload.wafers_in:
        raise IngestError("scrap_wafers cannot exceed wafers_in")
    if payload.good_die is not None and payload.tested_die is None:
        raise IngestError("tested_die is required when good_die is set")
    if (
        payload.good_die is not None
        and payload.tested_die is not None
        and payload.good_die > payload.tested_die
    ):
        raise IngestError("good_die cannot exceed tested_die")


def ingest_event(db: Session, event: EventIn) -> IngestResult:
    """Persist one event. Caller commits.

    Replays of an existing ``event_id`` are acknowledged and ignored so a
    tool bridge can retry safely.
    """
    if db.get(ProcessEvent, event.event_id) is not None:
        return IngestResult(event_id=event.event_id, status="duplicate")

    payload = parse_payload(event)
    _precheck(db, event, payload)
    timestamp = _aware(event.timestamp)
    db.add(
        ProcessEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            tool_id=event.tool_id,
            lot_id=event.lot_id,
            ceid=event.ceid,
            timestamp=timestamp,
            payload=event.payload,
            received_at=_utcnow(),
        )
    )
    # Flush the event row first so a duplicate inside this transaction fails
    # before projections are applied twice.
    db.flush()

    if isinstance(payload, ToolStatePayload):
        _apply_tool_state(db, event, payload)
    elif isinstance(payload, AlarmPayload):
        _apply_alarm(db, event, payload)
    else:
        _apply_lot_move(db, event, payload)

    db.flush()
    return IngestResult(event_id=event.event_id, status="accepted")
