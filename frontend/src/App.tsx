import { useCallback, useEffect, useState } from "react";
import { getJson } from "./api";
import { AlarmFeed, EventLog } from "./components/AlarmFeed";
import { Header } from "./components/Header";
import { KpiStrip } from "./components/KpiStrip";
import { LotTable } from "./components/LotTable";
import { SpcPanel } from "./components/SpcPanel";
import { ToolBoard } from "./components/ToolBoard";
import { YieldPanel } from "./components/YieldPanel";
import type { Alarm, DashboardData, Lot, ProcessEvent, Spc, Summary, Tool, YieldGroup, YieldPoint } from "./types";

export function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [metric, setMetric] = useState("piezo_thickness_nm");
  const [recipe, setRecipe] = useState("XB-S-KU");
  const [status, setStatus] = useState<"ALL" | "WIP" | "HOLD" | "COMPLETE" | "SCRAPPED">("ALL");

  const load = useCallback(async () => {
    try {
      const recipeQuery = recipe ? `&recipe_id=${encodeURIComponent(recipe)}` : "";
      const [summary, trend, recipes, tools, lots, alarms, events, spc] = await Promise.all([
        getJson<Summary>("/api/kpis/summary?hours=168"),
        getJson<YieldPoint[]>("/api/kpis/yield-trend?days=14"),
        getJson<YieldGroup[]>("/api/kpis/yield?group_by=recipe&hours=168"),
        getJson<Tool[]>("/api/tools?hours=168"),
        getJson<Lot[]>("/api/lots?limit=80"),
        getJson<Alarm[]>("/api/alarms?limit=18"),
        getJson<ProcessEvent[]>("/api/events?limit=8"),
        getJson<Spc>(`/api/kpis/spc?metric=${encodeURIComponent(metric)}${recipeQuery}&limit=300`),
      ]);
      setData({ summary, trend, recipes, tools, lots, alarms, events, spc });
      setUpdatedAt(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "API unavailable");
    }
  }, [metric, recipe]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(id);
  }, [load]);

  return (
    <div className="app">
      <Header
        tools={data?.tools ?? []}
        openAlarms={data?.summary.open_alarms ?? 0}
        online={error == null && data != null}
        updatedAt={updatedAt}
      />
      {error && (
        <p className="banner" role="alert">
          Cannot reach the API ({error}). Start it with <code>docker compose up --build</code> or{" "}
          <code>make api</code>.
        </p>
      )}
      {!data && !error && <p className="banner">Loading line data…</p>}
      {data && (
        <>
          <KpiStrip summary={data.summary} />
          <div className="stack">
            <YieldPanel trend={data.trend} recipes={data.recipes} />
            <ToolBoard tools={data.tools} />
            <div className="split">
              <LotTable lots={data.lots} status={status} onStatus={setStatus} />
              <AlarmFeed alarms={data.alarms} />
            </div>
            <SpcPanel
              spc={data.spc}
              metric={metric}
              recipe={recipe}
              onMetric={setMetric}
              onRecipe={setRecipe}
            />
            <EventLog events={data.events} />
          </div>
        </>
      )}
      <footer>
        <p>
          XBAW Fab Ops is a portfolio demo by Gyan Mistry. It is not affiliated with SpaceX, Starlink,
          or Akoustis, and it does not use proprietary process data. Spec windows, tool models, and lot
          history are synthetic.
        </p>
      </footer>
    </div>
  );
}
