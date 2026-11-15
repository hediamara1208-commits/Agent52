import { useEffect, useState } from "react";
import type { SessionView } from "../model/sessionView";
import { RULE_NAMES } from "./CourtroomTimeline";

/** The five steps a session goes through, in order. */
export const STEPS = ["Limits", "Advocate", "Investigator", "Judge", "Clerk"] as const;
/** Typical length of a live session (benchmark median ~70 s). */
export const TYPICAL_SECONDS = 70;

const list = (xs: string[]) => xs.length <= 1 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`;
const ruleName = (r: string) => RULE_NAMES[r] ?? r.replace(/_/g, " ");

function dateOf(iso: string | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso);
  return Number.isNaN(d.getTime()) ? null
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
}

export interface Progress { step: number; current: string; done: string[] }

/** What the tribunal is doing now and what is already done. The view is republished at each
 * stage boundary (orchestrator.publish), so this reads only fields that arrive with those. */
export function progressOf(view: SessionView): Progress {
  const done: string[] = [];
  const finished = new Set(view.stages_done);
  const snapDate = dateOf(view.snapshot?.coverage_end);
  if (finished.has("snapshot") && snapDate) done.push(`Market data pinned: prices up to ${snapDate}.`);

  if (finished.has("request_rules") && view.rule_results.length) {
    const failing = view.rule_results.filter((r) => r.status === "fail").map((r) => ruleName(r.rule));
    done.push(failing.length
      ? `Your request checked against ${view.rule_results.length} limits: it breaks the ${list(failing)}.`
      : `Your request checked against ${view.rule_results.length} limits: it passes all of them.`);
  }
  if (finished.has("advocate")) {
    const news = view.exhibits.filter((e) => e.metric === "web_news").length;
    if (news) done.push(`${news} recent news article${news === 1 ? "" : "s"} found for the court.`);
    const tools = view.trace.filter((e) => e.kind === "tool_call").length;
    if (tools) done.push(`${tools} portfolio comparison${tools === 1 ? "" : "s"} computed from the price history.`);
    done.push("The Advocate proposed its options.");
  }
  if (finished.has("option_rules")) {
    const batches = view.trace.filter((e) => e.kind === "judge_check" && e.name === "per_asset_cap").length;
    const options = Math.max(0, batches - 1);
    if (options) done.push(`Each of the ${options} option${options === 1 ? "" : "s"} checked against your limits.`);
  }
  if (finished.has("investigator")) done.push("The Investigator named the risks.");
  if (finished.has("judge")) done.push("The Judge ruled.");

  let step = 0;
  let current = "Pinning the market data and checking your request against your limits…";
  if (finished.has("judge")) { step = 4; current = "The Clerk is checking every number against its Exhibit and writing the ruling…"; }
  else if (finished.has("investigator")) { step = 3; current = "The Judge is weighing your preferences against the rules…"; }
  else if (finished.has("option_rules")) { step = 2; current = "The Investigator is naming the risks that matter for you…"; }
  else if (finished.has("advocate")) { step = 1; current = "The code is checking each option against your limits…"; }
  else if (finished.has("request_rules")) { step = 1; current = "The Advocate is reading recent news and building options that serve your goal…"; }
  return { step, current, done };
}

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** Shown while a session runs: elapsed time, the five steps, and what is already done. */
export function LiveProgress({ view, now = () => Date.now() }: { view: SessionView; now?: () => number }) {
  const [start] = useState(now);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed(Math.floor((now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, [now, start]);
  if (view.status !== "running") return null;
  const { step, current, done } = progressOf(view);
  const over = elapsed > TYPICAL_SECONDS + 20;
  return (
    <section aria-label="Session progress" aria-live="polite" data-testid="live-progress" className="card live-progress">
      <div className="live-head">
        <strong>In session</strong>
        <span data-testid="live-clock">{clock(elapsed)} · {over ? "taking longer than usual" : `usually about ${clock(TYPICAL_SECONDS)}`}</span>
      </div>
      <ol className="live-steps">
        {STEPS.map((s, i) => (
          <li key={s} data-state={i < step ? "done" : i === step ? "active" : "pending"}>{s}</li>
        ))}
      </ol>
      <p className="live-current" data-testid="live-current">{current}</p>
      {done.length > 0 && (
        <ul className="live-done" data-testid="live-done">
          {done.map((d) => <li key={d}>{d}</li>)}
        </ul>
      )}
    </section>
  );
}
