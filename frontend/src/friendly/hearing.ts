import type { SessionView } from "../model/sessionView";
import { RULE_NAMES } from "./CourtroomTimeline";

/** Who can take the floor. The Bailiff and the Clerk are code; the others are agents. */
export type Speaker = "bailiff" | "advocate" | "investigator" | "judge" | "clerk" | "objection";

export interface Speech {
  id: string;
  speaker: Speaker;
  text: string;
  exhibits: number[];
  /** A claim the citation validator struck from the record (shown struck through). */
  struck?: string;
}

export const SPEAKER_NAME: Record<Speaker, string> = {
  bailiff: "Bailiff", advocate: "Advocate", investigator: "Investigator",
  judge: "Judge", clerk: "Clerk", objection: "Objection",
};

const pct = (w: number) => `${(w * 100).toFixed(1)}%`;
const ruleName = (r: string) => RULE_NAMES[r] ?? r.replace(/_/g, " ");
const list = (xs: string[]) => xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`;

/** Keep a speech short enough to read aloud: whole sentences, at most `max` words. */
export function trimSpeech(text: string, max = 45): string {
  const clean = text.replace(/\s+/g, " ").trim();
  // Split at a full stop followed by a space and a capital, never inside "30.0%".
  const sentences = clean.split(/(?<=[.!?])\s+(?=[A-Z"(])/).map((x) => `${x} `);
  let out = "";
  for (const s of sentences) {
    const next = (out + s).trim();
    if (out && next.split(" ").length > max) break;
    out = next + " ";
  }
  out = out.trim() || clean;
  const words = out.split(" ");
  return words.length > max + 10 ? `${words.slice(0, max).join(" ")}…` : out;
}

/** Exhibit numbers cited in a text: "Exhibit 10", "Exhibits 6 and 19", "(Exhibits 11, 12)". */
export function exhibitsIn(text: string): number[] {
  const out: number[] = [];
  for (const m of text.matchAll(/Exhibits?\s+((?:\d+(?:\s*(?:,|and|&)\s*)?)+)/gi)) {
    for (const n of m[1].match(/\d+/g) ?? []) out.push(Number(n));
  }
  return [...new Set(out)];
}

interface Option { option_id: string; source: string; ticker: string; weight: number; rejected: boolean; failing_rules: string[]; rationale?: string }
interface Risk { risk: string; why_for_this_person?: string; exhibits?: number[] }
interface RulingShape { options?: Option[]; material_risks?: Risk[]; decided_by?: string }
interface VerdictShape { verdict?: string; max_weight?: number | null; reason?: string; conditions?: string[] }

const VERDICT_WORDS: Record<string, string> = {
  accept: "The request is accepted",
  accept_with_conditions: "The request is accepted with conditions",
  reject: "The request is rejected",
};

/** The hearing, in order, built only from what the session already produced (no model call).
 * While the session runs, speeches appear as their stage's data arrives. */
export function hearingOf(view: SessionView): Speech[] {
  const out: Speech[] = [];
  const done = new Set(view.stages_done);
  const ruling = (view.ruling ?? null) as unknown as RulingShape | null;
  const options = (ruling?.options ?? []).filter((o) => o.weight > 0);
  const request = options.find((o) => o.source === "request");
  const say = (speaker: Speaker, text: string, exhibits: number[] = [], extra: Partial<Speech> = {}) =>
    out.push({ id: `${speaker}-${out.length}`, speaker, text: trimSpeech(text), exhibits: [...new Set([...exhibits, ...exhibitsIn(text)])].slice(0, 4), ...extra });

  // 1. Bailiff opens and reads the request against the investor's limits (code).
  if (done.has("request_rules") || view.rule_results.length) {
    const failing = view.rule_results.filter((r) => r.status === "fail").map((r) => ruleName(r.rule));
    const asked = request ? `${request.ticker} at ${pct(request.weight)}` : "the request";
    say("bailiff", `All rise. The court will hear ${asked}. ` + (failing.length
      ? `It breaks ${failing.length} of the investor's ${view.rule_results.length} limits: the ${list(failing)}.`
      : `It stays within all ${view.rule_results.length} of the investor's limits.`));
  }

  // 2. Advocate: the goal, then the sizes it pleads for.
  if (done.has("advocate")) {
    const proposed = options.filter((o) => o.source === "advocate");
    const goal = (view.summaries.advocate ?? "").replace(/^The Advocate sees the goal as:\s*/i, "")
      .split(/(?<=\.)\s/)[0];
    const plea = proposed.length
      ? `I propose ${list(proposed.map((o) => `${o.ticker} at ${pct(o.weight)}`))}. ${proposed[0].rationale ?? ""}`
      : view.summaries.advocate ?? "";
    say("advocate", `${goal ? `The investor's goal: ${goal} ` : ""}${plea}`);
  }

  // 3. Investigator: the two risks that matter most for this person.
  if (done.has("investigator")) {
    const risks = ruling?.material_risks ?? [];
    if (risks.length) {
      const top = risks.slice(0, 2);
      say("investigator",
        top.map((r) => `${r.risk.replace(/\.$/, "")}${r.why_for_this_person ? `: ${r.why_for_this_person.replace(/\.$/, "")}` : ""}.`).join(" "),
        top.flatMap((r) => r.exhibits ?? []));
    } else if (view.summaries.investigator) {
      say("investigator", view.summaries.investigator);
    }
  }

  // 4. Bailiff re-checks every option (code).
  if (ruling && options.some((o) => o.source !== "request")) {
    const fits = options.filter((o) => o.source !== "request" && !o.failing_rules.length);
    const fails = options.filter((o) => o.source !== "request" && o.failing_rules.length);
    say("bailiff", [
      fits.length ? `${list(fits.map((o) => pct(o.weight)))} fit${fits.length === 1 ? "s" : ""} within every limit.` : "",
      fails.length ? `${list(fails.map((o) => pct(o.weight)))} break${fails.length === 1 ? "s" : ""} the ${list([...new Set(fails.flatMap((o) => o.failing_rules.map(ruleName)))])}.` : "",
    ].join(" ").trim());
  }

  // 5. Objections: claims struck by the citation validator, and Judge send-backs (code).
  for (const e of view.trace) {
    if (e.kind === "claim_removed") {
      const claim = String((e.summary as { claim?: string } | undefined)?.claim ?? "");
      say("objection", "Objection sustained. A statement without an Exhibit behind it is struck from the record.", [], { struck: claim || undefined });
    } else if (e.kind === "judge_check" && e.name === "judge_ruling") {
      const inputs = String((e.summary as { inputs?: string } | undefined)?.inputs ?? "");
      const attempt = Number(/"attempt":\s*(\d+)/.exec(inputs)?.[1] ?? 1);
      if (attempt > 1) say("objection", "Objection sustained. The Judge's first ruling did not hold against the law; the Judge rules again.");
    }
  }

  // 6. Judge: verdict, size, reason, conditions.
  const v = (view.verdict ?? null) as unknown as VerdictShape | null;
  if (done.has("judge") && v?.verdict) {
    const size = v.verdict !== "reject" && typeof v.max_weight === "number" ? ` at ${pct(v.max_weight)}` : "";
    const conds = v.conditions?.length ? ` Condition: ${v.conditions[0].replace(/^The user may wish to /i, "").replace(/\.$/, "")}.` : "";
    say("judge", `${VERDICT_WORDS[v.verdict] ?? v.verdict}${size}. ${v.reason ?? ""}${conds}`);
  }

  // 7. Clerk closes (code).
  if (view.status === "completed") {
    say("clerk", ruling?.decided_by === "code"
      ? "So ordered by the code, because the Judge was unavailable. Every number is backed by an Exhibit. This is a simulation, not financial advice."
      : "So ordered. Every number in this ruling is backed by an Exhibit. This is a simulation, not financial advice.");
  }
  return out;
}
