import { useState } from "react";
import type { SessionView } from "../model/sessionView";
import { ExhibitLink } from "./ExhibitLinks";
import { SPEAKER_NAME, hearingOf, type Speaker } from "./hearing";
import { RULE_NAMES, plain } from "./plain";

type Who = Exclude<Speaker, "objection">;
interface Point { text: string; exhibits: number[] }
interface Part { who: Who; role: string; kind: string; main: string; evidence: Point[]; why: string }

interface Option { source: string; ticker: string; weight: number; failing_rules: string[]; rationale?: string }
interface Risk { risk: string; why_for_this_person?: string; exhibits?: number[] }
interface Fact { text: string; citations?: number[] }
interface RulingShape { options?: Option[]; material_risks?: Risk[]; facts?: Fact[]; assumptions?: string[]; limits?: string[]; what_would_change?: Fact[] }
interface VerdictShape { reason?: string; tension?: string; conditions?: string[]; exhibits?: number[] }

const pct = (w: number) => `${(w * 100).toFixed(1)}%`;
const name = (r: string) => RULE_NAMES[r] ?? r.replace(/_/g, " ");
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** What each member of the court contributed, taken only from what the hearing already produced.
 * No model is called here and nothing is added to what the agents and the calculations said. */
export function argumentsOf(view: SessionView): Part[] {
  const ruling = (view.ruling ?? {}) as unknown as RulingShape;
  const v = (view.verdict ?? {}) as unknown as VerdictShape;
  const said = (who: Who) => hearingOf(view).filter((x) => x.speaker === who).map((x) => plain(x.text));
  const options = (ruling.options ?? []).filter((o) => o.weight > 0);
  const proposed = options.filter((o) => o.source === "advocate");
  const risks = ruling.material_risks ?? [];
  const failing = view.rule_results.filter((r) => r.status === "fail");
  const ruleFacts = (ruling.facts ?? []).filter((f) => /^Rule /.test(f.text));
  const out: Part[] = [];
  const add = (p: Part) => { if (p.main) out.push(p); };

  add({
    who: "advocate", role: "Makes the best case for the investment within your limits.", kind: "AI agent",
    main: said("advocate")[0] ?? "",
    evidence: proposed.map((o) => ({
      text: `${o.ticker} at ${pct(o.weight)}: ${o.failing_rules.length ? `exceeds the ${o.failing_rules.map(name).join(", ")}` : "within every limit"}.`, exhibits: [],
    })),
    why: proposed.some((o) => !o.failing_rules.length)
      ? "At least one proposed size stays within every limit you set, so the Judge has an option that can be accepted."
      : proposed.length ? "None of the proposed sizes stays within every limit you set." : "",
  });
  add({
    who: "investigator", role: "Looks for the risks that matter for this investor.", kind: "AI agent",
    main: risks[0] ? plain(risks[0].risk) : said("investigator")[0] ?? "",
    evidence: risks.map((r, i) => ({ text: i === 0 ? "The calculation behind the main argument." : plain(r.risk), exhibits: (r.exhibits ?? []).slice(0, 3) })),
    why: risks.map((r) => r.why_for_this_person).filter(Boolean).map((t) => plain(String(t))).join(" "),
  });
  add({
    who: "bailiff", role: "Checks the request and every option against your limits.", kind: "Calculation, not an AI agent",
    main: view.rule_results.length
      ? failing.length ? `The request exceeds ${failing.length} of your ${view.rule_results.length} limits: ${failing.map((r) => name(r.rule)).join(", ")}.`
        : `The request stays within all ${view.rule_results.length} of your limits.`
      : "",
    evidence: ruleFacts.map((f) => ({
      text: cap(plain(f.text).replace(/^Rule (.+?): \w+; observed /, "$1: ")), exhibits: (f.citations ?? []).slice(0, 2),
    })),
    why: "Your limits are checked by calculation. No argument from the Defense, the Prosecutor or the Judge can override them.",
  });
  add({
    who: "judge", role: "Weighs both sides against your preferences and rules.", kind: "AI agent",
    main: said("judge")[0] ?? "",
    evidence: [v.tension, v.reason].filter(Boolean).map((t, i) => ({ text: plain(String(t)), exhibits: i === 0 ? (v.exhibits ?? []).slice(0, 3) : [] })),
    why: plain(ruling.what_would_change?.[0]?.text ?? v.conditions?.[0] ?? ""),
  });
  add({
    who: "clerk", role: "Keeps the record: the data used and its limits.", kind: "Calculation, not an AI agent",
    main: view.status === "completed" ? `The record holds ${view.exhibits.length} pieces of evidence. Every number in the ruling points to one of them.` : "",
    evidence: (ruling.assumptions ?? []).slice(0, 3).map((t) => ({ text: plain(t), exhibits: [] })).filter((p) => p.text.trim()),
    why: plain((ruling.limits ?? [])[0] ?? ""),
  });
  return out;
}

/** Optional: pick a member of the court and read its argument, the evidence behind it and why it matters. */
export function TribunalArguments({ view, onOpen }: { view: SessionView; onOpen: (n: number) => void }) {
  const parts = argumentsOf(view);
  const [who, setWho] = useState<Who>("investigator");
  if (!parts.length) return null;
  const p = parts.find((x) => x.who === who) ?? parts[0];
  return (
    <div className="args" data-testid="arguments">
      <div role="tablist" aria-label="Members of the court" className="args-tabs">
        {parts.map((x) => (
          <button key={x.who} type="button" role="tab" aria-selected={x.who === p.who} className={`tab-${x.who}`} onClick={() => setWho(x.who)}>
            {SPEAKER_NAME[x.who]}
          </button>
        ))}
      </div>
      <div role="tabpanel" aria-label={SPEAKER_NAME[p.who]} className={`args-panel panel-${p.who}`}>
        <p className="args-role">{p.role} <span>{p.kind}</span></p>
        <h3>Main argument</h3>
        <p>{p.main}</p>
        {p.evidence.length > 0 && (<>
          <h3>Supporting evidence</h3>
          <ul>{p.evidence.map((e, i) => (
            <li key={i}>{e.text} {e.exhibits.map((n) => <ExhibitLink key={n} number={n} onOpen={onOpen} />)}</li>
          ))}</ul>
        </>)}
        {p.why && (<><h3>Why it matters</h3><p>{p.why}</p></>)}
      </div>
    </div>
  );
}
