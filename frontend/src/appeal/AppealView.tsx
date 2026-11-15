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

/** Original and Appeal side by side (Req. 30.3). */
export function AppealView({ original, appeal, change }: {
  original: SessionView; appeal: SessionView; change: AppealChange;
}) {
  const d = diffSessions(original, appeal);
  return (
    <section aria-label="Appeal comparison" data-testid="appeal-view">
      <h2>Appeal comparison</h2>
      <p data-testid="appeal-change">Changed input: <strong>{change.field}</strong> = {show(change.value)}</p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        <div data-testid="appeal-original">
          <h3>Original</h3>
          <p>Verdict: {show(d.verdict.original.verdict)} (max weight {show(d.verdict.original.max_weight)})</p>
        </div>
        <div data-testid="appeal-appeal">
          <h3>Appeal</h3>
          <p>Verdict: {show(d.verdict.appeal.verdict)} (max weight {show(d.verdict.appeal.max_weight)})</p>
        </div>
      </div>
      <p data-testid="appeal-verdict-changed">{d.verdict.changed ? "The verdict changed." : "The verdict did not change."}</p>
      <h3>Hard rules that changed</h3>
      {d.hard_rules.length === 0 ? <p>None.</p> : (
        <ul>{d.hard_rules.map((r) => (
          <li key={r.rule}>{r.rule}: {show(r.original?.status)} (observed {show(r.original?.observed)}) → {show(r.appeal?.status)} (observed {show(r.appeal?.observed)})</li>
        ))}</ul>
      )}
      <h3>Soft preferences that changed</h3>
      {d.soft_preferences.length === 0 ? <p>None.</p> : (
        <ul>{d.soft_preferences.map((p) => <li key={p.preference}>{p.preference}: {show(p.original)} → {show(p.appeal)}</li>)}</ul>
      )}
      <h3>Exhibits whose value changed</h3>
      {d.exhibits.length === 0 ? <p>None.</p> : (
        <ul>{d.exhibits.map((e) => (
          <li key={`${e.metric}|${e.assets.join(",")}`}>
            {e.metric}{e.assets.length ? ` (${e.assets.join(", ")})` : ""}: {show(e.original.value)} [Exhibit {e.original.number}] → {show(e.appeal.value)} [Exhibit {e.appeal.number}]
          </li>
        ))}</ul>
      )}
    </section>
  );
}
