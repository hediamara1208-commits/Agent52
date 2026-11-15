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

const RISKS = ["low", "low_to_moderate", "moderate", "high"];
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
