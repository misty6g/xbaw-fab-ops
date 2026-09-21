import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { dayLabel, pct } from "../format";
import type { YieldGroup, YieldPoint } from "../types";

export function YieldPanel({ trend, recipes }: { trend: YieldPoint[]; recipes: YieldGroup[] }) {
  const data = trend.map((point) => ({
    label: dayLabel(point.date),
    die: point.die_yield == null ? null : Number((point.die_yield * 100).toFixed(2)),
    line: point.line_yield == null ? null : Number((point.line_yield * 100).toFixed(2)),
    lots: point.lots,
  }));
  const values = data.flatMap((point) => [point.die, point.line]).filter((value): value is number => value != null);
  const floor = values.length ? Math.max(60, Math.floor((Math.min(...values) - 3) / 5) * 5) : 70;

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Yield trend</h2>
          <p>Completed and scrapped lots by close date. Axis starts at {floor}%.</p>
        </div>
      </div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(148, 184, 196, 0.12)" vertical={false} />
            <XAxis dataKey="label" tick={{ fill: "#8eacb8", fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis
              domain={[floor, 100]}
              tick={{ fill: "#8eacb8", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              width={42}
              unit="%"
            />
            <Tooltip
              contentStyle={{
                background: "#10202b",
                border: "1px solid #2a4552",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: "#d5e6ec" }}
            />
            <Legend />
            <Line type="monotone" dataKey="die" name="Die yield" stroke="#3ddec8" strokeWidth={2} dot={false} connectNulls />
            <Line type="monotone" dataKey="line" name="Line yield" stroke="#e2a15a" strokeWidth={2} dot={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="recipe-list">
        {recipes.map((recipe) => (
          <div key={recipe.key} className="recipe-row">
            <div className="recipe-id">
              <strong>{recipe.key}</strong>
              <span>{recipe.label}</span>
            </div>
            <div className="bar-track" aria-hidden="true">
              <span style={{ width: `${Math.max(0, (recipe.die_yield ?? 0) * 100)}%` }} />
            </div>
            <div className="recipe-stats">
              <span>{pct(recipe.die_yield)} die</span>
              <span>{pct(recipe.line_yield)} line</span>
              <span>{pct(recipe.scrap_rate)} scrap</span>
              <span>{recipe.lots} lots</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
