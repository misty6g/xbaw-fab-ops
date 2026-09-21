"""Relational projection of the fab event log."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base


class Tool(Base):
    __tablename__ = "tools"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    area: Mapped[str] = mapped_column(String(32), index=True)
    model: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(16), default="IDLE")
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    family: Mapped[str] = mapped_column(String(64))
    target_freq_mhz: Mapped[float] = mapped_column(Float)
    die_per_wafer: Mapped[int] = mapped_column(Integer)


class SpecLimit(Base):
    __tablename__ = "spec_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"), index=True)
    metric: Mapped[str] = mapped_column(String(64), index=True)
    unit: Mapped[str] = mapped_column(String(16))
    lsl: Mapped[float] = mapped_column(Float)
    usl: Mapped[float] = mapped_column(Float)
    target: Mapped[float] = mapped_column(Float)


class Lot(Base):
    __tablename__ = "lots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"), index=True)
    wafer_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="QUEUED", index=True)
    current_step: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_tool_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    good_die: Mapped[int] = mapped_column(Integer, default=0)
    tested_die: Mapped[int] = mapped_column(Integer, default=0)
    scrap_wafers: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcessEvent(Base):
    __tablename__ = "process_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    tool_id: Mapped[str] = mapped_column(ForeignKey("tools.id"), index=True)
    lot_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    ceid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlarmRecord(Base):
    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alarm_key: Mapped[str] = mapped_column(String(96), index=True)
    tool_id: Mapped[str] = mapped_column(ForeignKey("tools.id"), index=True)
    lot_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    alarm_code: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    set_event_id: Mapped[str] = mapped_column(String(64))
    clear_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class LotMove(Base):
    __tablename__ = "lot_moves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    lot_id: Mapped[str] = mapped_column(ForeignKey("lots.id"), index=True)
    tool_id: Mapped[str] = mapped_column(ForeignKey("tools.id"), index=True)
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"), index=True)
    step: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(16))
    wafers_in: Mapped[int] = mapped_column(Integer)
    wafers_out: Mapped[int] = mapped_column(Integer)
    scrap_wafers: Mapped[int] = mapped_column(Integer, default=0)
    good_die: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tested_die: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lot_id: Mapped[str] = mapped_column(ForeignKey("lots.id"), index=True)
    tool_id: Mapped[str] = mapped_column(ForeignKey("tools.id"), index=True)
    recipe_id: Mapped[str] = mapped_column(ForeignKey("recipes.id"), index=True)
    step: Mapped[str] = mapped_column(String(32))
    metric: Mapped[str] = mapped_column(String(64), index=True)
    wafer_slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
