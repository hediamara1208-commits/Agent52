import { findSecurity } from "./universe";
import type { PersonaEntry } from "./api/client";

export type Weights = Record<string, number>;
export interface Scenario { label: string; weights: Weights }

/** The persona's own holdings, as fractions of the portfolio. */
export function personaPortfolio(p: PersonaEntry | undefined): Weights | null {
  const raw = p?.contract_values?.base_portfolio?.value;
  if (!raw || typeof raw !== "object") return null;
  const out: Weights = {};
  for (const [t, w] of Object.entries(raw as Record<string, unknown>)) if (typeof w === "number" && w > 0) out[t] = w;
  return Object.keys(out).length ? out : null;
}

/** Typed holdings come in percent (or already as fractions); the toolkit works in fractions. */
export function asFractions(w: Weights): Weights {
  const total = Object.values(w).reduce((a, b) => a + b, 0);
  const out: Weights = {};
  for (const [t, v] of Object.entries(w)) out[t] = total > 1.5 ? v / 100 : v;
  return out;
}

/** Same rule as the toolkit (guide/toolkit/risk_panel.py, _proposed): the new position is funded by
 * reducing every current holding in proportion, so the weights still add up to 100%. */
export function withPosition(base: Weights, ticker: string, weight: number): Weights {
  const out: Weights = {};
  for (const [t, w] of Object.entries(base)) out[t] = w * (1 - weight);
  out[ticker] = (out[ticker] ?? 0) + weight;
  return out;
}

const pct = (w: number | undefined) => (w === undefined || w <= 0 ? "–" : `${(w * 100).toFixed(1)}%`);
const largest = (w: Weights) => Object.entries(w).sort((a, b) => b[1] - a[1])[0];
const nameOf = (t: string) => findSecurity(t)?.name ?? t;

/** Holdings table with one column and one bar per scenario. Every scenario is hypothetical. */
export function PortfolioTable({ scenarios, highlight }: { scenarios: Scenario[]; highlight?: string }) {
  const tickers = [...new Set(scenarios.flatMap((s) => Object.keys(s.weights)))]
    .sort((a, b) => (scenarios[scenarios.length - 1].weights[b] ?? 0) - (scenarios[scenarios.length - 1].weights[a] ?? 0));
  const max = Math.max(...scenarios.flatMap((s) => Object.values(s.weights)), 0.0001);
  return (
    <div className="pf" data-testid="portfolio-table">
      <table>
        <thead>
          <tr><th scope="col">Holding</th>{scenarios.map((s) => <th key={s.label} scope="col" className="num">{s.label}</th>)}</tr>
        </thead>
        <tbody>
          {tickers.map((t) => (
            <tr key={t} className={t === highlight ? "pf-new" : undefined}>
              <th scope="row"><span className="pf-name">{nameOf(t)}</span> <span className="pf-ticker">{t}</span></th>
              {scenarios.map((s, i) => (
                <td key={s.label} className="num">
                  <span className="pf-bar" aria-hidden="true"><i className={`pf-fill pf-${i}`} style={{ width: `${((s.weights[t] ?? 0) / max) * 100}%` }} /></span>
                  {pct(s.weights[t])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">Largest holding</th>
            {scenarios.map((s) => { const [t, w] = largest(s.weights); return <td key={s.label} className="num">{t} {pct(w)}</td>; })}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

/** Before and after: the current portfolio, the request, and (after a ruling) the accepted size. */
export function PortfolioComparison({ base, ticker, requested, accepted }: {
  base: Weights; ticker: string | null; requested: number | null; accepted?: number | null;
}) {
  const scenarios: Scenario[] = [{ label: "Today", weights: base }];
  if (ticker && requested !== null && requested > 0 && requested <= 1) {
    scenarios.push({ label: `At ${(requested * 100).toFixed(requested * 100 % 1 ? 1 : 0)}% ${ticker}`, weights: withPosition(base, ticker, requested) });
    if (accepted != null && accepted > 0 && Math.abs(accepted - requested) > 1e-9) {
      scenarios.push({ label: `At ${(accepted * 100).toFixed(accepted * 100 % 1 ? 1 : 0)}% ${ticker}`, weights: withPosition(base, ticker, accepted) });
    }
  }
  return (
    <>
      <PortfolioTable scenarios={scenarios} highlight={ticker ?? undefined} />
      {scenarios.length > 1 && (
        <p className="pf-note" data-testid="portfolio-note">
          Hypothetical scenarios; nothing is bought or sold. The new position is funded by reducing every current holding in proportion.
        </p>
      )}
    </>
  );
}
