import type { SensitivityResult } from "../model/sessionView";
import { plain } from "../friendly/VerdictPanel";

const fmt = (t: SensitivityResult["threshold"]) =>
  typeof t === "number" ? (Math.abs(t) <= 1.5 ? `${(t * 100).toFixed(1)}%` : String(t)) : t ?? "";

/** Sensitivity_Analysis: where the verdict flips (Req. 7.6). */
export function SensitivityPanel({ results, onExhibit }: {
  results: SensitivityResult[]; onExhibit: (n: number) => void;
}) {
  return (
    <section aria-label="Sensitivity">
      <div className="section-title"><h2>What would change the decision</h2></div>
      {results.length === 0 ? <p style={{ color: "var(--muted)" }}>No sensitivity results.</p> : (
        <ul className="sens-list">
          {results.map((s) => (
            <li key={s.variable} data-testid={`sensitivity-${s.variable}`} data-changed={s.changed}>
              <strong>{s.variable.replace(/^contract\./, "").replace(/_/g, " ")}</strong>{" "}
              {s.changed ? (
                <span>
                  {(s.baseline_verdict ?? "baseline").replace(/_/g, " ")} <span className="arrow">→</span> {(s.verdict_at_threshold ?? "unknown").replace(/_/g, " ")}
                  {s.threshold != null ? <> at <code>{fmt(s.threshold)}</code></> : null}
                </span>
              ) : <span style={{ color: "var(--muted)" }}>verdict does not change</span>}{" "}
              <button type="button" className="exhibit-link" onClick={() => onExhibit(s.exhibit)}>[Exhibit {s.exhibit}]</button>
              {s.text ? <div style={{ color: "var(--muted)", fontSize: ".78rem", marginTop: ".25rem" }}>{plain(s.text)}</div> : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
