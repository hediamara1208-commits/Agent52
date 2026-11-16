import { useState } from "react";
import type { SessionView } from "../model/sessionView";
import { diffSessions } from "./diff";

export interface AppealChange { field: string; value: unknown }

export const APPEAL_FIELDS = [
  "position_size", "period", "risk_level", "horizon_years", "max_volatility", "max_drawdown",
  "per_asset_cap", "per_asset_class_caps", "crypto_cap", "sector_caps", "esg_exclusions", "speculative_limit",
] as const;

/** Appeal control: changes exactly one input (Req. 30.1). */
export function AppealControl({ busy, onSubmit, view }: { busy: boolean; onSubmit: (c: AppealChange) => void; view?: SessionView | null }) {
  const whatIfs = whatIfsOf(view);
  const [field, setField] = useState<string>("position_size");
  const [text, setText] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (field === "period") {
      if (!start || !end || start >= end) { setError("Enter a start date before the end date."); return; }
      onSubmit({ field, value: { start, end } });
      return;
    }
    let value: unknown = text.trim();
    if (value === "") { setError("Enter a new value."); return; }
    try { value = JSON.parse(text); } catch { /* plain string, e.g. risk_level */ }
    if (field === "position_size" && typeof value === "number" && value > 1) value = value / 100;
    onSubmit({ field, value });
  };

  return (
    <form aria-label="Appeal" onSubmit={submit} className="appeal">
      <h2>Appeal: what if…?</h2>
      <p>Change one thing and the court hears the case again. Your original ruling stays on record, and nothing changes on screen until the new ruling is in.</p>
      {whatIfs.length > 0 && (
        <div className="whatifs" data-testid="whatifs">
          {whatIfs.map((w) => (
            <button key={w.label} type="button" className="whatif" disabled={busy} onClick={() => onSubmit(w.change)}>
              <b>{w.label}</b><small>{w.detail}</small>
            </button>
          ))}
        </div>
      )}
      <details className="appeal-custom">
        <summary>Change something else</summary>
        <label>Input to change{" "}
          <select aria-label="Appeal field" value={field} onChange={(e) => setField(e.target.value)}>
            {APPEAL_FIELDS.map((f) => <option key={f} value={f}>{FIELD_LABEL[f] ?? f}</option>)}
          </select>
        </label>{" "}
        {field === "period" ? (
          <>
            <label>Start <input type="date" aria-label="Appeal start" value={start} onChange={(e) => setStart(e.target.value)} /></label>{" "}
            <label>End <input type="date" aria-label="Appeal end" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
          </>
        ) : (
          <label>New value{" "}
            <input aria-label="Appeal value" value={text} onChange={(e) => setText(e.target.value)}
              placeholder={field === "position_size" ? "e.g. 15 for 15%" : field === "horizon_years" ? "e.g. 10" : "e.g. 0.2 for 20%"} />
          </label>
        )}{" "}
        <button type="submit" disabled={busy}>Submit appeal</button>
      </details>
      {error && <p role="alert" data-testid="appeal-error">{error}</p>}
    </form>
  );
}

const FIELD_LABEL: Record<string, string> = {
  position_size: "Size of the position", period: "Period of history used", risk_level: "Risk tolerance", horizon_years: "Horizon (years)",
  max_volatility: "Max volatility", max_drawdown: "Max drawdown", per_asset_cap: "Cap per holding", per_asset_class_caps: "Asset-class caps",
  crypto_cap: "Crypto cap", sector_caps: "Sector caps", esg_exclusions: "ESG exclusions", speculative_limit: "Speculative limit",
};

export interface WhatIf { label: string; detail: string; change: AppealChange }

/** One-click appeals built from the session's own contract and sensitivity results. */
export function whatIfsOf(view: SessionView | null | undefined): WhatIf[] {
  if (!view) return [];
  const c = (view.contract ?? {}) as Record<string, unknown>;
  const out: WhatIf[] = [];
  const p = (x: number) => `${Number((x * 100).toFixed(1))}%`;
  const h = c.horizon_years;
  const years = typeof h === "number" ? h : (h as { max?: number; min?: number } | undefined)?.max ?? (h as { min?: number } | undefined)?.min;
  if (typeof years === "number") {
    const longer = years < 10 ? 10 : years * 2;
    out.push({ label: `What if my horizon were ${longer} years?`, detail: `Now: ${years} years`, change: { field: "horizon_years", value: longer } });
  }
  const size = (view.sensitivity as unknown as { variable?: string; changed?: boolean; threshold?: unknown }[]).find((x) => x.variable === "position_size" && x.changed);
  if (size && typeof size.threshold === "number") {
    out.push({ label: `What if I asked for ${p(size.threshold)}?`, detail: "The size where the answer changes", change: { field: "position_size", value: size.threshold } });
  }
  const bump = (field: string, name: string, cap = 1) => {
    const v = c[field];
    if (typeof v === "number" && v > 0) {
      const next = Math.min(cap, Number((v * 2).toFixed(4)));
      out.push({ label: `What if my ${name} were ${p(next)}?`, detail: `Now: ${p(v)}`, change: { field, value: next } });
    }
  };
  bump("speculative_limit", "speculative limit");
  bump("max_drawdown", "max drawdown");
  if (Array.isArray(c.esg_exclusions) && c.esg_exclusions.includes("fossil_fuel_screen")) {
    out.push({ label: "What if I allowed fossil fuels?", detail: "Now: fossil fuels excluded", change: { field: "esg_exclusions", value: [] } });
  }
  return out.slice(0, 4);
}

const show = (v: unknown) => v === null || v === undefined ? "none" : typeof v === "object" ? JSON.stringify(v) : String(v);

/** Contract fields and Exhibit values that are fractions are read as percentages. */
const FRACTION_FIELDS = new Set(["position_size", "max_volatility", "max_drawdown", "per_asset_cap", "crypto_cap",
  "speculative_limit"]);
const LABELS: Record<string, string> = {
  position_size: "Position size", period: "Period", risk_level: "Risk level", horizon_years: "Horizon (years)",
  max_volatility: "Maximum volatility", max_drawdown: "Maximum drawdown", per_asset_cap: "Cap per holding",
  per_asset_class_caps: "Caps per asset class", crypto_cap: "Crypto cap", sector_caps: "Sector caps",
  esg_exclusions: "ESG exclusions", speculative_limit: "Speculative limit",
};
const VERDICTS: Record<string, string> = {
  accept: "accept", accept_with_conditions: "accept with conditions", reject: "reject",
};
export const label = (field: string) => LABELS[field] ?? field.replace(/_/g, " ");

/** 0.025 -> "2.5%"; other numbers keep two decimals at most. */
export function pct(x: unknown): string {
  if (typeof x !== "number" || !Number.isFinite(x)) return x === null || x === undefined ? "none" : String(x);
  return Math.abs(x) <= 1.5 ? `${(x * 100).toFixed(1)}%` : `${Math.round(x * 100) / 100}`;
}

/** A field value as a person reads it. */
export function fieldValue(field: string, v: unknown): string {
  if (typeof v === "number") return FRACTION_FIELDS.has(field) ? pct(v) : String(v);
  if (Array.isArray(v)) return v.length ? v.join(", ") : "none";
  if (v && typeof v === "object") return Object.entries(v as Record<string, unknown>)
    .map(([k, x]) => `${k} ${typeof x === "number" ? pct(x) : String(x)}`).join(", ");
  return v === null || v === undefined || v === "" ? "none" : String(v).replace(/_/g, " ");
}

/** Exhibit values: numbers as %, one level of nesting as "key value" lists. */
export function exhibitValue(v: unknown): string {
  if (typeof v === "number") return pct(v);
  if (v && typeof v === "object" && !Array.isArray(v)) {
    return Object.entries(v as Record<string, unknown>).map(([k, x]) =>
      x && typeof x === "object" && !Array.isArray(x)
        ? `${k}: ${Object.entries(x as Record<string, unknown>).map(([a, b]) => `${a} ${typeof b === "number" ? pct(b) : String(b)}`).join(", ")}`
        : `${k} ${typeof x === "number" ? pct(x) : String(x)}`).join(" · ");
  }
  return show(v);
}

const verdictText = (v: string | null, w: number | null) =>
  `${v ? VERDICTS[v] ?? v : "none"}${w !== null && w !== undefined ? `, up to ${pct(w)}` : ""}`;

/** One sentence: what the appeal changed in the outcome. */
export function outcomeSentence(o: { verdict: string | null; max_weight: number | null },
                                a: { verdict: string | null; max_weight: number | null }): string {
  if (o.verdict !== a.verdict) return `The verdict changed: ${verdictText(o.verdict, null)} → ${verdictText(a.verdict, null)}.`;
  if (o.max_weight !== a.max_weight) {
    return `Same verdict; the largest lawful size changed from ${pct(o.max_weight)} to ${pct(a.max_weight)}.`;
  }
  return "The verdict did not change.";
}

const MAX_EXHIBITS = 6;

/** Original and Appeal side by side (Req. 30.3). */
export function AppealView({ original, appeal, change }: {
  original: SessionView; appeal: SessionView; change: AppealChange;
}) {
  const d = diffSessions(original, appeal);
  const before = (original.contract as Record<string, unknown> | null)?.[change.field];
  const exhibits = d.exhibits.slice(0, MAX_EXHIBITS);
  return (
    <section aria-label="Appeal comparison" data-testid="appeal-view">
      <h2>Appeal comparison</h2>
      <p data-testid="appeal-change">Changed input: <strong>{label(change.field)}</strong>{" "}
        {before !== undefined && change.field !== "position_size" ? `${fieldValue(change.field, before)} → ` : ""}
        {fieldValue(change.field, change.value)} <small>({change.field})</small></p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        <div data-testid="appeal-original">
          <h3>Original</h3>
          <p>Verdict: {verdictText(d.verdict.original.verdict, d.verdict.original.max_weight)}</p>
        </div>
        <div data-testid="appeal-appeal">
          <h3>Appeal</h3>
          <p>Verdict: {verdictText(d.verdict.appeal.verdict, d.verdict.appeal.max_weight)}</p>
        </div>
      </div>
      <p data-testid="appeal-verdict-changed"><strong>{outcomeSentence(d.verdict.original, d.verdict.appeal)}</strong></p>
      <h3>Hard rules that changed</h3>
      {d.hard_rules.length === 0 ? <p>None.</p> : (
        <ul>{d.hard_rules.map((r) => (
          <li key={r.rule}>{label(r.rule)}: {ruleText(r.original)} → {ruleText(r.appeal)}</li>
        ))}</ul>
      )}
      <h3>Soft preferences that changed</h3>
      {d.soft_preferences.length === 0 ? <p>None.</p> : (
        <ul>{d.soft_preferences.map((p) => <li key={p.preference}>{p.preference}: {show(p.original)} → {show(p.appeal)}</li>)}</ul>
      )}
      <h3>Exhibits whose value changed</h3>
      {d.exhibits.length === 0 ? <p>None.</p> : (
        <ul>{exhibits.map((e) => (
          <li key={`${e.metric}|${e.assets.join(",")}`}>
            {e.metric.replace(/_/g, " ")}: {exhibitValue(e.original.value)} [Exhibit {e.original.number}] → {exhibitValue(e.appeal.value)} [Exhibit {e.appeal.number}]
          </li>
        ))}
        {d.exhibits.length > MAX_EXHIBITS && <li>and {d.exhibits.length - MAX_EXHIBITS} more (see Advanced mode).</li>}
        </ul>
      )}
    </section>
  );
}

/** "fail (30.0% vs limit 5.0%)"; a missing rule reads "not evaluated". */
function ruleText(r: { status: string; observed: number | null; limit: number | null } | null): string {
  if (!r) return "not evaluated";
  const parts = [r.observed !== null ? pct(r.observed) : null, r.limit !== null ? `limit ${pct(r.limit)}` : null]
    .filter(Boolean).join(" vs ");
  return parts ? `${r.status} (${parts})` : r.status;
}
