import { useRef } from "react";
import type { Exhibit } from "../model/sessionView";
import { useFocusScroll } from "./useFocusScroll";
import { ExhibitCard, exhibitTitle } from "./ExhibitCard";

const WEB_METRIC = "web_news";


function ExhibitItem({ exhibit, focused, onFocus }: { exhibit: Exhibit; focused: boolean; onFocus: (n: number) => void }) {
  const ref = useRef<HTMLLIElement>(null);
  useFocusScroll(ref, focused);
  return (
    <li ref={ref} data-testid={`exhibit-${exhibit.number}`} data-focused={focused}>
      <button type="button" aria-expanded={focused} onClick={() => onFocus(exhibit.number)}>
        <span><span className="num">#{exhibit.number}</span> {exhibitTitle(exhibit)}</span>
        <span style={{ color: "var(--muted)" }}>{(exhibit.assets ?? []).slice(0, 3).join(", ")}</span>
      </button>
      {focused && <ExhibitCard exhibit={exhibit} />}
    </li>
  );
}

function counts(exhibits: Exhibit[]): string {
  const web = exhibits.filter((e) => e.metric === WEB_METRIC).length;
  const code = exhibits.length - web;
  return web ? `${code} calculations · ${web} news` : `${code} calculations`;
}

const GROUPS: { title: string; metrics: string[]; source: string }[] = [
  { title: "Portfolio risk", metrics: ["annualized_volatility", "portfolio_metrics", "risk_contribution"], source: "market" },
  { title: "Diversification", metrics: ["sector_weights", "correlation_with_base", "currency_exposure"], source: "market" },
  { title: "Historical performance", metrics: ["portfolio_comparison"], source: "market" },
  { title: "Investor constraints", metrics: ["max_weight_within_contract", "sensitivity"], source: "limits" },
  { title: "Market context", metrics: [WEB_METRIC], source: "news" },
];
const month = (iso?: string) => {
  if (!iso) return "";
  const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-CA", { month: "short", year: "numeric", timeZone: "UTC" });
};
function sourceLine(kind: string, items: Exhibit[]): string {
  if (kind === "news") return "News articles found by web search. Context only; never used in a calculation.";
  const e = items.find((x) => x.period_start && x.period_end);
  const period = e ? ` Period ${month(e.period_start)} to ${month(e.period_end)}.` : "";
  const base = "Daily market prices (Yahoo Finance), in CAD using the Bank of Canada USD/CAD rate.";
  return kind === "limits" ? `Your own limits, tested on the same market data. ${base}${period}` : `${base}${period}`;
}

/** Evidence browser, grouped by what the evidence is about; the focused item opens its details (Req. 7.6, 7.17). */
export function ExhibitList({ exhibits, focusedNumber, onFocus }: {
  exhibits: Exhibit[]; focusedNumber: number | null; onFocus: (n: number) => void;
}) {
  const known = new Set(GROUPS.flatMap((g) => g.metrics));
  const groups = [...GROUPS, { title: "Other calculations", metrics: [] as string[], source: "market" }]
    .map((g) => ({ ...g, items: exhibits.filter((e) => (g.metrics.length ? g.metrics.includes(e.metric) : !known.has(e.metric))) }))
    .filter((g) => g.items.length);
  return (
    <section aria-label="Exhibits">
      <div className="section-title"><h2>Evidence</h2><span className="pill">{counts(exhibits)}</span></div>
      {exhibits.length === 0 ? <p style={{ color: "var(--muted)" }}>No evidence yet.</p> : groups.map((g) => (
        <div key={g.title} className="evidence-group" data-testid={`evidence-group-${g.title.toLowerCase().replace(/ /g, "-")}`}>
          <h3>{g.title}</h3>
          <p className="evidence-source">{sourceLine(g.source, g.items)}</p>
          <ul className="exhibit-grid">
            {g.items.map((e) => (
              <ExhibitItem key={e.number} exhibit={e} focused={e.number === focusedNumber} onFocus={onFocus} />
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
