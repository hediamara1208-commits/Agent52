import { useRef } from "react";
import type { RuleResult } from "../model/sessionView";
import { useFocusScroll } from "./useFocusScroll";
import { RULE_NAMES } from "../friendly/CourtroomTimeline";

const isFraction = (r: RuleResult) => r.rule !== "esg_exclusion";
export function fmtValue(r: RuleResult, v: number | null | undefined): string {
  if (v === null || v === undefined) return "n/a";
  return isFraction(r) ? `${(v * 100).toFixed(1)}%` : String(v);
}

/** Bar: observed value against the limit marker. */
function Meter({ r }: { r: RuleResult }) {
  if (r.observed == null || r.limit == null || !isFraction(r)) return null;
  const scale = Math.max(r.observed, r.limit, 0.0001) * 1.15;
  const color = r.status === "fail" ? "var(--fail)" : r.status === "pass" ? "var(--pass)" : "var(--warn)";
  return (
    <div className="meter" aria-hidden="true">
      <span style={{ width: `${(r.observed / scale) * 100}%`, background: color }} />
      <i style={{ left: `${(r.limit / scale) * 100}%` }} />
    </div>
  );
}

function Row({ r, focused, onExhibit }: { r: RuleResult; focused: boolean; onExhibit: (n: number) => void }) {
  const ref = useRef<HTMLTableRowElement>(null);
  useFocusScroll(ref, focused);
  return (
    <tr ref={ref} data-testid={`rule-${r.rule}`} data-focused={focused} data-status={r.status}>
      <td><strong>{RULE_NAMES[r.rule] ?? r.rule.replace(/_/g, " ")}</strong>{r.detail ? <div style={{ color: "var(--muted)", fontSize: ".75rem" }}>{r.detail}</div> : null}</td>
      <td><span className="status" data-status={r.status}>{r.status}</span></td>
      <td style={{ width: "30%" }}><Meter r={r} /></td>
      <td className="meter-label">{fmtValue(r, r.observed)}</td>
      <td className="meter-label">{fmtValue(r, r.limit)}</td>
      <td>
        {(r.exhibits ?? []).map((n) => (
          <button key={n} type="button" className="exhibit-link" onClick={() => onExhibit(n)}>[Exhibit {n}]</button>
        ))}
      </td>
    </tr>
  );
}

/** Per-rule pass or fail table with observed values, limits, and a bar per rule (Req. 7.6). */
export function RuleTable({ rules, focusedRule, onExhibit }: {
  rules: RuleResult[]; focusedRule: string | null; onExhibit: (n: number) => void;
}) {
  return (
    <section aria-label="Rules">
      <div className="section-title"><h2>Hard rules</h2><span className="pill">observed vs limit</span></div>
      {rules.length === 0 ? <p style={{ color: "var(--muted)" }}>No rule results yet.</p> : (
        <table>
          <thead>
            <tr><th>Your limit</th><th>Result</th><th></th><th>Measured</th><th>Limit</th><th>Evidence</th></tr>
          </thead>
          <tbody>
            {rules.map((r) => <Row key={r.rule} r={r} focused={r.rule === focusedRule} onExhibit={onExhibit} />)}
          </tbody>
        </table>
      )}
    </section>
  );
}
