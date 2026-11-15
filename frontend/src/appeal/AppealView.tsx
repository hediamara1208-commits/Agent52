import { useState } from "react";
import type { SessionView } from "../model/sessionView";
import { diffSessions } from "./diff";

export interface AppealChange { field: string; value: unknown }

export const APPEAL_FIELDS = [
  "position_size", "period", "risk_level", "horizon_years", "max_volatility", "max_drawdown",
  "per_asset_cap", "per_asset_class_caps", "crypto_cap", "sector_caps", "esg_exclusions", "speculative_limit",
] as const;

/** Appeal control: changes exactly one input (Req. 30.1). */
export function AppealControl({ busy, onSubmit }: { busy: boolean; onSubmit: (c: AppealChange) => void }) {
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
    <form aria-label="Appeal" onSubmit={submit}>
      <h2>Appeal</h2>
      <p>Change one input and re-run the tribunal. The original session stays as it is.</p>
      <label>Input to change{" "}
        <select aria-label="Appeal field" value={field} onChange={(e) => setField(e.target.value)}>
          {APPEAL_FIELDS.map((f) => <option key={f} value={f}>{f}</option>)}
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
            placeholder={field === "position_size" ? "e.g. 0.15 or 15" : "e.g. 0.2"} />
        </label>
      )}{" "}
      <button type="submit" disabled={busy}>Submit appeal</button>
      {error && <p role="alert" data-testid="appeal-error">{error}</p>}
    </form>
  );
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
