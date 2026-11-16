import { useState } from "react";
import type { ContractValues, PersonaEntry } from "./api/client";

export const EMPTY_VALUES: ContractValues = {
  risk_level: "moderate", horizon_min: null, horizon_max: null, max_volatility: null,
  max_drawdown: null, per_asset_cap: null, crypto_cap: null, esg_exclusions: [],
};

const val = (p: PersonaEntry, k: string) => p.contract_values[k]?.value;

/** Pre-fill the form from a Persona_Template (Req. 7.2). */
export function valuesFromPersona(p: PersonaEntry): ContractValues {
  const h = val(p, "horizon_years") ?? p.horizon;
  const hmin = typeof h === "number" ? h : (h as { min?: number } | undefined)?.min ?? null;
  const hmax = typeof h === "number" ? null : (h as { max?: number } | undefined)?.max ?? null;
  const num = (k: string) => (typeof val(p, k) === "number" ? (val(p, k) as number) : null);
  const esg = val(p, "esg_exclusions");
  return {
    risk_level: p.risk_level, horizon_min: hmin, horizon_max: hmax,
    max_volatility: num("max_volatility"), max_drawdown: num("max_drawdown"),
    per_asset_cap: num("per_asset_cap"), crypto_cap: num("crypto_cap"),
    esg_exclusions: Array.isArray(esg) ? esg.map(String) : [],
  };
}

const RISKS: [string, string][] = [
  ["low", "Low: protect what I have"],
  ["low_to_moderate", "Low to moderate: mostly protect, some growth"],
  ["moderate", "Moderate: balance growth and stability"],
  ["high", "High: growth first, I accept large swings"],
  ["very_high", "Very high: maximum growth, very large swings"],
];
const toNum = (s: string) => (s.trim() === "" || Number.isNaN(Number(s)) ? null : Number(s));
export const FOSSIL = "fossil_fuel_screen";

/** ESG choice as the rules read it: only the fossil-fuel screen has sourced data behind it. */
export function esgChoice(values: ContractValues, stated: boolean): "unspecified" | "none" | "fossil" {
  return values.esg_exclusions.includes(FOSSIL) ? "fossil" : stated ? "none" : "unspecified";
}

export function ProfileForm({ values, onChange, fromProfile = false }: {
  values: ContractValues; onChange: (v: ContractValues) => void;
  /** True when the values come from a persona or saved profile (its ESG choice is then stated). */
  fromProfile?: boolean;
}) {
  const [esgTouched, setEsgTouched] = useState(false);
  const set = (patch: Partial<ContractValues>) => onChange({ ...values, ...patch });
  const years = (label: string, key: "horizon_min" | "horizon_max", hint?: string) => (
    <label>{label}{" "}
      <input type="number" min="0" step="1" inputMode="numeric" placeholder={hint} value={values[key] ?? ""}
        onChange={(e) => set({ [key]: toNum(e.target.value) } as Partial<ContractValues>)} />
    </label>
  );
  /** Limits are stored as fractions (0.12) and typed as percentages (12). */
  const percent = (label: string, key: "max_volatility" | "max_drawdown" | "per_asset_cap" | "crypto_cap", help: string) => {
    const v = values[key];
    return (
      <label>{label}{" "}
        <span className="unit-input">
          <input type="number" min="0" max="100" step="any" inputMode="decimal" aria-describedby={`help-${key}`}
            value={v === null || v === undefined ? "" : Number((v * 100).toFixed(4))}
            onChange={(e) => { const n = toNum(e.target.value); set({ [key]: n === null ? null : n / 100 } as Partial<ContractValues>); }} />
          <span aria-hidden="true">%</span>
        </span>
        <small id={`help-${key}`}>{help}</small>
      </label>
    );
  };
  const choice = esgChoice(values, fromProfile || esgTouched);
  const others = values.esg_exclusions.filter((x) => x !== FOSSIL);
  const pickEsg = (c: "unspecified" | "none" | "fossil") => {
    setEsgTouched(c !== "unspecified");
    set({ esg_exclusions: c === "fossil" ? [...others, FOSSIL] : others });
  };
  const ESG: ["unspecified" | "none" | "fossil", string, string][] = [
    ["unspecified", "Not specified yet", "No ESG screen is applied until you choose one."],
    ["none", "No ESG restriction", "Any asset in the list may be considered."],
    ["fossil", "Avoid fossil fuels", "Rejects companies whose main business is oil and gas (in this dataset: Enbridge, Canadian Natural Resources, Exxon Mobil). Funds are not screened."],
  ];
  return (
    <fieldset aria-label="Custom profile" className="profile-form">
      <label className="wide">Risk tolerance{" "}
        <select value={values.risk_level} onChange={(e) => set({ risk_level: e.target.value })}>
          {RISKS.map(([r, text]) => <option key={r} value={r}>{text}</option>)}
        </select>
      </label>
      <p className="field-group wide">When will you need this money?</p>
      {years("From (years)", "horizon_min", "e.g. 3")}
      {years("To (years)", "horizon_max", "optional")}
      <p className="field-group wide">Your limits</p>
      {percent("Max volatility", "max_volatility", "Largest yearly ups and downs you accept for the whole portfolio.")}
      {percent("Max drawdown", "max_drawdown", "Largest fall from a high point you accept.")}
      <details className="wide more-limits">
        <summary>More limits</summary>
        <div className="two">
          {percent("Per-asset cap", "per_asset_cap", "Most you want in any single holding.")}
          {percent("Crypto cap", "crypto_cap", "Most you want in crypto, in total.")}
        </div>
      </details>
      <div className="wide esg" role="radiogroup" aria-label="ESG preference">
        <p className="field-group">Values-based exclusions (ESG)</p>
        {ESG.map(([c, title, help]) => (
          <label key={c} className={`choice${choice === c ? " on" : ""}`}>
            <input type="radio" name="esg" checked={choice === c} onChange={() => pickEsg(c)} />
            <span><b>{title}</b><small>{help}</small></span>
          </label>
        ))}
        {others.length > 0 && <small>Also on this profile: {others.join(", ")} (no data behind these; they are recorded but not checked).</small>}
        <small>Other screens such as tobacco or weapons are not offered: this project has no sourced data for them.</small>
      </div>
    </fieldset>
  );
}

export type Holdings = { ok: true; value: Record<string, number> | null } | { ok: false; error: string };

/** "XIU.TO 40, RY.TO 15, XBB.TO 45" (or "XIU.TO: 0.4; ...") -> {ticker: weight in percent}.
 * Empty text means "use the persona's portfolio". The server checks tickers against the universe. */
export function parseHoldings(text: string): Holdings {
  const parts = text.split(/[,;\n]+/).map((s) => s.trim()).filter(Boolean);
  if (parts.length === 0) return { ok: true, value: null };
  const out: Record<string, number> = {};
  for (const part of parts) {
    const m = part.match(/^([A-Za-z][A-Za-z0-9.\-]*)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*%?$/);
    if (!m) return { ok: false, error: `Could not read "${part}". Write a ticker then a weight, e.g. XIU.TO 40.` };
    const ticker = m[1].toUpperCase();
    if (ticker in out) return { ok: false, error: `${ticker} appears twice.` };
    out[ticker] = Number(m[2]);
  }
  const total = Object.values(out).reduce((a, b) => a + b, 0);
  const pct = total > 1.5 ? total : total * 100;
  if (Math.abs(pct - 100) > 1) return { ok: false, error: `Weights must add up to 100% (they add up to ${pct.toFixed(1)}%).` };
  return { ok: true, value: out };
}

/** Optional current holdings; without them the persona's own Base_Portfolio is used. */
export function HoldingsField({ text, onChange }: { text: string; onChange: (t: string) => void }) {
  const parsed = parseHoldings(text);
  return (
    <label>What you hold today (optional){" "}
      <input value={text} placeholder="e.g. XIU.TO 40, RY.TO 15, TD.TO 10, ENB.TO 10, XBB.TO 25"
        aria-invalid={!parsed.ok} aria-describedby="holdings-help" onChange={(e) => onChange(e.target.value)} />
      <small id="holdings-help" role={parsed.ok ? undefined : "alert"}>
        {parsed.ok ? "Leave empty to use the persona's portfolio. Weights in %, adding up to 100." : parsed.error}
      </small>
    </label>
  );
}
