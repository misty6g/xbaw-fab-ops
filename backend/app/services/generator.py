"""Deterministic synthetic lot history for the Harborline demo line."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from app.domain.catalog import (
    CEID_ALARM_CLEAR,
    CEID_ALARM_SET,
    CEID_HOLD,
    CEID_SCRAP,
    CEID_TOOL_STATE,
    CEID_TRACK_IN,
    CEID_TRACK_OUT,
    RECIPE_BY_ID,
    STEP_IDS,
    recipe_specs,
    step_tools,
)
from app.schemas import EventIn, MeasurementIn

STEP_MINUTES: dict[str, tuple[int, int]] = {
    "SUBSTRATE_START": (6, 12),
    "BOTTOM_ELECTRODE": (35, 50),
    "PIEZO_DEPOSITION": (55, 75),
    "TOP_ELECTRODE": (30, 45),
    "LITHOGRAPHY": (40, 55),
    "ETCH": (45, 65),
    "FREQ_TRIM": (25, 40),
    "RF_PROBE": (35, 50),
    "DICE": (20, 35),
    "FINAL_TEST": (30, 45),
}

BASE_YIELD = {"XB-C-2G4": 0.958, "XB-N77": 0.934, "XB-S-KU": 0.908}

ALARM_LIBRARY = {
    "PIEZO_DEPOSITION": ("GAS_FLOW_LOW", "warning", "MFC flow below recipe tolerance"),
    "ETCH": ("CHAMBER_PRESSURE", "alarm", "Chamber pressure above interlock band"),
    "RF_PROBE": ("PROBE_CONTACT", "warning", "Probe contact resistance high"),
    "FREQ_TRIM": ("RF_REFLECTED_POWER", "warning", "Trim head reflected power high"),
    "DICE": ("HANDLER_PICK_FAIL", "alarm", "Pick failed, wafer returned to cassette"),
}


def _aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


class _Emitter:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.seq = 0
        self.events: list[EventIn] = []

    def add(
        self,
        event_type: str,
        tool_id: str,
        timestamp: datetime,
        payload: dict,
        lot_id: str | None,
        ceid: int,
    ) -> None:
        self.seq += 1
        self.events.append(
            EventIn(
                event_id=f"seed-{self.seed}-{self.seq:05d}",
                event_type=event_type,  # type: ignore[arg-type]
                timestamp=_aware(timestamp),
                tool_id=tool_id,
                lot_id=lot_id,
                ceid=ceid,
                payload=payload,
            )
        )


def _spec_map(recipe_id: str) -> dict[str, dict]:
    return {str(spec["metric"]): spec for spec in recipe_specs(recipe_id)}


def _sample(rng: random.Random, center: float, sigma: float, slots: list[int], metric: str, unit: str) -> list[MeasurementIn]:
    readings: list[MeasurementIn] = []
    for slot in slots:
        value = rng.gauss(center, sigma)
        readings.append(
            MeasurementIn(metric=metric, value=round(value, 3), unit=unit, wafer_slot=slot)
        )
    return readings


def build_history(
    as_of: datetime,
    days: int = 14,
    seed: int = 42,
    wafers: int = 25,
) -> list[EventIn]:
    """Build a chronological event list ending just before ``as_of``.

    The stream includes a thickness/frequency excursion, a few holds and a
    scrap, one lot still in lithography, and two alarms left open.
    """
    if days < 2:
        raise ValueError("days must be at least 2")
    if not 1 <= wafers <= 25:
        raise ValueError("wafers must be between 1 and 25")

    as_of = _aware(as_of)
    start = as_of - timedelta(days=days)
    horizon = as_of - timedelta(hours=3)
    excursion_day = (start + timedelta(days=max(days - 5, 1))).date()
    rng = random.Random(seed)
    emit = _Emitter(seed)
    recipes = list(RECIPE_BY_ID)
    clock = {tool_id: start for tool_id in step_tools("SUBSTRATE_START")}
    for step in STEP_IDS:
        for tool_id in step_tools(step):
            clock.setdefault(tool_id, start)

    lot_index = 0
    while True:
        desired = start + timedelta(hours=6 * lot_index, minutes=15)
        if desired >= horizon:
            break
        scheduled = _schedule_lot(
            rng=rng,
            emit_seed=seed,
            lot_index=lot_index,
            desired=desired,
            horizon=horizon,
            wafers=wafers,
            recipe_id=recipes[lot_index % len(recipes)],
            clock=clock,
            excursion_day=excursion_day,
        )
        if scheduled is None:
            break
        emit.events.extend(scheduled)
        lot_index += 1

    _append_live_tail(emit, as_of, wafers)
    emit.events.sort(key=lambda event: (event.timestamp, event.event_id))
    return emit.events


def _schedule_lot(
    rng: random.Random,
    emit_seed: int,
    lot_index: int,
    desired: datetime,
    horizon: datetime,
    wafers: int,
    recipe_id: str,
    clock: dict[str, datetime],
    excursion_day,
) -> list[EventIn] | None:
    """Return the lot's events, or None if it would finish after the horizon.

    ``clock`` is updated only when the lot is accepted.
    """
    shadow = dict(clock)
    local = _Emitter(emit_seed)
    local.seq = 10_000 + lot_index * 100  # replaced after accept; unique temporarily
    operator = ("OP-14", "OP-22", "OP-31")[lot_index % 3]
    lot_id = f"L{desired:%y%m%d}-{lot_index + 1:03d}"
    hold = lot_index % 17 == 7
    abort = lot_index % 19 == 11
    cursor = desired
    remaining = wafers
    excursion = False
    specs = _spec_map(recipe_id)

    for step in STEP_IDS:
        tool_id = min(step_tools(step), key=lambda tool: shadow[tool])
        t_in = max(cursor, shadow[tool_id])
        minutes = rng.randint(*STEP_MINUTES[step])
        t_out = t_in + timedelta(minutes=minutes)
        if t_out > horizon and not (hold and step == "ETCH"):
            return None
        if step == "PIEZO_DEPOSITION":
            excursion = t_in.date() == excursion_day

        local.add(
            "tool_state",
            tool_id,
            t_in,
            {
                "from_state": "IDLE",
                "to_state": "EXECUTING",
                "recipe_id": recipe_id,
                "operator": operator,
            },
            lot_id,
            CEID_TOOL_STATE,
        )
        local.add(
            "lot_move",
            tool_id,
            t_in + timedelta(seconds=1),
            {
                "action": "track_in",
                "step": step,
                "recipe_id": recipe_id,
                "wafers_in": remaining,
                "wafers_out": remaining,
                "scrap_wafers": 0,
                "measurements": [],
            },
            lot_id,
            CEID_TRACK_IN,
        )

        if hold and step == "ETCH":
            code, severity, text = ALARM_LIBRARY["ETCH"]
            local.add(
                "alarm",
                tool_id,
                t_in + timedelta(minutes=8),
                {
                    "alarm_id": f"HLD-{lot_id}",
                    "alarm_code": code,
                    "severity": severity,
                    "state": "set",
                    "text": text,
                },
                lot_id,
                CEID_ALARM_SET,
            )
            local.add(
                "lot_move",
                tool_id,
                t_in + timedelta(minutes=12),
                {
                    "action": "hold",
                    "step": step,
                    "recipe_id": recipe_id,
                    "wafers_in": remaining,
                    "wafers_out": remaining,
                    "scrap_wafers": 0,
                    "measurements": [],
                },
                lot_id,
                CEID_HOLD,
            )
            local.add(
                "alarm",
                tool_id,
                t_in + timedelta(minutes=20),
                {
                    "alarm_id": f"HLD-{lot_id}",
                    "alarm_code": code,
                    "severity": severity,
                    "state": "clear",
                    "text": "Interlock reset, lot held for engineering review",
                },
                lot_id,
                CEID_ALARM_CLEAR,
            )
            local.add(
                "tool_state",
                tool_id,
                t_in + timedelta(minutes=21),
                {
                    "from_state": "EXECUTING",
                    "to_state": "IDLE",
                    "recipe_id": recipe_id,
                    "operator": operator,
                },
                lot_id,
                CEID_TOOL_STATE,
            )
            shadow[tool_id] = t_in + timedelta(minutes=22)
            clock.update(shadow)
            return _reidentify(local.events, emit_seed, lot_index)

        alarm_chance = 0.45 if excursion and step in ALARM_LIBRARY else 0.1
        if step in ALARM_LIBRARY and rng.random() < alarm_chance:
            code, severity, text = ALARM_LIBRARY[step]
            local.add(
                "alarm",
                tool_id,
                t_in + timedelta(minutes=5),
                {
                    "alarm_id": f"AL-{lot_id}-{step[:3]}",
                    "alarm_code": code,
                    "severity": severity,
                    "state": "set",
                    "text": text,
                },
                lot_id,
                CEID_ALARM_SET,
            )
            local.add(
                "alarm",
                tool_id,
                t_out - timedelta(minutes=2),
                {
                    "alarm_id": f"AL-{lot_id}-{step[:3]}",
                    "alarm_code": code,
                    "severity": severity,
                    "state": "clear",
                    "text": f"{code} cleared",
                },
                lot_id,
                CEID_ALARM_CLEAR,
            )

        scrap = _scrap_wafers(rng, step, remaining, excursion)
        if abort and step == "DICE":
            scrap = remaining
        leaving = remaining - scrap
        measurements = _measurements(
            rng, step, recipe_id, specs, excursion, remaining, wafers
        )

        if leaving == 0:
            local.add(
                "lot_move",
                tool_id,
                t_out,
                {
                    "action": "scrap",
                    "step": step,
                    "recipe_id": recipe_id,
                    "wafers_in": remaining,
                    "wafers_out": 0,
                    "scrap_wafers": scrap,
                    "measurements": [item.model_dump() for item in measurements],
                },
                lot_id,
                CEID_SCRAP,
            )
            local.add(
                "tool_state",
                tool_id,
                t_out + timedelta(seconds=1),
                {
                    "from_state": "EXECUTING",
                    "to_state": "IDLE",
                    "recipe_id": recipe_id,
                    "operator": operator,
                },
                lot_id,
                CEID_TOOL_STATE,
            )
            shadow[tool_id] = t_out + timedelta(seconds=30)
            clock.update(shadow)
            return _reidentify(local.events, emit_seed, lot_index)

        payload: dict = {
            "action": "track_out",
            "step": step,
            "recipe_id": recipe_id,
            "wafers_in": remaining,
            "wafers_out": leaving,
            "scrap_wafers": scrap,
            "measurements": [item.model_dump() for item in measurements],
        }
        if step == "FINAL_TEST":
            die_per_wafer = int(RECIPE_BY_ID[recipe_id]["die_per_wafer"])
            tested = leaving * die_per_wafer
            draw = BASE_YIELD[recipe_id] + rng.gauss(0, 0.01)
            if excursion:
                draw -= 0.075
            draw = min(0.992, max(0.70, draw))
            payload["tested_die"] = tested
            payload["good_die"] = round(tested * draw)
        local.add("lot_move", tool_id, t_out, payload, lot_id, CEID_TRACK_OUT)
        local.add(
            "tool_state",
            tool_id,
            t_out + timedelta(seconds=1),
            {
                "from_state": "EXECUTING",
                "to_state": "IDLE",
                "recipe_id": recipe_id,
                "operator": operator,
            },
            lot_id,
            CEID_TOOL_STATE,
        )
        shadow[tool_id] = t_out + timedelta(seconds=30)
        remaining = leaving
        cursor = t_out + timedelta(minutes=rng.randint(4, 10))

    clock.update(shadow)
    return _reidentify(local.events, emit_seed, lot_index)


def _scrap_wafers(rng: random.Random, step: str, remaining: int, excursion: bool) -> int:
    if remaining <= 1 or step not in {"PIEZO_DEPOSITION", "ETCH", "FREQ_TRIM", "DICE"}:
        return 0
    probability = 0.05
    if excursion and step in {"PIEZO_DEPOSITION", "ETCH"}:
        probability = 0.38
    if rng.random() < probability:
        return 1
    return 0


def _measurements(
    rng: random.Random,
    step: str,
    recipe_id: str,
    specs: dict[str, dict],
    excursion: bool,
    remaining: int,
    wafers: int,
) -> list[MeasurementIn]:
    slots = rng.sample(range(1, wafers + 1), k=min(5, remaining, wafers))
    slots.sort()
    bias = excursion
    if step == "PIEZO_DEPOSITION":
        spec = specs["piezo_thickness_nm"]
        center = float(spec["target"]) + (24.0 if bias else 0.0)
        return _sample(rng, center, 8.0, slots, "piezo_thickness_nm", "nm")
    if step == "FREQ_TRIM":
        spec = specs["resonance_mhz"]
        target = float(spec["target"])
        center = target + (target * 0.006 if bias else 0.0)
        return _sample(rng, center, target * 0.0015, slots, "resonance_mhz", "MHz")
    if step == "RF_PROBE":
        freq = specs["resonance_mhz"]
        loss = specs["insertion_loss_db"]
        target = float(freq["target"])
        center = target + (target * 0.004 if bias else 0.0)
        readings = _sample(rng, center, target * 0.0018, slots, "resonance_mhz", "MHz")
        readings.extend(
            _sample(
                rng,
                float(loss["target"]) + (0.28 if bias else 0.0),
                0.12,
                slots,
                "insertion_loss_db",
                "dB",
            )
        )
        return readings
    if step == "FINAL_TEST":
        loss = specs["insertion_loss_db"]
        return _sample(
            rng,
            float(loss["target"]) + (0.18 if bias else 0.0),
            0.1,
            slots,
            "insertion_loss_db",
            "dB",
        )
    return []


def _reidentify(events: list[EventIn], seed: int, lot_index: int) -> list[EventIn]:
    """Assign stable ids once a lot is committed to the history."""
    rebuilt: list[EventIn] = []
    for offset, event in enumerate(events, start=1):
        rebuilt.append(
            event.model_copy(
                update={"event_id": f"seed-{seed}-L{lot_index + 1:03d}-{offset:02d}"}
            )
        )
    return rebuilt


def _append_live_tail(emit: _Emitter, as_of: datetime, wafers: int) -> None:
    """Leave the line in a recognizable state: WIP at lithography, etch down."""
    recipe_id = "XB-N77"
    lot_id = f"L{as_of:%y%m%d}-WIP"
    cursor = as_of - timedelta(hours=2, minutes=10)
    plan = [
        ("SUBSTRATE_START", "STK-01", 8),
        ("BOTTOM_ELECTRODE", "SPT-01", 28),
        ("PIEZO_DEPOSITION", "DEP-01", 36),
    ]
    remaining = wafers
    for step, tool_id, minutes in plan:
        t_out = cursor + timedelta(minutes=minutes)
        emit.add(
            "tool_state",
            tool_id,
            cursor,
            {"from_state": "IDLE", "to_state": "EXECUTING", "recipe_id": recipe_id, "operator": "OP-22"},
            lot_id,
            CEID_TOOL_STATE,
        )
        emit.add(
            "lot_move",
            tool_id,
            cursor + timedelta(seconds=1),
            {
                "action": "track_in",
                "step": step,
                "recipe_id": recipe_id,
                "wafers_in": remaining,
                "wafers_out": remaining,
                "scrap_wafers": 0,
                "measurements": [],
            },
            lot_id,
            CEID_TRACK_IN,
        )
        measurements: list[MeasurementIn] = []
        if step == "PIEZO_DEPOSITION":
            measurements = _sample(
                random.Random(7),
                1004.0,
                6.0,
                [2, 8, 14, 19, 23],
                "piezo_thickness_nm",
                "nm",
            )
        emit.add(
            "lot_move",
            tool_id,
            t_out,
            {
                "action": "track_out",
                "step": step,
                "recipe_id": recipe_id,
                "wafers_in": remaining,
                "wafers_out": remaining,
                "scrap_wafers": 0,
                "measurements": [item.model_dump() for item in measurements],
            },
            lot_id,
            CEID_TRACK_OUT,
        )
        emit.add(
            "tool_state",
            tool_id,
            t_out + timedelta(seconds=1),
            {"from_state": "EXECUTING", "to_state": "IDLE", "recipe_id": recipe_id, "operator": "OP-22"},
            lot_id,
            CEID_TOOL_STATE,
        )
        cursor = t_out + timedelta(minutes=6)

    emit.add(
        "tool_state",
        "LTH-01",
        as_of - timedelta(minutes=18),
        {"from_state": "IDLE", "to_state": "EXECUTING", "recipe_id": recipe_id, "operator": "OP-22"},
        lot_id,
        CEID_TOOL_STATE,
    )
    emit.add(
        "lot_move",
        "LTH-01",
        as_of - timedelta(minutes=18) + timedelta(seconds=1),
        {
            "action": "track_in",
            "step": "LITHOGRAPHY",
            "recipe_id": recipe_id,
            "wafers_in": remaining,
            "wafers_out": remaining,
            "scrap_wafers": 0,
            "measurements": [],
        },
        lot_id,
        CEID_TRACK_IN,
    )
    emit.add(
        "tool_state",
        "ETH-01",
        as_of - timedelta(minutes=26),
        {"from_state": "IDLE", "to_state": "ALARM", "recipe_id": None, "operator": "OP-14"},
        None,
        CEID_TOOL_STATE,
    )
    emit.add(
        "alarm",
        "ETH-01",
        as_of - timedelta(minutes=26),
        {
            "alarm_id": "ETH-OPEN-1",
            "alarm_code": "CHAMBER_PRESSURE",
            "severity": "alarm",
            "state": "set",
            "text": "Chamber pressure above interlock — etch waiting on recovery",
        },
        None,
        CEID_ALARM_SET,
    )
    emit.add(
        "alarm",
        "DEP-01",
        as_of - timedelta(minutes=11),
        {
            "alarm_id": "DEP-OPEN-1",
            "alarm_code": "THICKNESS_DRIFT",
            "severity": "warning",
            "state": "set",
            "text": "Piezo thickness running high versus target — watch next lots",
        },
        lot_id,
        CEID_ALARM_SET,
    )
