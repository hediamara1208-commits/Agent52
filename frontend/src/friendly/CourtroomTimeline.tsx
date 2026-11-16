import type { SessionView } from "../model/sessionView";
import { ExhibitLink } from "./ExhibitLinks";

/** Plain names for the Hard_Rules (the investor's limits). */
export const RULE_NAMES: Record<string, string> = {
  per_asset_cap: "cap per holding", per_asset_class_caps: "asset-class caps", sector_caps: "sector caps",
  crypto_cap: "crypto cap", max_volatility: "volatility limit", max_drawdown: "drawdown limit",
  speculative_limit: "speculative limit", esg_exclusions: "ESG exclusion", esg_exclusion: "ESG exclusion",
};
const ruleName = (r: string) => RULE_NAMES[r] ?? r.replace(/_/g, " ");
const pct = (w: number) => `${(w * 100).toFixed(1)}%`;
const list = (xs: string[]) => xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`;

interface Option {
  option_id: string; source: string; ticker: string; weight: number; rejected: boolean;
  failing_rules: string[]; hard_rule_results?: { rule: string; status: string }[];
}
interface Risk { risk: string; option?: string; exhibits?: number[] }
interface RulingShape {
  options?: Option[]; material_risks?: Risk[]; decided_by?: string;
  agents?: { ran?: string[]; failed?: { agent: string; reason?: string }[] | string[] };
}

export interface Step { agent: string; title: string; lines: string[]; exhibits: number[]; note?: string }

/** Who contributed what, from the Ruling and the trace. Pure, so it is tested without rendering. */
export function timelineOf(view: SessionView): Step[] {
  const ruling = (view.ruling ?? null) as unknown as RulingShape | null;
  if (!ruling) return [];
  // A 0% "option" means "do not buy": it is not shown as a size the court weighed.
  const options = (ruling.options ?? []).filter((o) => o.weight > 0);
  const declined = (ruling.options ?? []).some((o) => o.source !== "request" && o.weight <= 0);
  const failed = new Set((ruling.agents?.failed ?? []).map((f) => typeof f === "string" ? f : f.agent));
  const web = new Set(view.exhibits.filter((e) => e.metric === "web_news").map((e) => e.number));
  const label = (o: Option) => o.source === "request" ? `your request (${o.ticker} ${pct(o.weight)})`
    : `${o.ticker} ${pct(o.weight)}`;
  const steps: Step[] = [];

  const request = options.find((o) => o.source === "request");
  const proposed = options.filter((o) => o.source === "advocate");
  steps.push({
    agent: "advocate", title: "The Defense proposed options",
    lines: failed.has("advocate")
      ? ["The Defense could not run; the code added the largest size within your limits."]
      : [proposed.length
          ? `Proposed ${proposed.length} option${proposed.length > 1 ? "s" : ""}: ${list(proposed.map(label))}.`
          : declined ? `Proposed no size above 0% for ${request?.ticker ?? "this asset"}.` : "Proposed no option beyond your request."],
    exhibits: [],
    note: request ? `Your request: ${request.ticker} at ${pct(request.weight)}.` : undefined,
  });

  const risks = ruling.material_risks ?? [];
  const newsRisks = risks.filter((r) => (r.exhibits ?? []).some((n) => web.has(n)));
  steps.push({
    agent: "investigator", title: "The Prosecutor named the risks",
    lines: failed.has("investigator") ? ["The Prosecutor could not run; only the code checks apply."]
      : [`Flagged ${risks.length} risk${risks.length === 1 ? "" : "s"}${newsRisks.length ? `, ${newsRisks.length} citing recent news` : ""}.`,
        ...risks.slice(0, 3).map((r) => r.risk)],
    exhibits: [...new Set(risks.slice(0, 3).flatMap((r) => r.exhibits ?? []))].slice(0, 6),
  });

  const screened = view.trace.filter((e) => e.kind === "judge_check" && e.name === "guidance_only").length;
  steps.push({
    agent: "code", title: "Code checked your limits",
    lines: [
      ...options.map((o) => {
        const total = o.hard_rule_results?.length;
        return o.failing_rules.length
          ? `${label(o)}: breaks the ${list(o.failing_rules.map(ruleName))}.`
          : `${label(o)}: within all ${total ?? ""}${total ? " " : ""}limits.`;
      }),
      ...(screened ? [`${screened} agent statement${screened === 1 ? "" : "s"} screened for buy or sell wording.`] : []),
    ],
    exhibits: [],
  });

  const max = view.verdict?.max_weight ?? null;
  const chosen = max === null ? undefined
    : options.find((o) => !o.rejected && o.source !== "request" && Math.abs(o.weight - max) < 1e-9)
      ?? options.find((o) => !o.rejected && Math.abs(o.weight - max) < 1e-9);
  const byJudge = ruling.decided_by === "judge";
  const verdict = view.verdict?.verdict;
  const reason = (view.verdict as unknown as { reason?: string } | null)?.reason;
  const conditions = (view.verdict as unknown as { conditions?: string[] } | null)?.conditions ?? [];
  steps.push({
    agent: "judge", title: byJudge ? "Judge ruled" : "The code ruled (Judge unavailable)",
    lines: [
      verdict === "reject" ? "Rejected the request: no option fits your limits."
        : chosen ? `Chose ${label(chosen)}${verdict === "accept_with_conditions" ? `, with ${conditions.length} condition${conditions.length === 1 ? "" : "s"}` : ""}.`
        : `Verdict: ${String(verdict ?? "pending").replace(/_/g, " ")}.`,
      ...(reason ? [reason] : []),
    ],
    exhibits: [],
  });
  return steps;
}


/** "How the court decided": the Defense's options, the Prosecutor's risks, the code's checks,
 * the Judge's choice, in that order. Shown once the Ruling is in. */
export function CourtroomTimeline({ view, onOpen }: { view: SessionView; onOpen: (n: number) => void }) {
  const steps = timelineOf(view);
  if (steps.length === 0) return null;
  return (
    <section aria-label="How the court decided" data-testid="court-timeline" className="card timeline">
      <div className="section-title"><h2>How the court decided</h2></div>
      <ol className="timeline-steps">
        {steps.map((s, i) => (
          <li key={s.agent} data-testid={`timeline-${s.agent}`} className={`timeline-step step-${s.agent}`}>
            <span className="timeline-dot" aria-hidden="true">{i + 1}</span>
            <div>
              <h3>{s.title}</h3>
              {s.note && <p className="timeline-note">{s.note}</p>}
              {s.lines.map((l, j) => <p key={j} className={j === 0 ? "timeline-lead" : undefined}>{l}</p>)}
              {s.exhibits.length > 0 && (
                <p className="timeline-exhibits">{s.exhibits.map((n) => <ExhibitLink key={n} number={n} onOpen={onOpen} />)}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
