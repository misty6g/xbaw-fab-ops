import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fixed } from "../format";
import type { Spc } from "../types";

const METRICS = [
  { id: "piezo_thickness_nm", label: "Thickness" },
  { id: "resonance_mhz", label: "Resonance" },
  { id: "insertion_loss_db", label: "Insertion loss" },
] as const;

const RECIPES = [
  { id: "", label: "All recipes" },
  { id: "XB-C-2G4", label: "XB-C-2G4" },
  { id: "XB-N77", label: "XB-N77" },
  { id: "XB-S-KU", label: "XB-S-KU" },
] as const;

export function SpcPanel({
  spc,
  metric,
  recipe,
  onMetric,
  onRecipe,
}: {
  spc: Spc;
  metric: string;
  recipe: string;
  onMetric: (metric: string) => void;
  onRecipe: (recipe: string) => void;
}) {
  const data = spc.points.map((point, index) => ({
    index: index + 1,
    value: point.value,
    oos: point.oos,
    ooc: point.ooc,
    lot: point.lot_id,
    slot: point.wafer_slot,
  }));

  const cpkTone = spc.cpk == null ? "flat" : spc.cpk >= 1.33 ? "good" : spc.cpk >= 1 ? "warn" : "hot";

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>SPC</h2>
          <p>
            Individuals chart approximation: mean ± 3σ using the sample standard deviation. Not a
            moving-range I-MR chart.
          </p>
        </div>
        <div className="filters">
          {METRICS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={item.id === metric ? "on" : ""}
              onClick={() => onMetric(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className="filters recipe-filters">
        {RECIPES.map((item) => (
          <button
            key={item.id || "all"}
            type="button"
            className={item.id === recipe ? "on" : ""}
            onClick={() => onRecipe(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="spc-stats">
        <Stat label="N" value={String(spc.n)} />
        <Stat label="Mean" value={`${fixed(spc.mean, 2)} ${spc.unit}`} />
        <Stat label="Sigma" value={fixed(spc.sigma, 2)} />
        <Stat label="Cp" value={fixed(spc.cp, 2)} />
        <Stat label="Cpk" value={fixed(spc.cpk, 2)} tone={cpkTone} />
        <Stat label="OOC" value={String(spc.ooc)} />
        <Stat label="OOS" value={String(spc.oos)} />
      </div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
            <CartesianGrid stroke="rgba(148, 184, 196, 0.12)" vertical={false} />
            <XAxis dataKey="index" tick={{ fill: "#8eacb8", fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis
              tick={{ fill: "#8eacb8", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={56}
              domain={["auto", "auto"]}
            />
            <Tooltip
              contentStyle={{
                background: "#10202b",
                border: "1px solid #2a4552",
                borderRadius: 8,
                fontSize: 12,
              }}
              formatter={(value) => [typeof value === "number" ? value.toFixed(2) : String(value), spc.unit]}
              labelFormatter={(_label, payload) => {
                const row = payload?.[0]?.payload as { lot?: string; slot?: number | null } | undefined;
                if (!row) return "";
                return `${row.lot}${row.slot ? ` · slot ${row.slot}` : ""}`;
              }}
            />
            {spc.usl != null && <ReferenceLine y={spc.usl} stroke="#ff6b78" strokeDasharray="4 4" />}
            {spc.lsl != null && <ReferenceLine y={spc.lsl} stroke="#ff6b78" strokeDasharray="4 4" />}
            {spc.ucl != null && <ReferenceLine y={spc.ucl} stroke="#e2a15a" strokeDasharray="2 3" />}
            {spc.lcl != null && <ReferenceLine y={spc.lcl} stroke="#e2a15a" strokeDasharray="2 3" />}
            {spc.target != null && <ReferenceLine y={spc.target} stroke="#3ddec8" />}
            <Line
              type="monotone"
              dataKey="value"
              name={spc.label}
              stroke="#9fd6e2"
              strokeWidth={1.6}
              dot={(props) => {
                const { cx, cy, payload } = props as {
                  cx?: number;
                  cy?: number;
                  payload?: { oos?: boolean; ooc?: boolean };
                };
                if (cx == null || cy == null) return <g />;
                const fill = payload?.oos ? "#ff6b78" : payload?.ooc ? "#e2a15a" : "#3ddec8";
                return <circle cx={cx} cy={cy} r={2.5} fill={fill} />;
              }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="legend-note">
        Teal target · amber control limits · red spec limits · red dots are out of spec.
      </p>
    </section>
  );
}

function Stat({ label, value, tone = "flat" }: { label: string; value: string; tone?: string }) {
  return (
    <div className={`stat tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
