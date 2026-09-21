"""Seeded history produces a coherent line."""

from datetime import datetime, timedelta, timezone

from app.models import AlarmRecord, Lot
from app.services.generator import build_history
from app.services.ingest import ingest_event
from app.services.queries import spc, summary, tool_board, yield_trend


def test_history_ingests_and_reports(db):
    as_of = datetime(2026, 9, 21, 18, 0, tzinfo=timezone.utc)
    events = build_history(as_of, days=4, seed=7, wafers=25)
    assert len(events) > 100
    ids = [event.event_id for event in events]
    assert len(ids) == len(set(ids))
    for event in events:
        ingest_event(db, event)
    db.commit()

    report = summary(db, window_hours=24 * 4, as_of=as_of + timedelta(minutes=1))
    assert report.die_yield is not None
    assert 0.75 <= report.die_yield <= 0.99
    assert report.line_yield is not None
    assert report.line_yield <= report.die_yield
    assert report.throughput_wph is not None
    assert report.wafers_out > 0
    assert report.lots_wip >= 1

    open_alarms = db.query(AlarmRecord).filter(AlarmRecord.cleared_at.is_(None)).count()
    assert open_alarms >= 2
    assert db.query(Lot).filter(Lot.status == "WIP").count() >= 1

    trend = yield_trend(db, days=4, as_of=as_of)
    assert len(trend) == 4
    assert any(point.lots > 0 for point in trend)

    thickness = spc(db, "piezo_thickness_nm", "XB-N77", limit=50, as_of=as_of)
    assert thickness.n > 5
    assert thickness.sigma is not None
    assert thickness.lsl == 970
    assert thickness.usl == 1030

    board = tool_board(db, window_hours=24, as_of=as_of + timedelta(minutes=1))
    by_id = {tool.id: tool for tool in board}
    assert by_id["ETH-01"].state == "ALARM"
    assert by_id["ETH-01"].open_alarms >= 1
    assert by_id["LTH-01"].state == "EXECUTING"
