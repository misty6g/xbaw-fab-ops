"""Pydantic contracts for ingest and read models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ToolStateName = Literal["IDLE", "SETUP", "EXECUTING", "PAUSE", "ALARM", "DOWN"]
AlarmSeverity = Literal["warning", "alarm", "critical"]
AlarmState = Literal["set", "clear"]
LotAction = Literal["track_in", "track_out", "scrap", "hold"]
EventType = Literal["tool_state", "alarm", "lot_move"]


class ToolStatePayload(BaseModel):
    from_state: ToolStateName | None = None
    to_state: ToolStateName
    recipe_id: str | None = None
    operator: str | None = None


class AlarmPayload(BaseModel):
    alarm_id: str = Field(min_length=1, max_length=64)
    alarm_code: str = Field(min_length=1, max_length=64)
    severity: AlarmSeverity
    state: AlarmState
    text: str = Field(min_length=1, max_length=240)


class MeasurementIn(BaseModel):
    metric: str = Field(min_length=1, max_length=64)
    value: float
    unit: str | None = Field(default=None, max_length=16)
    wafer_slot: int | None = Field(default=None, ge=1, le=25)


class LotMovePayload(BaseModel):
    action: LotAction
    step: str = Field(min_length=1, max_length=32)
    recipe_id: str = Field(min_length=1, max_length=32)
    wafers_in: int = Field(ge=0)
    wafers_out: int = Field(ge=0)
    scrap_wafers: int = Field(default=0, ge=0)
    good_die: int | None = Field(default=None, ge=0)
    tested_die: int | None = Field(default=None, ge=0)
    measurements: list[MeasurementIn] = Field(default_factory=list)

    @field_validator("measurements")
    @classmethod
    def cap_measurements(cls, value: list[MeasurementIn]) -> list[MeasurementIn]:
        if len(value) > 25:
            raise ValueError("at most 25 measurements per lot move")
        return value


class EventIn(BaseModel):
    event_id: str = Field(min_length=1, max_length=64)
    event_type: EventType
    timestamp: datetime
    tool_id: str = Field(min_length=1, max_length=32)
    lot_id: str | None = Field(default=None, max_length=32)
    ceid: int | None = Field(default=None, ge=0)
    payload: dict


class EventBatch(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=500)


class IngestResult(BaseModel):
    event_id: str
    status: Literal["accepted", "duplicate"]


class IngestBatchResult(BaseModel):
    accepted: int
    duplicates: int
    results: list[IngestResult]


class EventOut(BaseModel):
    event_id: str
    event_type: str
    timestamp: datetime
    tool_id: str
    lot_id: str | None
    ceid: int | None
    payload: dict
    summary: str


class LotOut(BaseModel):
    id: str
    recipe_id: str
    recipe_name: str
    status: str
    current_step: str | None
    step_label: str | None
    current_tool_id: str | None
    wafer_count: int
    scrap_wafers: int
    good_die: int
    tested_die: int
    die_yield: float | None
    line_yield: float | None
    started_at: datetime | None
    completed_at: datetime | None


class ToolOut(BaseModel):
    id: str
    name: str
    area: str
    area_label: str
    model: str
    state: str
    updated_at: datetime | None
    open_alarms: int
    utilization: float | None
    wafers_out: int
    step_yield: float | None


class AlarmOut(BaseModel):
    id: int
    tool_id: str
    tool_name: str
    lot_id: str | None
    alarm_code: str
    severity: str
    text: str
    set_at: datetime
    cleared_at: datetime | None
    open: bool


class YieldPoint(BaseModel):
    date: str
    die_yield: float | None
    line_yield: float | None
    scrap_rate: float | None
    lots: int
    wafers_started: int


class YieldGroup(BaseModel):
    key: str
    label: str
    die_yield: float | None
    line_yield: float | None
    scrap_rate: float | None
    step_yield: float | None
    lots: int
    wafers_started: int
    wafers_out: int


class SpcPoint(BaseModel):
    timestamp: datetime
    value: float
    lot_id: str
    tool_id: str
    wafer_slot: int | None
    ooc: bool
    oos: bool


class SpcOut(BaseModel):
    metric: str
    label: str
    unit: str
    recipe_id: str | None
    n: int
    mean: float | None
    sigma: float | None
    ucl: float | None
    lcl: float | None
    lsl: float | None
    usl: float | None
    target: float | None
    cp: float | None
    cpk: float | None
    ooc: int
    oos: int
    points: list[SpcPoint]


class SummaryOut(BaseModel):
    window_hours: int
    as_of: datetime
    lots_completed: int
    lots_wip: int
    lots_hold: int
    lots_scrapped: int
    die_yield: float | None
    die_yield_prior: float | None
    line_yield: float | None
    wafer_scrap_rate: float | None
    throughput_wph: float | None
    open_alarms: int
    wafers_started: int
    wafers_scrapped: int
    wafers_out: int
    good_die: int
    tested_die: int
