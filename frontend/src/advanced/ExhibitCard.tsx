import type { Exhibit } from "../model/sessionView";
import { newsDate, safeUrl } from "../friendly/NewsCards";

type Num = Record<string, number>;
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const pct = (v: number, d = 1) => `${(v * 100).toFixed(d)}%`;
const day = (iso?: string) => (iso ? newsDate(iso) ?? iso : "");

/** Human names for the data files behind an Exhibit (docs/data_sources.md). */
const SOURCES: [RegExp, string][] = [
  [/prices_daily/, "Daily prices, adjusted for splits and dividends (Yahoo Finance)"],
  [/fx_usdcad/, "USD/CAD exchange rate (Bank of Canada)"],
  [/assets_universe/, "Asset list: class, sector, currency (datathon starter data)"],
  [/esg_exclusions/, "Fossil-fuel exclusion list (team, from a public ESG fund methodology)"],
  [/macro_rates/, "Interest rates and inflation (Bank of Canada, FRED)"],
  [/corporate_actions/, "Dividends and splits (Yahoo Finance)"],
];
export function sourceLabels(exhibit: Exhibit): string[] {
  const files = exhibit.source_files ?? [];
  const out = SOURCES.filter(([re]) => files.some((f) => re.test(f))).map(([, label]) => label);
  return out.length ? out : files.length ? ["Project data files"] : [];
}

const METRIC_LABEL: Record<string, string> = {
  annualized_return: "Return per year", annualized_volatility: "Yearly swings (volatility)", max_drawdown: "Worst fall from a peak",
  return_2022: "Return in 2022", worst_rolling_252d_return: "Worst 12 months",
};
/** Lower is better for these, so a rise is shown in red. */
const RISKY = new Set(["annualized_volatility", "max_drawdown", "worst_rolling_252d_return", "return_2022"]);

export interface Described {
  title: string; why: string; key: string; keyNote?: string;
  rows?: { label: string; a?: number; b: number; worse?: boolean; text?: string; textA?: string }[];
  legend?: [string, string];
}

/** Plain-language reading of an Exhibit: what it shows, why it matters, the key result. */
export function describe(exhibit: Exhibit): Described {
  const v = exhibit.value as unknown;
  const o = (v && typeof v === "object" ? v : {}) as Record<string, unknown>;
  const asset = (exhibit.inputs as { ticker?: string; asset?: string } | undefined)?.ticker
    ?? (exhibit.inputs as { asset?: string } | undefined)?.asset ?? (exhibit.assets?.length === 1 ? exhibit.assets[0] : "the asset");
  const pair = (fmt: (n: number) => string = (n) => pct(Math.abs(n))): Described["rows"] => {
    const a = (o.base ?? {}) as Num, b = (o.proposed ?? {}) as Num;
    return Object.keys(b).filter((k) => isNum(b[k])).map((k) => ({
      label: METRIC_LABEL[k] ?? k, a: isNum(a[k]) ? Math.abs(a[k]) : undefined, b: Math.abs(b[k]),
      worse: RISKY.has(k) && isNum(a[k]) && Math.abs(b[k]) > Math.abs(a[k]) + 1e-9,
      textA: isNum(a[k]) ? fmt(a[k]) : undefined, text: fmt(b[k]),
    }));
  };
  switch (exhibit.metric) {
    case "portfolio_comparison": {
      const a = (o.base ?? {}) as Num, b = (o.proposed ?? {}) as Num;
      return { title: "Your portfolio, before and after the request", legend: ["Today", "With the request"],
        why: "Shows how the request would have changed the portfolio's swings, falls and return over the period.",
        key: isNum(a.annualized_volatility) && isNum(b.annualized_volatility) ? `${pct(a.annualized_volatility)} → ${pct(b.annualized_volatility)}` : "",
        keyNote: "yearly swings (volatility)", rows: pair((n) => pct(n)) };
    }
    case "risk_contribution": {
      const shares = Object.entries((o.share_of_variance_pct ?? {}) as Num).sort((x, y) => y[1] - x[1]);
      return { title: "Where the portfolio's risk comes from",
        why: "A holding can be a small part of the money and a large part of the risk. This splits the portfolio's ups and downs by holding.",
        key: shares.length ? `${shares[0][1].toFixed(1)}%` : "", keyNote: shares.length ? `of the risk comes from ${shares[0][0]}` : undefined,
        rows: shares.slice(0, 6).map(([label, s]) => ({ label, b: s / 100, text: `${s.toFixed(1)}%`, worse: s > 50 })) };
    }
    case "currency_exposure":
      return { title: "Currency mix, before and after", legend: ["Today", "With the request"],
        why: "A Canadian investor holding U.S. assets also carries the exchange rate.",
        key: isNum((o.proposed as Num | undefined)?.USD) ? pct((o.proposed as Num).USD) : "", keyNote: "in U.S. dollars with the request", rows: pair() };
    case "sector_weights":
      return { title: "Sector mix, before and after", legend: ["Today", "With the request"],
        why: "Shows whether the request concentrates the portfolio in one part of the economy.", key: "", rows: pair() };
    case "correlation_with_base":
      return { title: `How closely ${asset} moves with the rest of the portfolio`,
        why: "Close to 1 means it rises and falls with what you already hold, so it adds little diversification. Close to 0 means it moves on its own.",
        key: isNum(v) ? v.toFixed(2) : "", keyNote: "correlation (from -1 to 1)", rows: isNum(v) ? [{ label: "Correlation", b: Math.abs(v), text: v.toFixed(2) }] : [] };
    case "max_weight_within_contract":
      return { title: `Largest ${String(o.asset ?? asset)} position that fits every limit`,
        why: "The code tries each size in small steps and keeps the largest one that breaks none of your limits. The Judge can never go above it.",
        key: isNum(o.max_weight) ? pct(o.max_weight as number) : "none", keyNote: "of the portfolio, at most" };
    case "portfolio_metrics":
      return { title: "The portfolio with the request, in numbers",
        why: "Yearly swings and the worst fall over the period, computed on the portfolio as a whole.",
        key: isNum(o.annualized_volatility) ? pct(o.annualized_volatility as number) : "", keyNote: "yearly swings (volatility)",
        rows: ["annualized_return", "annualized_volatility", "max_drawdown"].filter((k) => isNum(o[k])).map((k) => ({ label: METRIC_LABEL[k], b: Math.abs(o[k] as number), text: pct(o[k] as number) })) };
    case "sensitivity":
      return { title: "What would change the verdict",
        why: "The code re-runs the limits while moving one input, to find where the answer flips.",
        key: o.changed ? (isNum(o.threshold) ? (Math.abs(o.threshold as number) <= 1 ? pct(o.threshold as number) : String(o.threshold)) : String(o.threshold ?? "")) : "No change",
        keyNote: o.changed ? `${String(o.variable ?? "").replace(/_/g, " ")}: the verdict becomes ${String(o.verdict_at_threshold ?? "").replace(/_/g, " ")}` : `moving ${String(o.variable ?? "").replace(/_/g, " ")} alone does not change the verdict` };
    case "annualized_volatility":
      return { title: `How much ${asset} swings in a year`, why: "Volatility is the usual size of yearly ups and downs. It is one risk indicator among others.", key: isNum(v) ? pct(v) : "", keyNote: "yearly swings, in CAD" };
    case "annualized_return":
      return { title: `What ${asset} returned per year`, why: "Past return over the period shown. It says nothing certain about the future.", key: isNum(v) ? pct(v) : "", keyNote: "per year over the period, in CAD" };
    case "max_drawdown":
      return { title: `The worst fall of ${asset}`, why: "The largest drop from a peak to the following low over the period.", key: isNum(v) ? pct(v) : "", keyNote: "from peak to low, in CAD" };
    default: {
      const name = exhibit.metric.replace(/_/g, " ");
      return { title: name.charAt(0).toUpperCase() + name.slice(1), why: "A figure computed by code from the pinned data.",
        key: isNum(v) ? (Math.abs(v) <= 1.5 ? pct(v, 2) : v.toLocaleString()) : "",
        rows: Object.entries(o).filter(([, x]) => isNum(x)).slice(0, 6).map(([k, x]) => ({ label: k.replace(/_/g, " "), b: Math.min(1, Math.abs(x as number)), text: Math.abs(x as number) <= 1.5 ? pct(x as number) : String(x) })) };
    }
  }
}

interface WebValue { title?: string; url?: string; source?: string; published?: string; snippet?: string }

function Bars({ d }: { d: Described }) {
  const rows = d.rows ?? [];
  if (!rows.length) return null;
  const max = Math.max(...rows.flatMap((r) => [r.a ?? 0, r.b]), 0.0001);
  return (
    <div className="ex-bars" role="img" aria-label={rows.map((r) => `${r.label}: ${r.textA ? `${r.textA} then ` : ""}${r.text}`).join("; ")}>
      {d.legend && <p className="ex-legend"><span className="sw sw-a" />{d.legend[0]} <span className="sw sw-b" />{d.legend[1]}</p>}
      {rows.map((r) => (
        <div key={r.label} className="ex-row">
          <span className="ex-label">{r.label}</span>
          <span className="ex-track">
            {r.a !== undefined && <span className="ex-bar ex-a" style={{ width: `${(r.a / max) * 100}%` }} />}
            <span className={`ex-bar ex-b${r.worse ? " worse" : ""}`} style={{ width: `${(r.b / max) * 100}%` }} />
          </span>
          <span className="ex-val">{r.textA ? <><s>{r.textA}</s> </> : null}<b>{r.text}</b></span>
        </div>
      ))}
    </div>
  );
}

/** One Exhibit, readable in a few seconds; the full trace stays one click away. */
export function ExhibitCard({ exhibit }: { exhibit: Exhibit }) {
  const web = exhibit.metric === "web_news";
  const wv = exhibit.value as WebValue;
  const href = web ? safeUrl(wv.url) : null;
  const d = web ? null : describe(exhibit);
  return (
    <article className="ex-card" data-testid={`exhibit-details-${exhibit.number}`}>
      <p className="ex-kicker">Evidence {exhibit.number} · {web ? "News, context only" : "calculated from market data"}</p>
      {web ? (
        <>
          <h3 className="ex-title" data-testid="web-exhibit-title">
            {href ? <a href={href} target="_blank" rel="noopener noreferrer nofollow">{wv.title ?? href}</a> : wv.title}
          </h3>
          <p className="ex-why">Recent news the court may cite as context. It never changes a number, a limit or the maximum size.</p>
          {wv.snippet && <blockquote className="ex-quote">{wv.snippet}</blockquote>}
          <p className="ex-source">Source: {wv.source ?? "web"}{wv.published ? ` · ${newsDate(wv.published)}` : ""}</p>
        </>
      ) : d && (
        <>
          <h3 className="ex-title">{d.title}</h3>
          <p className="ex-why">{d.why}</p>
          {d.key && <p className="ex-key"><strong>{d.key}</strong>{d.keyNote && <span> {d.keyNote}</span>}</p>}
          <Bars d={d} />
          <p className="ex-source">
            Source: {sourceLabels(exhibit).join("; ") || "market data"}
            {exhibit.period_start ? ` · ${day(exhibit.period_start)} to ${day(exhibit.period_end)}` : ""}{exhibit.currency ? ` · in ${exhibit.currency}` : ""}
          </p>
        </>
      )}
      {!web && (
        <details className="ex-tech">
          <summary>Method and limits</summary>
          <dl>
            {exhibit.period_start && (<><dt>Period</dt><dd>{day(exhibit.period_start)} to {day(exhibit.period_end)}</dd></>)}
            {exhibit.currency && (<><dt>Currency</dt><dd>{exhibit.currency}{(exhibit.processing_notes ?? []).some((n) => /converted from USD/i.test(n)) ? "; US-dollar prices converted at the Bank of Canada daily rate" : ""}</dd></>)}
            {exhibit.assets && exhibit.assets.length > 0 && (<><dt>Securities</dt><dd>{exhibit.assets.join(", ")}</dd></>)}
            <dt>Prices</dt><dd>Daily closing prices adjusted for splits and dividends.</dd>
            <dt>Limits</dt><dd>Measured on past prices over this period only. Past results do not predict future ones, and the securities covered all still exist today.</dd>
          </dl>
        </details>
      )}
    </article>
  );
}

/** Short name for lists and chips. */
export function exhibitTitle(exhibit: Exhibit): string {
  return exhibit.metric === "web_news" ? String((exhibit.value as WebValue).title ?? "News article") : describe(exhibit).title;
}
