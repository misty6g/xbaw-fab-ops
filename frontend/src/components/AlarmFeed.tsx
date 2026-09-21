import { stamp } from "../format";
import type { Alarm, ProcessEvent } from "../types";

export function AlarmFeed({ alarms }: { alarms: Alarm[] }) {
  const ordered = [...alarms].sort((a, b) => Number(b.open) - Number(a.open));
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Alarm feed</h2>
          <p>Open alarms stay at the top. Cleared rows remain for context.</p>
        </div>
      </div>
      <ul className="feed">
        {ordered.map((alarm) => (
          <li key={alarm.id} className={`alarm sev-${alarm.severity} ${alarm.open ? "is-open" : "is-clear"}`}>
            <div className="alarm-top">
              <span className="sev">{alarm.open ? alarm.severity : "cleared"}</span>
              <span className="mono">{alarm.tool_id}</span>
              <span className="mono dim">{alarm.alarm_code}</span>
            </div>
            <p>{alarm.text}</p>
            <p className="dim mono">
              {stamp(alarm.set_at)}
              {alarm.lot_id ? ` · ${alarm.lot_id}` : ""}
              {alarm.cleared_at ? ` · cleared ${stamp(alarm.cleared_at)}` : ""}
            </p>
          </li>
        ))}
        {ordered.length === 0 && <li className="empty">No alarms in the recent window.</li>}
      </ul>
    </section>
  );
}

export function EventLog({ events }: { events: ProcessEvent[] }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Recent events</h2>
          <p>JSON collection events as stored. CEID numbers mirror S6F11-style reports.</p>
        </div>
      </div>
      <ul className="event-log">
        {events.map((event) => (
          <li key={event.event_id}>
            <span className="mono dim">{stamp(event.timestamp)}</span>
            <span className="mono ceid">{event.ceid ?? "—"}</span>
            <span className="etype">{event.event_type}</span>
            <span className="mono">{event.tool_id}</span>
            <span className="mono dim">{event.lot_id ?? "—"}</span>
            <span className="summary">{event.summary}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
