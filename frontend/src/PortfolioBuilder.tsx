import { useState } from "react";
import { SecuritySearch } from "./SecuritySearch";
import { findSecurity } from "./universe";
import type { Weights } from "./Portfolio";

export interface HoldingRow { ticker: string; pct: string }
export type Checked = { ok: true; value: Weights; total: number } | { ok: false; error: string; total: number };

const num = (s: string) => (/^\d+(?:[.,]\d+)?$/.test(s.trim()) ? Number(s.trim().replace(",", ".")) : NaN);

/** The typed holdings as percentages, or the one thing to fix. Nothing is assumed for a blank field. */
export function checkRows(rows: HoldingRow[]): Checked {
  const total = rows.reduce((a, r) => a + (Number.isFinite(num(r.pct)) ? num(r.pct) : 0), 0);
  if (rows.length === 0) return { ok: false, error: "Add at least one holding.", total };
  for (const r of rows) {
    const v = num(r.pct);
    if (!Number.isFinite(v) || v <= 0 || v > 100) return { ok: false, error: `Enter a percentage between 0 and 100 for ${r.ticker}.`, total };
  }
  if (Math.abs(total - 100) > 0.5) {
    const gap = 100 - total;
    return { ok: false, total, error: gap > 0 ? `${fmt(gap)}% left to allocate.` : `${fmt(-gap)}% over 100%.` };
  }
  const value: Weights = {};
  for (const r of rows) value[r.ticker] = num(r.pct);
  return { ok: true, value, total };
}
const fmt = (n: number) => String(Math.round(n * 10) / 10);

const MAX_PASTE = 4000;
/** Reads "XIU.TO 40" lines. Pasted text is only ever matched against the known securities; nothing else is kept. */
export function readPaste(text: string): { rows: HoldingRow[]; unknown: string[]; unread: number } {
  const rows: HoldingRow[] = []; const unknown: string[] = []; let unread = 0;
  for (const part of text.slice(0, MAX_PASTE).split(/[\n;]+|,(?!\d)/).map((s) => s.trim()).filter(Boolean)) {
    const m = /^([A-Za-z][A-Za-z0-9.-]{0,11})[\s:=,|]+(\d+(?:[.,]\d+)?)\s*%?$/.exec(part);
    if (!m) { unread += 1; continue; }
    const s = findSecurity(m[1].toUpperCase()) ?? findSecurity(`${m[1].toUpperCase()}.TO`);
    if (!s) { unknown.push(m[1].toUpperCase()); continue; }
    if (rows.some((r) => r.ticker === s.ticker)) continue;
    rows.push({ ticker: s.ticker, pct: m[2].replace(",", ".") });
  }
  return { rows, unknown, unread };
}

/** "Use my own portfolio": search a holding, give it a share, see the total. No account, no brokerage link. */
export function PortfolioBuilder({ rows, onChange, example }: {
  rows: HoldingRow[]; onChange: (rows: HoldingRow[]) => void; example: Weights | null;
}) {
  const [paste, setPaste] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const check = checkRows(rows);
  const set = (i: number, pct: string) => onChange(rows.map((r, j) => (j === i ? { ...r, pct } : r)));
  const importPaste = () => {
    const got = readPaste(paste);
    if (got.rows.length) onChange(got.rows);
    setNote([
      got.rows.length ? `${got.rows.length} holding${got.rows.length === 1 ? "" : "s"} imported.` : "Nothing could be imported.",
      got.unknown.length ? `Not among the securities VERDICT can analyse: ${got.unknown.slice(0, 8).join(", ")}.` : "",
      got.unread ? `${got.unread} line${got.unread === 1 ? "" : "s"} could not be read (write a ticker, then a percentage).` : "",
    ].filter(Boolean).join(" "));
  };
  return (
    <div className="builder" data-testid="portfolio-builder">
      {rows.length > 0 && (
        <ul className="builder-rows" aria-label="Your holdings">
          {rows.map((r, i) => {
            const s = findSecurity(r.ticker);
            const bad = r.pct.trim() !== "" && !(num(r.pct) > 0 && num(r.pct) <= 100);
            return (
              <li key={r.ticker}>
                <span className="builder-name"><b>{s?.name ?? r.ticker}</b><small>{r.ticker}</small></span>
                <span className="unit-input">
                  <input type="text" inputMode="decimal" autoComplete="off" aria-label={`Share of ${s?.name ?? r.ticker} (%)`}
                    aria-invalid={bad} value={r.pct} onChange={(e) => set(i, e.target.value)} />
                  <span aria-hidden="true">%</span>
                </span>
                <button type="button" className="btn-quiet" aria-label={`Remove ${s?.name ?? r.ticker}`}
                  onClick={() => onChange(rows.filter((_, j) => j !== i))}>Remove</button>
              </li>
            );
          })}
        </ul>
      )}
      <SecuritySearch value={null} label="Add a holding" placeholder="Add a holding, e.g. Royal Bank"
        onPick={(s) => { if (s && !rows.some((r) => r.ticker === s.ticker)) onChange([...rows, { ticker: s.ticker, pct: "" }]); }} />
      <p className={`builder-total${check.ok ? " ok" : ""}`} data-testid="builder-total" role="status">
        <b>Total {fmt(check.total)}%</b>{" "}{check.ok ? "Ready." : check.error}
      </p>
      <div className="builder-actions">
        {example && <button type="button" className="btn-quiet"
          onClick={() => onChange(Object.entries(example).map(([ticker, w]) => ({ ticker, pct: fmt(w * 100) })))}>Start from the example</button>}
        {rows.length > 0 && <button type="button" className="btn-quiet" onClick={() => { onChange([]); setNote(null); }}>Clear</button>}
      </div>
      <details className="own-words">
        <summary>Paste a list instead</summary>
        <label>One holding per line{" "}
          <textarea aria-label="Paste holdings" value={paste} maxLength={MAX_PASTE} placeholder={"XIU.TO 40\nRY.TO 20\nXBB.TO 40"}
            onChange={(e) => setPaste(e.target.value)} />
        </label>
        <button type="button" onClick={importPaste} disabled={!paste.trim()}>Import</button>
        {note && <p className="builder-note" role="status" data-testid="paste-note">{note}</p>}
      </details>
    </div>
  );
}
