import type { Focus, SessionView } from "../model/sessionView";
import { PortfolioComparison, type Weights } from "../Portfolio";
import { StatementText } from "./ExhibitLinks";
import { RULE_NAMES, plain } from "./plain";
export { plain };

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
  return requestOf(view)?.weight ?? null;
}

/** The asset and size the investor asked about. */
export function requestOf(view: SessionView): { ticker: string; weight: number } | null {
  const options = (view.ruling as unknown as { options?: { option_id?: string; weight?: number; ticker?: string }[] } | null)?.options;
  const o = options?.find((x) => x.option_id === "request");
  return o && typeof o.weight === "number" && typeof o.ticker === "string" ? { ticker: o.ticker, weight: o.weight } : null;
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
      <path d="M 20 110 A 80 80 0 0 1 180 110" fill="none" stroke="var(--surface-2)" strokeWidth="14" strokeLinecap="round" />
      <path className="gauge-arc" d="M 20 110 A 80 80 0 0 1 180 110" fill="none" stroke="var(--accent)" strokeWidth="14"
        strokeLinecap="round" strokeDasharray={len} strokeDashoffset={len * (1 - frac)} />
      <text x="100" y="92" textAnchor="middle" fontSize="28" fontWeight="600" fill="var(--text)">{pct(allowed)}</text>
      <text x="100" y="114" textAnchor="middle" fontSize="11" fill="var(--muted)">
        {requested != null ? `max allowed · requested ${pct(requested)}` : "max allowed"}
      </text>
    </svg>
  );
}

/** Verdict and "What would change the verdict" in plain language (Req. 7.12). */

export function VerdictPanel({
  view, onSeeDetails, portfolio,
}: {
  view: SessionView; onSeeDetails: (focus: Focus) => void;
  /** The investor's current holdings, when known, for the before-and-after comparison. */
  portfolio?: Weights | null;
}) {
  const { verdict, ruling } = view;
  if (!verdict) return null;
  const openExhibit = (number: number) => onSeeDetails({ kind: "exhibit", number });
  const request = requestOf(view);
  const requested = request?.weight ?? null;
  const failed = verdict.failing_rules ?? [];
  // For a conditional accept the verdict lists no failing rule: show the limits the request itself broke.
  const decisive = failed.length ? failed : verdict.verdict === "accept" ? [] : view.rule_results.filter((r) => r.status === "fail").map((r) => r.rule);
  const names = decisive.map((r) => RULE_NAMES[r] ?? r.replace(/_/g, " "));
  const why = verdict.tension || verdict.reason;
  const smaller = verdict.max_weight != null && requested != null && requested > verdict.max_weight + 1e-9;
  return (
    <section aria-label="Verdict" className="card verdict">
      <h3>Decision</h3>
      <h2 data-testid="verdict" className="verdict-line">
        <span className="sr-only" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>Verdict: </span>
        <span className="verdict-stamp" data-kind={verdict.verdict}>{verdictLabel(verdict.verdict)}</span>
      </h2>
      <dl className="verdict-facts">
        {request && (<><dt>You asked for</dt><dd>{pct(request.weight)} in {request.ticker}</dd></>)}
        {verdict.max_weight != null && (<><dt>{smaller ? "Largest size within your limits" : "Size accepted"}</dt><dd data-testid="verdict-max">{pct(verdict.max_weight)}</dd></>)}
        {names.length > 0 && (<><dt>{verdict.verdict === "accept" ? "Limits checked" : "Limits exceeded at the size you asked for"}</dt>
          <dd aria-label="Failing rules">{names.join(", ")}</dd></>)}
      </dl>
      {why && <p className="verdict-why" data-testid="verdict-why"><b>Why.</b> {plain(why)}</p>}
      {portfolio && request && (
        <details className="more" data-testid="verdict-portfolio">
          <summary>View portfolio comparison</summary>
          <PortfolioComparison base={portfolio} ticker={request.ticker} requested={request.weight} accepted={verdict.verdict === "reject" ? null : verdict.max_weight} />
        </details>
      )}
      {ruling && ruling.what_would_change.length > 0 && (
        <details className="more">
          <summary>What would change the decision</summary>
          <ul className="change-list">
            {ruling.what_would_change.map((s, i) => (
              <li key={i}><StatementText statement={{ ...s, text: plain(s.text) }} onOpen={openExhibit} /></li>
            ))}
          </ul>
        </details>
      )}
      {(verdict.conditions ?? []).length > 0 && (
        <ul className="sr-only" data-testid="verdict-conditions" style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0 0 0 0)" }}>
          {(verdict.conditions ?? []).map((c, i) => <li key={i}>{plain(c)}</li>)}
        </ul>
      )}
    </section>
  );
}
