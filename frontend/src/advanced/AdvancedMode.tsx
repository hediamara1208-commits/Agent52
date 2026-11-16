import type { Focus, SessionView } from "../model/sessionView";
import { ExhibitList } from "./ExhibitList";
import { RuleTable } from "./RuleTable";
import { SensitivityPanel } from "./SensitivityPanel";

const VERDICT_COLOR: Record<string, string> = { accept: "var(--pass)", accept_with_conditions: "var(--warn)", reject: "var(--fail)" };

function Kpis({ view }: { view: SessionView }) {
  const failing = view.rule_results.filter((r) => r.status === "fail").length;
  const v = view.verdict;
  return (
    <div className="kpis" data-testid="kpis">
      <div className="kpi">
        <div className="kpi-label">Verdict</div>
        <div className="kpi-value" style={{ color: v ? VERDICT_COLOR[v.verdict] : undefined, fontSize: "1.2rem", paddingTop: ".35rem" }}>
          {v ? v.verdict.replace(/_/g, " ") : "pending"}
        </div>
        <div className="kpi-sub">from your limits</div>
      </div>
      <div className="kpi">
        <div className="kpi-label">Largest size</div>
        <div className="kpi-value">{v?.max_weight != null ? `${(v.max_weight * 100).toFixed(1)}%` : "—"}</div>
        <div className="kpi-sub">within every limit</div>
      </div>
      <div className="kpi">
        <div className="kpi-label">Limits respected</div>
        <div className="kpi-value" style={{ color: failing ? "var(--fail)" : "var(--pass)" }}>
          {view.rule_results.length - failing}/{view.rule_results.length}
        </div>
        <div className="kpi-sub">{failing} failing</div>
      </div>
      <div className="kpi">
        <div className="kpi-label">Evidence</div>
        <div className="kpi-value">{view.exhibits.length}</div>
        <div className="kpi-sub">calculations and sources</div>
      </div>
    </div>
  );
}

/** Advanced_Mode: analyst dashboard over the shared SessionView (Req. 7.6, 7.7, 7.17). */
export function AdvancedMode({ view, focus, onFocus }: {
  view: SessionView; focus: Focus | null; onFocus: (focus: Focus) => void;
}) {
  const openExhibit = (number: number) => onFocus({ kind: "exhibit", number });
  return (
    <div data-testid="advanced-mode">
      <Kpis view={view} />
      <div className="dash-grid">
        <div className="card span-2">
          <RuleTable rules={view.rule_results} focusedRule={focus?.kind === "rule" ? focus.rule : null} onExhibit={openExhibit} />
        </div>
        <div className="card">
          <ExhibitList exhibits={view.exhibits} focusedNumber={focus?.kind === "exhibit" ? focus.number : null} onFocus={openExhibit} />
        </div>
        <div className="card">
          <SensitivityPanel results={view.sensitivity} onExhibit={openExhibit} />
        </div>
      </div>
    </div>
  );
}
