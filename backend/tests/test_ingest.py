"""Event ingest and the projections it drives."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import AlarmRecord, Lot, ProcessEvent, Tool
from app.schemas import EventIn
from app.services.ingest import IngestError, ingest_event
from app.services.queries import summary


def _ts(minutes: int = 0) -> datetime:
    return datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes)


def _state(event_id: str, tool_id: str, to_state: str, minutes: int) -> EventIn:
    return EventIn(
        event_id=event_id,
        event_type="tool_state",
        timestamp=_ts(minutes),
        tool_id=tool_id,
        ceid=1001,
        payload={"from_state": "IDLE", "to_state": to_state, "recipe_id": "XB-N77", "operator": "OP-14"},
    )


def _move(
    event_id: str,
    action: str,
    step: str,
    minutes: int,
    wafers_in: int,
    wafers_out: int,
    scrap: int = 0,
    good: int | None = None,
    tested: int | None = None,
    lot_id: str = "L260921-001",
    tool_id: str = "PKG-01",
) -> EventIn:
    payload: dict = {
        "action": action,
        "step": step,
        "recipe_id": "XB-C-2G4",
        "wafers_in": wafers_in,
        "wafers_out": wafers_out,
        "scrap_wafers": scrap,
        "measurements": [
            {"metric": "piezo_thickness_nm", "value": 1001.5, "wafer_slot": 3},
        ]
        if step == "PIEZO_DEPOSITION"
        else [],
    }
    if good is not None:
        payload["good_die"] = good
        payload["tested_die"] = tested
    return EventIn(
        event_id=event_id,
        event_type="lot_move",
        timestamp=_ts(minutes),
        tool_id=tool_id,
        lot_id=lot_id,
        ceid=3002,
        payload=payload,
    )


def test_tool_state_keeps_the_latest_timestamp(db):
    ingest_event(db, _state("s1", "DEP-01", "EXECUTING", 10))
    ingest_event(db, _state("s0", "DEP-01", "IDLE", 0))
    db.commit()
    tool = db.get(Tool, "DEP-01")
    assert tool is not None
    assert tool.state == "EXECUTING"


def test_duplicate_event_is_ignored(db):
    first = ingest_event(db, _state("same", "ETH-01", "ALARM", 1))
    second = ingest_event(db, _state("same", "ETH-01", "IDLE", 2))
    db.commit()
    assert first.status == "accepted"
    assert second.status == "duplicate"
    assert db.get(Tool, "ETH-01").state == "ALARM"
    assert db.query(ProcessEvent).count() == 1


def test_alarm_set_and_clear(db):
    ingest_event(
        db,
        EventIn(
            event_id="a-set",
            event_type="alarm",
            timestamp=_ts(1),
            tool_id="ETH-01",
            lot_id="L260921-001",
            ceid=2001,
            payload={
                "alarm_id": "ETH-42",
                "alarm_code": "CHAMBER_PRESSURE",
                "severity": "alarm",
                "state": "set",
                "text": "Chamber pressure above interlock",
            },
        ),
    )
    ingest_event(
        db,
        EventIn(
            event_id="a-clear",
            event_type="alarm",
            timestamp=_ts(5),
            tool_id="ETH-01",
            ceid=2002,
            payload={
                "alarm_id": "ETH-42",
                "alarm_code": "CHAMBER_PRESSURE",
                "severity": "alarm",
                "state": "clear",
                "text": "Pressure recovered",
            },
        ),
    )
    db.commit()
    row = db.query(AlarmRecord).one()
    assert row.cleared_at is not None
    assert row.alarm_code == "CHAMBER_PRESSURE"


def test_clear_without_set_does_not_open_an_alarm(db):
    ingest_event(
        db,
        EventIn(
            event_id="a-orphan",
            event_type="alarm",
            timestamp=_ts(1),
            tool_id="PRB-01",
            ceid=2002,
            payload={
                "alarm_id": "missing",
                "alarm_code": "PROBE_CONTACT",
                "severity": "warning",
                "state": "clear",
                "text": "clear",
            },
        ),
    )
    db.commit()
    assert db.query(AlarmRecord).count() == 0


def test_lot_flow_projects_yield_and_throughput(db):
    ingest_event(db, _move("in", "track_in", "SUBSTRATE_START", 0, 25, 25, tool_id="STK-01"))
    ingest_event(
        db,
        _move("etch", "track_out", "ETCH", 30, 25, 24, scrap=1, tool_id="ETH-01"),
    )
    ingest_event(
        db,
        _move(
            "final",
            "track_out",
            "FINAL_TEST",
            90,
            24,
            24,
            good=54000,
            tested=60000,
            tool_id="PKG-01",
        ),
    )
    db.commit()
    lot = db.get(Lot, "L260921-001")
    assert lot is not None
    assert lot.status == "COMPLETE"
    assert lot.wafer_count == 25
    assert lot.scrap_wafers == 1
    assert lot.good_die == 54000
    assert lot.tested_die == 60000

    report = summary(db, window_hours=4, as_of=_ts(120))
    assert report.die_yield == pytest.approx(0.9)
    assert report.line_yield == pytest.approx(54000 / (25 * 2500))
    assert report.wafer_scrap_rate == pytest.approx(0.04)
    assert report.throughput_wph == pytest.approx(24 / 4)
    assert report.wafers_out == 24


def test_scrap_action_closes_the_lot(db):
    ingest_event(db, _move("in", "track_in", "SUBSTRATE_START", 0, 25, 25, tool_id="STK-01"))
    ingest_event(db, _move("scrap", "scrap", "DICE", 20, 25, 0, scrap=25, tool_id="DIC-01"))
    db.commit()
    lot = db.get(Lot, "L260921-001")
    assert lot.status == "SCRAPPED"
    assert lot.scrap_wafers == 25


def test_unknown_tool_and_illegal_die_counts(db):
    with pytest.raises(IngestError, match="unknown tool"):
        ingest_event(db, _state("bad-tool", "NOPE-01", "IDLE", 0))
    with pytest.raises(IngestError, match="good_die"):
        ingest_event(
            db,
            _move("bad-die", "track_out", "FINAL_TEST", 1, 25, 25, good=10, tested=4),
        )
    with pytest.raises(IngestError, match="lot_id"):
        ingest_event(
            db,
            EventIn(
                event_id="no-lot",
                event_type="lot_move",
                timestamp=_ts(2),
                tool_id="STK-01",
                payload={
                    "action": "track_in",
                    "step": "SUBSTRATE_START",
                    "recipe_id": "XB-N77",
                    "wafers_in": 25,
                    "wafers_out": 25,
                },
            ),
        )


def test_api_ingest_and_idempotent_replay(client):
    body = {
        "event_id": "api-1",
        "event_type": "tool_state",
        "timestamp": "2026-09-21T12:00:00Z",
        "tool_id": "LTH-02",
        "ceid": 1001,
        "payload": {"from_state": "IDLE", "to_state": "SETUP", "operator": "OP-31"},
    }
    first = client.post("/api/events", json=body)
    second = client.post("/api/events", json=body)
    assert first.status_code == 200
    assert first.json()["status"] == "accepted"
    assert second.json()["status"] == "duplicate"
    rejected = client.post(
        "/api/events",
        json={
            **body,
            "event_id": "api-2",
            "tool_id": "NOT-A-TOOL",
        },
    )
    assert rejected.status_code == 422
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_batch_is_atomic(client):
    response = client.post(
        "/api/events/batch",
        json={
            "events": [
                {
                    "event_id": "b1",
                    "event_type": "tool_state",
                    "timestamp": "2026-09-21T12:00:00Z",
                    "tool_id": "SPT-01",
                    "payload": {"to_state": "EXECUTING"},
                },
                {
                    "event_id": "b2",
                    "event_type": "lot_move",
                    "timestamp": "2026-09-21T12:05:00Z",
                    "tool_id": "SPT-01",
                    "lot_id": "L-BATCH",
                    "payload": {
                        "action": "track_out",
                        "step": "BOTTOM_ELECTRODE",
                        "recipe_id": "XB-N77",
                        "wafers_in": 10,
                        "wafers_out": 12,
                    },
                },
            ]
        },
    )
    assert response.status_code == 422
    listing = client.get("/api/events")
    assert listing.json() == []
