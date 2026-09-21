"""Read-side rollups for the dashboard and REST API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.catalog import (
    AREA_LABELS,
    FINAL_STEP,
    METRIC_BY_ID,
    RECIPE_BY_ID,
    STEP_LABELS,
    TOOL_BY_ID,
)
from app.models import AlarmRecord, Lot, LotMove, Measurement, ProcessEvent, Recipe, SpecLimit, Tool
from app.schemas import (
    AlarmOut,
    EventOut,
    LotOut,
    SpcOut,
    SpcPoint,
    SummaryOut,
    ToolOut,
    YieldGroup,
    YieldPoint,
)
from app.services.metrics import (
    combine_lots,
    point_flags,
    spc_summary,
    step_yield,
    throughput_wph,
    utilization,
)
def _aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _round(value: float | None, places: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, places)


def _lot_rows(lots: list[Lot], die_per_wafer: dict[str, int]) -> list[tuple[int, int, int, int, int]]:
    return [
        (
            lot.wafer_count,
            lot.scrap_wafers,
            lot.good_die,
            lot.tested_die,
            die_per_wafer[lot.recipe_id],
        )
        for lot in lots
    ]


def _die_map(db: Session) -> dict[str, int]:
    return {recipe.id: recipe.die_per_wafer for recipe in db.scalars(select(Recipe))}


def lot_to_out(lot: Lot, die_per_wafer: int, recipe_name: str) -> LotOut:
    totals = combine_lots(
        [(lot.wafer_count, lot.scrap_wafers, lot.good_die, lot.tested_die, die_per_wafer)]
    )
    return LotOut(
        id=lot.id,
        recipe_id=lot.recipe_id,
        recipe_name=recipe_name,
        status=lot.status,
        current_step=lot.current_step,
        step_label=STEP_LABELS.get(lot.current_step) if lot.current_step else None,
        current_tool_id=lot.current_tool_id,
        wafer_count=lot.wafer_count,
        scrap_wafers=lot.scrap_wafers,
        good_die=lot.good_die,
        tested_die=lot.tested_die,
        die_yield=_round(totals.die_yield),
        line_yield=_round(totals.line_yield),
        started_at=lot.started_at,
        completed_at=lot.completed_at,
    )


def list_lots(db: Session, status: str | None, limit: int) -> list[LotOut]:
    stmt = select(Lot)
    if status:
        stmt = stmt.where(Lot.status == status)
    lots = list(db.scalars(stmt))
    rank = {"WIP": 0, "HOLD": 1, "QUEUED": 2, "COMPLETE": 3, "SCRAPPED": 4}

    def sort_key(lot: Lot) -> tuple[int, float]:
        started = _aware(lot.started_at).timestamp() if lot.started_at else 0.0
        return (rank.get(lot.status, 9), -started)

    lots.sort(key=sort_key)
    die_map = _die_map(db)
    return [
        lot_to_out(lot, die_map[lot.recipe_id], str(RECIPE_BY_ID[lot.recipe_id]["name"]))
        for lot in lots[:limit]
    ]


def list_alarms(db: Session, open_only: bool, limit: int) -> list[AlarmOut]:
    stmt = select(AlarmRecord).order_by(AlarmRecord.set_at.desc()).limit(limit if not open_only else 200)
    rows = list(db.scalars(stmt))
    if open_only:
        rows = [row for row in rows if row.cleared_at is None]
    rows = rows[:limit]
    output: list[AlarmOut] = []
    for row in rows:
        tool = TOOL_BY_ID.get(row.tool_id, {})
        output.append(
            AlarmOut(
                id=row.id,
                tool_id=row.tool_id,
                tool_name=str(tool.get("name", row.tool_id)),
                lot_id=row.lot_id,
                alarm_code=row.alarm_code,
                severity=row.severity,
                text=row.text,
                set_at=row.set_at,
                cleared_at=row.cleared_at,
                open=row.cleared_at is None,
            )
        )
    return output


def event_summary(event: ProcessEvent) -> str:
    payload = event.payload or {}
    if event.event_type == "tool_state":
        return f"{payload.get('from_state') or '—'} → {payload.get('to_state')}"
    if event.event_type == "alarm":
        return f"{payload.get('state')} {payload.get('alarm_code')}: {payload.get('text')}"
    action = payload.get("action")
    step = payload.get("step")
    return f"{action} {step} wafers {payload.get('wafers_in')}→{payload.get('wafers_out')}"


def list_events(db: Session, limit: int) -> list[EventOut]:
    rows = list(
        db.scalars(select(ProcessEvent).order_by(ProcessEvent.timestamp.desc()).limit(limit))
    )
    return [
        EventOut(
            event_id=row.event_id,
            event_type=row.event_type,
            timestamp=row.timestamp,
            tool_id=row.tool_id,
            lot_id=row.lot_id,
            ceid=row.ceid,
            payload=row.payload,
            summary=event_summary(row),
        )
        for row in rows
    ]


def _closed_lots(db: Session, start: datetime, end: datetime) -> list[Lot]:
    """Completed and scrapped lots whose close timestamp falls in the window."""
    lots = list(db.scalars(select(Lot).where(Lot.status.in_(("COMPLETE", "SCRAPPED")))))
    selected: list[Lot] = []
    for lot in lots:
        closed = lot.completed_at
        if closed is None:
            continue
        closed = _aware(closed)
        if start <= closed < end:
            selected.append(lot)
    return selected


def summary(db: Session, window_hours: int, as_of: datetime | None = None) -> SummaryOut:
    as_of = _aware(as_of or datetime.now(timezone.utc))
    start = as_of - timedelta(hours=window_hours)
    prior_start = start - timedelta(hours=window_hours)
    die_map = _die_map(db)

    current = _closed_lots(db, start, as_of)
    prior = _closed_lots(db, prior_start, start)
    totals = combine_lots(_lot_rows(current, die_map)) if current else None
    prior_totals = combine_lots(_lot_rows(prior, die_map)) if prior else None

    moves = list(
        db.scalars(
            select(LotMove).where(
                LotMove.step == FINAL_STEP,
                LotMove.action == "track_out",
                LotMove.timestamp >= start,
                LotMove.timestamp < as_of,
            )
        )
    )
    wafers_out = sum(move.wafers_out for move in moves)

    status_counts = dict(
        db.execute(select(Lot.status, func.count()).group_by(Lot.status)).all()
    )
    open_alarms = db.scalar(
        select(func.count()).select_from(AlarmRecord).where(AlarmRecord.cleared_at.is_(None))
    )

    return SummaryOut(
        window_hours=window_hours,
        as_of=as_of,
        lots_completed=sum(1 for lot in current if lot.status == "COMPLETE"),
        lots_wip=status_counts.get("WIP", 0),
        lots_hold=status_counts.get("HOLD", 0),
        lots_scrapped=sum(1 for lot in current if lot.status == "SCRAPPED"),
        die_yield=_round(totals.die_yield) if totals else None,
        die_yield_prior=_round(prior_totals.die_yield) if prior_totals else None,
        line_yield=_round(totals.line_yield) if totals else None,
        wafer_scrap_rate=_round(totals.scrap_rate) if totals else None,
        throughput_wph=_round(throughput_wph(wafers_out, window_hours)),
        open_alarms=int(open_alarms or 0),
        wafers_started=totals.wafers_started if totals else 0,
        wafers_scrapped=totals.scrap_wafers if totals else 0,
        wafers_out=wafers_out,
        good_die=totals.good_die if totals else 0,
        tested_die=totals.tested_die if totals else 0,
    )


def yield_trend(db: Session, days: int, as_of: datetime | None = None) -> list[YieldPoint]:
    as_of = _aware(as_of or datetime.now(timezone.utc))
    start_day = (as_of - timedelta(days=days - 1)).date()
    die_map = _die_map(db)
    buckets: dict[str, list[Lot]] = {}
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        buckets[day.isoformat()] = []

    for lot in db.scalars(select(Lot).where(Lot.status.in_(("COMPLETE", "SCRAPPED")))):
        if lot.completed_at is None:
            continue
        day = _aware(lot.completed_at).date().isoformat()
        if day in buckets:
            buckets[day].append(lot)

    points: list[YieldPoint] = []
    for day, lots in buckets.items():
        totals = combine_lots(_lot_rows(lots, die_map)) if lots else None
        points.append(
            YieldPoint(
                date=day,
                die_yield=_round(totals.die_yield) if totals else None,
                line_yield=_round(totals.line_yield) if totals else None,
                scrap_rate=_round(totals.scrap_rate) if totals else None,
                lots=len(lots),
                wafers_started=totals.wafers_started if totals else 0,
            )
        )
    return points


def yield_by_recipe(db: Session, window_hours: int, as_of: datetime | None = None) -> list[YieldGroup]:
    as_of = _aware(as_of or datetime.now(timezone.utc))
    start = as_of - timedelta(hours=window_hours)
    die_map = _die_map(db)
    grouped: dict[str, list[Lot]] = {recipe_id: [] for recipe_id in RECIPE_BY_ID}
    for lot in _closed_lots(db, start, as_of):
        grouped.setdefault(lot.recipe_id, []).append(lot)

    groups: list[YieldGroup] = []
    for recipe_id, lots in grouped.items():
        recipe = RECIPE_BY_ID.get(recipe_id, {"name": recipe_id})
        totals = combine_lots(_lot_rows(lots, die_map)) if lots else None
        groups.append(
            YieldGroup(
                key=recipe_id,
                label=str(recipe["name"]),
                die_yield=_round(totals.die_yield) if totals else None,
                line_yield=_round(totals.line_yield) if totals else None,
                scrap_rate=_round(totals.scrap_rate) if totals else None,
                step_yield=None,
                lots=len(lots),
                wafers_started=totals.wafers_started if totals else 0,
                wafers_out=(totals.wafers_started - totals.scrap_wafers) if totals else 0,
            )
        )
    return groups


def tool_board(db: Session, window_hours: int, as_of: datetime | None = None) -> list[ToolOut]:
    as_of = _aware(as_of or datetime.now(timezone.utc))
    start = as_of - timedelta(hours=window_hours)
    open_counts = dict(
        db.execute(
            select(AlarmRecord.tool_id, func.count())
            .where(AlarmRecord.cleared_at.is_(None))
            .group_by(AlarmRecord.tool_id)
        ).all()
    )
    moves = list(
        db.scalars(
            select(LotMove).where(
                LotMove.action.in_(("track_out", "scrap")),
                LotMove.timestamp >= start,
                LotMove.timestamp < as_of,
            )
        )
    )
    wafers: dict[str, int] = {}
    entered: dict[str, int] = {}
    for move in moves:
        wafers[move.tool_id] = wafers.get(move.tool_id, 0) + move.wafers_out
        entered[move.tool_id] = entered.get(move.tool_id, 0) + move.wafers_in

    state_rows = list(
        db.scalars(select(ProcessEvent).where(ProcessEvent.event_type == "tool_state"))
    )
    states_by_tool: dict[str, list[tuple[datetime, str]]] = {}
    for row in state_rows:
        to_state = (row.payload or {}).get("to_state")
        if not to_state:
            continue
        states_by_tool.setdefault(row.tool_id, []).append((_aware(row.timestamp), str(to_state)))

    tools = list(db.scalars(select(Tool)))
    order = list(TOOL_BY_ID)
    tools.sort(key=lambda tool: order.index(tool.id) if tool.id in order else 99)
    board: list[ToolOut] = []
    for tool in tools:
        util = utilization(states_by_tool.get(tool.id, []), start, as_of)
        board.append(
            ToolOut(
                id=tool.id,
                name=tool.name,
                area=tool.area,
                area_label=AREA_LABELS.get(tool.area, tool.area),
                model=tool.model,
                state=tool.state,
                updated_at=tool.updated_at,
                open_alarms=int(open_counts.get(tool.id, 0)),
                utilization=_round(util),
                wafers_out=wafers.get(tool.id, 0),
                step_yield=_round(step_yield(wafers.get(tool.id, 0), entered.get(tool.id, 0))),
            )
        )
    return board


def spc(
    db: Session,
    metric: str,
    recipe_id: str | None,
    limit: int,
    as_of: datetime | None = None,
) -> SpcOut:
    as_of = _aware(as_of or datetime.now(timezone.utc))
    meta = METRIC_BY_ID.get(metric)
    if meta is None:
        raise ValueError(f"unknown metric {metric}")

    stmt = select(Measurement).where(Measurement.metric == metric, Measurement.timestamp <= as_of)
    if recipe_id:
        stmt = stmt.where(Measurement.recipe_id == recipe_id)
    rows = list(db.scalars(stmt.order_by(Measurement.timestamp.asc())))

    spec_stmt = select(SpecLimit).where(SpecLimit.metric == metric)
    if recipe_id:
        spec_stmt = spec_stmt.where(SpecLimit.recipe_id == recipe_id)
    specs = list(db.scalars(spec_stmt))
    lsl = usl = target = None
    if len(specs) == 1:
        lsl, usl, target = specs[0].lsl, specs[0].usl, specs[0].target
    elif recipe_id is None and specs:
        # Across recipes, thickness shares a window; frequency does not.
        lsls = {spec.lsl for spec in specs}
        usls = {spec.usl for spec in specs}
        targets = {spec.target for spec in specs}
        if len(lsls) == 1 and len(usls) == 1:
            lsl, usl = next(iter(lsls)), next(iter(usls))
            target = next(iter(targets)) if len(targets) == 1 else None

    summary_stats = spc_summary([row.value for row in rows], lsl, usl)
    tail = rows[-limit:]
    points = []
    for row in tail:
        ooc, oos = point_flags(row.value, lsl, usl, summary_stats.lcl, summary_stats.ucl)
        points.append(
            SpcPoint(
                timestamp=row.timestamp,
                value=round(row.value, 4),
                lot_id=row.lot_id,
                tool_id=row.tool_id,
                wafer_slot=row.wafer_slot,
                ooc=ooc,
                oos=oos,
            )
        )

    return SpcOut(
        metric=metric,
        label=str(meta["label"]),
        unit=str(meta["unit"]),
        recipe_id=recipe_id,
        n=summary_stats.n,
        mean=_round(summary_stats.mean, 4),
        sigma=_round(summary_stats.sigma, 4),
        ucl=_round(summary_stats.ucl, 4),
        lcl=_round(summary_stats.lcl, 4),
        lsl=lsl,
        usl=usl,
        target=target,
        cp=_round(summary_stats.cp, 4),
        cpk=_round(summary_stats.cpk, 4),
        ooc=summary_stats.ooc,
        oos=summary_stats.oos,
        points=points,
    )
