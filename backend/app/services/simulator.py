"""Light live ingest so tool state and the alarm feed keep moving.

The simulator does not complete lots. Yield, scrap, and throughput stay
anchored to the seeded history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.domain.catalog import CEID_ALARM_CLEAR, CEID_ALARM_SET, CEID_TOOL_STATE
from app.schemas import EventIn

_CYCLE = ("SPT-02", "PRB-02", "DIC-01", "PKG-01", "LTH-02")


class LiveSimulator:
    def __init__(self) -> None:
        self.tick = 0
        self._open_alarm: str | None = None

    def next_event(self, now: datetime | None = None) -> EventIn:
        moment = now or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        self.tick += 1
        tool_id = _CYCLE[self.tick % len(_CYCLE)]

        if self._open_alarm and self.tick % 5 == 0:
            alarm_tool, alarm_id = self._open_alarm.split(":", 1)
            self._open_alarm = None
            return EventIn(
                event_id=f"live-{uuid4().hex[:12]}",
                event_type="alarm",
                timestamp=moment,
                tool_id=alarm_tool,
                ceid=CEID_ALARM_CLEAR,
                payload={
                    "alarm_id": alarm_id,
                    "alarm_code": "HANDLER_PICK_FAIL",
                    "severity": "warning",
                    "state": "clear",
                    "text": "Transient handler warning cleared",
                },
            )

        if self.tick % 5 == 0:
            alarm_id = f"LIVE-{self.tick}"
            self._open_alarm = f"{tool_id}:{alarm_id}"
            return EventIn(
                event_id=f"live-{uuid4().hex[:12]}",
                event_type="alarm",
                timestamp=moment,
                tool_id=tool_id,
                ceid=CEID_ALARM_SET,
                payload={
                    "alarm_id": alarm_id,
                    "alarm_code": "HANDLER_PICK_FAIL",
                    "severity": "warning",
                    "state": "set",
                    "text": "Transient handler warning — auto recovery armed",
                },
            )

        to_state = "EXECUTING" if self.tick % 2 == 0 else "IDLE"
        from_state = "IDLE" if to_state == "EXECUTING" else "EXECUTING"
        return EventIn(
            event_id=f"live-{uuid4().hex[:12]}",
            event_type="tool_state",
            timestamp=moment,
            tool_id=tool_id,
            ceid=CEID_TOOL_STATE,
            payload={
                "from_state": from_state,
                "to_state": to_state,
                "recipe_id": "XB-C-2G4" if to_state == "EXECUTING" else None,
                "operator": "OP-31",
            },
        )
