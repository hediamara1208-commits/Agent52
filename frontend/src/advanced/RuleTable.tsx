import { useRef } from "react";
import type { RuleResult } from "../model/sessionView";
import { useFocusScroll } from "./useFocusScroll";

const show = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : String(v));

function Row({ r, focused, onExhibit }: { r: RuleResult; focused: boolean; onExhibit: (n: number) => void }) {
  const ref = useRef<HTMLTableRowElement>(null);
  useFocusScroll(ref, focused);
  return (
    <tr ref={ref} data-testid={`rule-${r.rule}`} data-focused={focused} data-status={r.status}>
      <td>{r.rule}</td>
      <td>{r.status}</td>
      <td>{show(r.observed)}</td>
      <td>{show(r.limit)}</td>
      <td>
        {(r.exhibits ?? []).map((n) => (
          <button key={n} type="button" className="exhibit-link" onClick={() => onExhibit(n)}>[Exhibit {n}]</button>
        ))}
      </td>
      <td>{r.detail ?? ""}</td>
    </tr>
  );
}

/** Per-rule pass or fail table with observed values and limits (Req. 7.6). */
export function RuleTable({ rules, focusedRule, onExhibit }: {
  rules: RuleResult[]; focusedRule: string | null; onExhibit: (n: number) => void;
}) {
  return (
    <section aria-label="Rules">
      <h2>Rules</h2>
      <table>
        <thead>
          <tr><th>Rule</th><th>Result</th><th>Observed</th><th>Limit</th><th>Exhibits</th><th>Detail</th></tr>
        </thead>
        <tbody>
          {rules.map((r) => <Row key={r.rule} r={r} focused={r.rule === focusedRule} onExhibit={onExhibit} />)}
        </tbody>
      </table>
    </section>
  );
}
