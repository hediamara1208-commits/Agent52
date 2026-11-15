import type { SensitivityResult } from "../model/sessionView";

/** Sensitivity_Analysis results (Req. 7.6). */
export function SensitivityPanel({ results, onExhibit }: {
  results: SensitivityResult[]; onExhibit: (n: number) => void;
}) {
  return (
    <section aria-label="Sensitivity">
      <h2>Sensitivity analysis</h2>
      {results.length === 0 ? <p>No sensitivity results.</p> : (
        <ul>
          {results.map((s) => (
            <li key={s.variable} data-testid={`sensitivity-${s.variable}`}>
              <strong>{s.variable}</strong>: {s.changed
                ? `verdict changes from ${s.baseline_verdict ?? "baseline"} to ${s.verdict_at_threshold ?? "unknown"}${s.threshold != null ? ` at ${s.threshold}` : ""}`
                : "verdict does not change"}
              {s.text ? ` (${s.text})` : ""}{" "}
              <button type="button" className="exhibit-link" onClick={() => onExhibit(s.exhibit)}>[Exhibit {s.exhibit}]</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
