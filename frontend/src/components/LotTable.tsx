import { pct, stamp } from "../format";
import type { Lot } from "../types";

const FILTERS = ["ALL", "WIP", "HOLD", "COMPLETE", "SCRAPPED"] as const;

export function LotTable({
  lots,
  status,
  onStatus,
}: {
  lots: Lot[];
  status: (typeof FILTERS)[number];
  onStatus: (status: (typeof FILTERS)[number]) => void;
}) {
  const visible = lots.filter((lot) => status === "ALL" || lot.status === status);

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Lots</h2>
          <p>WIP and holds stay pinned above closed lots.</p>
        </div>
        <div className="filters" role="tablist" aria-label="Lot status">
          {FILTERS.map((item) => (
            <button
              key={item}
              type="button"
              className={item === status ? "on" : ""}
              onClick={() => onStatus(item)}
            >
              {item === "ALL" ? "All" : item[0] + item.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
      </div>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Lot</th>
              <th>Recipe</th>
              <th>Status</th>
              <th>Step</th>
              <th>Wafers</th>
              <th>Scrap</th>
              <th>Die yield</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((lot) => (
              <tr key={lot.id}>
                <td className="mono">{lot.id}</td>
                <td>
                  <span className="mono">{lot.recipe_id}</span>
                  <span className="sub">{lot.recipe_name}</span>
                </td>
                <td>
                  <span className={`status status-${lot.status.toLowerCase()}`}>{lot.status}</span>
                </td>
                <td>
                  {lot.step_label ?? "—"}
                  <span className="sub">{lot.current_tool_id ?? ""}</span>
                </td>
                <td className="num">{lot.wafer_count}</td>
                <td className="num">{lot.scrap_wafers}</td>
                <td className="num">{pct(lot.die_yield)}</td>
                <td className="mono dim">{stamp(lot.started_at)}</td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={8} className="empty">
                  No lots in this state.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
