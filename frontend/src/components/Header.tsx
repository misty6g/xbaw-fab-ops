import { useEffect, useState } from "react";
import { clock } from "../format";
import type { Tool } from "../types";

interface HeaderProps {
  tools: Tool[];
  openAlarms: number;
  online: boolean;
  updatedAt: Date | null;
}

export function Header({ tools, openAlarms, online, updatedAt }: HeaderProps) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const alarmed = tools.filter((tool) => tool.state === "ALARM" || tool.state === "DOWN");
  const attention = alarmed.length
    ? `${alarmed.map((tool) => tool.id).join(", ")} needs attention`
    : "Line running";

  return (
    <header className="header">
      <div className="brand">
        <svg className="mark" viewBox="0 0 36 36" aria-hidden="true">
          <rect width="36" height="36" rx="8" />
          <circle cx="18" cy="18" r="10" />
          <circle cx="18" cy="18" r="5" />
          <circle cx="18" cy="18" r="1.5" />
        </svg>
        <div>
          <p className="eyebrow">Harborline RF · Line 2 · synthetic data</p>
          <h1>XBAW Fab Ops</h1>
        </div>
      </div>
      <p className="lede">
        MES-lite console for a fictional RF bulk-acoustic-wave filter line. Track tool state,
        lot moves, yield, and a simplified SPC view.
      </p>
      <div className="header-status">
        <p className={alarmed.length ? "attention hot" : "attention"}>{attention}</p>
        <p className="meta-line">
          <span className={online ? "dot live" : "dot"} />
          {online ? "API live" : "API unreachable"}
          <span className="sep">·</span>
          {openAlarms} open alarm{openAlarms === 1 ? "" : "s"}
          <span className="sep">·</span>
          {clock(now)} UTC
        </p>
        <p className="meta-line dim">
          {updatedAt ? `Board refreshed ${clock(updatedAt)} UTC` : "Waiting for the API"}
        </p>
      </div>
    </header>
  );
}
