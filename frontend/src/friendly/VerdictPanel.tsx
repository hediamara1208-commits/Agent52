import type { Focus, SessionView } from "../model/sessionView";
import { StatementText } from "./ExhibitLinks";

const VERDICT_TEXT: Record<string, string> = {
  accept: "Accepted",
  accept_with_conditions: "Accepted with conditions",
  reject: "Rejected",
};

export function verdictLabel(v: string): string {
  return VERDICT_TEXT[v] ?? v;
}

/** Verdict and "What would change the verdict" in plain language (Req. 7.12). */
export function VerdictPanel({
  view, onSeeDetails,
}: { view: SessionView; onSeeDetails: (focus: Focus) => void }) {
  const { verdict, ruling } = view;
  if (!verdict) return null;
  const openExhibit = (number: number) => onSeeDetails({ kind: "exhibit", number });
  return (
    <section aria-label="Verdict">
      <h2 data-testid="verdict">Verdict: {verdictLabel(verdict.verdict)}</h2>
      {verdict.max_weight != null && (
        <p>Maximum weight allowed: {(verdict.max_weight * 100).toFixed(1)}%</p>
      )}
      {verdict.reason && <p>{verdict.reason}</p>}
      {(verdict.exhibits ?? []).length > 0 && (
        <p>
          Evidence:{" "}
          {(verdict.exhibits ?? []).map((n) => (
            <button key={n} type="button" className="exhibit-link" onClick={() => openExhibit(n)}>
              See details [Exhibit {n}]
            </button>
          ))}
        </p>
      )}
      {(verdict.failing_rules ?? []).length > 0 && (
        <ul aria-label="Failing rules">
          {(verdict.failing_rules ?? []).map((r) => (
            <li key={r}>
              {r}{" "}
              <button type="button" onClick={() => onSeeDetails({ kind: "rule", rule: r })}>
                See details
              </button>
            </li>
          ))}
        </ul>
      )}
      {ruling && (
        <>
          <h3>What would change the verdict</h3>
          <ul>
            {ruling.what_would_change.map((s, i) => (
              <li key={i}>
                <StatementText statement={s} onOpen={openExhibit} />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
