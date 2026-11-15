import type { Focus, SessionView } from "../model/sessionView";
import { StatementText } from "./ExhibitLinks";

const VERDICT_TEXT: Record<string, string> = {
  accept: "Accepted",
  accept_with_conditions: "Accepted with conditions",
  reject: "Rejected",
};
const VERDICT_ICON: Record<string, string> = { accept: "✓", accept_with_conditions: "◐", reject: "✕" };

export function verdictLabel(v: string): string {
  return VERDICT_TEXT[v] ?? v;
}

/** Requested position size, read from the request Option the orchestrator puts in the Ruling. */
export function requestedWeight(view: SessionView): number | null {
  const options = (view.ruling as unknown as { options?: { option_id?: string; weight?: number }[] } | null)?.options;
  const w = options?.find((o) => o.option_id === "request")?.weight;
  return typeof w === "number" ? w : null;
}

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

/** Half-circle gauge: how much of the requested size the contract allows. */
export function SizeGauge({ allowed, requested }: { allowed: number; requested: number | null }) {
  const scale = Math.max(requested ?? allowed, allowed, 0.0001);
  const frac = Math.min(allowed / scale, 1);
  const len = Math.PI * 80;
  return (
    <svg className="gauge" viewBox="0 0 200 130" width="100%" role="img"
      aria-label={`Allowed ${pct(allowed)}${requested != null ? ` of requested ${pct(requested)}` : ""}`}>
      <defs>
        <linearGradient id="gaugeGrad" x1="0" x2="1">
          <stop offset="0" stopColor="#34d399" />
          <stop offset="0.6" stopColor="#fbbf24" />
          <stop offset="1" stopColor="#f6d58e" />
        </linearGradient>
      </defs>
      <path d="M 20 110 A 80 80 0 0 1 180 110" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="14" strokeLinecap="round" />
      <path className="gauge-arc" d="M 20 110 A 80 80 0 0 1 180 110" fill="none" stroke="url(#gaugeGrad)" strokeWidth="14"
        strokeLinecap="round" strokeDasharray={len} strokeDashoffset={len * (1 - frac)} />
      <text x="100" y="92" textAnchor="middle" fontSize="28" fontWeight="800" fill="#e9edf6">{pct(allowed)}</text>
      <text x="100" y="114" textAnchor="middle" fontSize="11" fill="#8b95ad">
        {requested != null ? `max allowed · requested ${pct(requested)}` : "max allowed"}
      </text>
    </svg>
  );
}

/** Verdict and "What would change the verdict" in plain language (Req. 7.12). */
export function VerdictPanel({
  view, onSeeDetails,
}: { view: SessionView; onSeeDetails: (focus: Focus) => void }) {
  const { verdict, ruling } = view;
  if (!verdict) return null;
  const openExhibit = (number: number) => onSeeDetails({ kind: "exhibit", number });
  const requested = requestedWeight(view);
  return (
    <section aria-label="Verdict" className="card">
      <div className="verdict-card">
        <div>
          <h3>The ruling</h3>
          <h2 data-testid="verdict" style={{ margin: 0 }}>
            <span className="sr-only" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>Verdict: </span>
            <span className="verdict-stamp" data-kind={verdict.verdict}>
              <span aria-hidden="true">{VERDICT_ICON[verdict.verdict] ?? "•"}</span>
              {verdictLabel(verdict.verdict)}
            </span>
          </h2>
          {verdict.max_weight != null && (
            <p style={{ marginTop: ".8rem" }}>Maximum weight allowed: <strong>{pct(verdict.max_weight)}</strong></p>
          )}
          {verdict.reason && <p className="verdict-reason">{verdict.reason}</p>}
          {(verdict.failing_rules ?? []).length > 0 && (
            <ul aria-label="Failing rules" className="chips" style={{ listStyle: "none", padding: 0 }}>
              {(verdict.failing_rules ?? []).map((r) => (
                <li key={r} className="chip-fail">
                  {r.replace(/_/g, " ")}{" "}
                  <button type="button" onClick={() => onSeeDetails({ kind: "rule", rule: r })}>See details</button>
                </li>
              ))}
            </ul>
          )}
          {(verdict.exhibits ?? []).length > 0 && (
            <p className="chips">
              <span style={{ color: "var(--muted)", fontSize: ".8rem", marginRight: ".3rem" }}>Evidence</span>
              {(verdict.exhibits ?? []).map((n) => (
                <button key={n} type="button" className="exhibit-link" onClick={() => openExhibit(n)}>
                  See details [Exhibit {n}]
                </button>
              ))}
            </p>
          )}
        </div>
        {verdict.max_weight != null && <SizeGauge allowed={verdict.max_weight} requested={requested} />}
      </div>
      {ruling && ruling.what_would_change.length > 0 && (
        <>
          <h3 style={{ marginTop: "1.2rem" }}>What would change the verdict</h3>
          <ul className="change-list">
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
