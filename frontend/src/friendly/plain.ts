// Words the investor reads. The agents and the trace use internal names; nothing here changes content.
export const RULE_NAMES: Record<string, string> = {
  per_asset_cap: "cap per holding", per_asset_class_caps: "asset-class caps", sector_caps: "sector caps",
  crypto_cap: "crypto cap", max_volatility: "volatility limit", max_drawdown: "drawdown limit",
  speculative_limit: "speculative limit", esg_exclusions: "ESG exclusion", esg_exclusion: "ESG exclusion",
};

/** Internal rule names never reach the investor: "per_asset_cap" reads "cap per holding". */
export function plain(text: string): string {
  let out = text
    .replace(/Tables used:[^.]*\./g, "Sources: daily market prices (Yahoo Finance) and the Bank of Canada USD/CAD rate.")
    .replace(/Snapshot_Id\s+\S+?,?\s*retrieved\s+([\d-]+)\.?/g, "Data retrieved $1.").replace(/Snapshot_Id\s+\S+/g, "")
    .replace(/\b[a-z_]+@\d{8}T\d{6}Z[\w-]*/g, "market data").replace(/\bthe Dataset\b/g, "the dataset").replace(/\bDataset\b/g, "dataset")
    .replace(/\bExhibits?\b(?! \d)/g, (m) => (m.endsWith("s") ? "evidence items" : "evidence item"))
    .replace(/;?\s*failing rules?:[^.]*\.?/gi, ".").replace(/Hard_Rules?/g, (m) => (m.endsWith("s") ? "limits" : "limit"))
    .replace(/Soft_Preferences?/g, "preference").replace(/Base_Portfolio/g, "current portfolio").replace(/\bVerdict\b/g, "verdict");
  for (const [id, name] of Object.entries(RULE_NAMES)) out = out.split(id).join(name);
  return out.replace(/\boption_(\d+)\b/g, "option $1").replace(/\.\./g, ".").replace(/\bAdvocate\b/g, "Defense").replace(/\bInvestigator\b/g, "Prosecutor");
}
