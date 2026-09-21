import { deltaPoints, integer, pct } from "../format";
import type { Summary } from "../types";

export function KpiStrip({ summary }: { summary: Summary }) {
  const cards = [
    {
      label: "Die yield",
      value: pct(summary.die_yield),
      note: deltaPoints(summary.die_yield, summary.die_yield_prior) ?? "Good die / tested die",
      tone: "good",
    },
    {
      label: "Line yield",
      value: pct(summary.line_yield),
      note: "Scrapped wafers count as lost die",
      tone: "info",
    },
    {
      label: "Wafer scrap",
      value: pct(summary.wafer_scrap_rate),
      note: `${integer(summary.wafers_scrapped)} of ${integer(summary.wafers_started)} wafers`,
      tone: "warn",
    },
    {
      label: "Wafers / day",
      value: summary.throughput_wph == null ? "—" : (summary.throughput_wph * 24).toFixed(0),
      note:
        summary.throughput_wph == null
          ? "Final test"
          : `${summary.throughput_wph.toFixed(1)} wafers/hour at final test`,
      tone: "info",
    },
    {
      label: "Open alarms",
      value: integer(summary.open_alarms),
      note: `${summary.lots_wip} WIP · ${summary.lots_hold} hold · ${summary.lots_completed} closed in window`,
      tone: summary.open_alarms > 0 ? "hot" : "good",
    },
  ];

  return (
    <section className="kpi-strip" aria-label="Line KPIs">
      {cards.map((card) => (
        <article key={card.label} className={`kpi tone-${card.tone}`}>
          <p className="kpi-label">{card.label}</p>
          <p className="kpi-value">{card.value}</p>
          <p className="kpi-note">{card.note}</p>
        </article>
      ))}
    </section>
  );
}
