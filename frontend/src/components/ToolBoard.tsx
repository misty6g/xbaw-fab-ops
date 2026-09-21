import { pct } from "../format";
import type { Tool } from "../types";

export function ToolBoard({ tools }: { tools: Tool[] }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Tool health</h2>
          <p>Route order over 7 days. Utilization is time in EXECUTING on this pilot cadence.</p>
        </div>
      </div>
      <div className="tool-grid">
        {tools.map((tool) => (
          <article key={tool.id} className={`tool state-${tool.state.toLowerCase()}`}>
            <div className="tool-top">
              <span className="tool-id">{tool.id}</span>
              <span className="state-pill">{tool.state}</span>
            </div>
            <h3>{tool.name}</h3>
            <p className="tool-model">
              {tool.area_label} · {tool.model}
            </p>
            <div className="util" aria-label="utilization">
              <span style={{ width: `${Math.round((tool.utilization ?? 0) * 100)}%` }} />
            </div>
            <dl>
              <div>
                <dt>Util</dt>
                <dd>{pct(tool.utilization, 0)}</dd>
              </div>
              <div>
                <dt>Wafers</dt>
                <dd>{tool.wafers_out}</dd>
              </div>
              <div>
                <dt>Step</dt>
                <dd>{pct(tool.step_yield, 1)}</dd>
              </div>
              <div>
                <dt>Alarms</dt>
                <dd>{tool.open_alarms}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}
