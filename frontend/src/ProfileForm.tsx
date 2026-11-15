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

const RISKS = ["low", "low_to_moderate", "moderate", "high", "very_high"];
const toNum = (s: string) => (s.trim() === "" || Number.isNaN(Number(s)) ? null : Number(s));

export function ProfileForm({ values, onChange }: { values: ContractValues; onChange: (v: ContractValues) => void }) {
  const set = (patch: Partial<ContractValues>) => onChange({ ...values, ...patch });
  const numField = (label: string, key: keyof ContractValues) => (
    <label>{label}{" "}
      <input type="number" step="any" value={(values[key] as number | null) ?? ""}
        onChange={(e) => set({ [key]: toNum(e.target.value) } as Partial<ContractValues>)} />
    </label>
  );
  return (
    <fieldset aria-label="Custom profile">
      <label>Risk level{" "}
        <select value={values.risk_level} onChange={(e) => set({ risk_level: e.target.value })}>
          {RISKS.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </label>
      {numField("Horizon min (years)", "horizon_min")}
      {numField("Horizon max (years)", "horizon_max")}
      {numField("Max volatility", "max_volatility")}
      {numField("Max drawdown", "max_drawdown")}
      {numField("Per-asset cap", "per_asset_cap")}
      {numField("Crypto cap", "crypto_cap")}
      <label>ESG exclusions (comma separated){" "}
        <input value={values.esg_exclusions.join(", ")}
          onChange={(e) => set({ esg_exclusions: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
      </label>
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
    <label>Current holdings (optional){" "}
      <input value={text} placeholder="e.g. XIU.TO 40, RY.TO 15, TD.TO 10, ENB.TO 10, XBB.TO 25"
        aria-invalid={!parsed.ok} aria-describedby="holdings-help" onChange={(e) => onChange(e.target.value)} />
      <small id="holdings-help" role={parsed.ok ? undefined : "alert"}>
        {parsed.ok ? "Leave empty to use the persona's portfolio. Weights in %, adding up to 100." : parsed.error}
      </small>
    </label>
  );
}
