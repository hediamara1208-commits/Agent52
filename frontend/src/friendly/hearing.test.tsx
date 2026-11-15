import { render, screen, act, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { Courtroom, hearingOf, trimSpeech, exhibitsIn } from "./index";
import type { SessionView } from "../model/sessionView";

const rules = ["per_asset_cap", "crypto_cap", "max_volatility", "max_drawdown", "speculative_limit", "sector_caps", "per_asset_class_caps"];
const res = (fail: string[]) => rules.map((rule) => ({ rule, status: fail.includes(rule) ? "fail" : "pass" }));

// Shape of the live Robert / 30% TSLA session.
const live = {
  session_id: "s1", status: "completed", contract: null, stage: "clerk",
  stages_done: ["snapshot", "profiler", "request_rules", "advocate", "option_rules", "investigator", "judge", "clerk"],
  active_agent: null, exhibits: [], sensitivity: [], snapshot: null, data_notices: [], error: null,
  rule_results: res(["per_asset_cap", "max_volatility", "max_drawdown", "speculative_limit"]),
  summaries: { advocate: "The Advocate sees the goal as: Robert wants some Tesla growth while keeping his savings safe. It proposes 2 options for the court.",
    investigator: "The Investigator names 13 material risks across 4 options." },
  trace: [
    { seq: 1, kind: "claim_removed", name: "judge", summary: { claim: "Tesla will double next year." } },
    { seq: 2, kind: "judge_check", name: "judge_ruling", summary: { inputs: "{\"attempt\": 2}", result: "ok" } },
  ],
  verdict: { verdict: "accept_with_conditions", max_weight: 0.05, failing_rules: [], exhibits: [],
    reason: "The 30.0% request fails four rules, including 20.1% volatility against a 12.0% limit (Exhibit 10).",
    conditions: ["The user may wish to review the position after six months."] },
  ruling: {
    verdict: "accept_with_conditions", facts: [], disclaimers: [], what_would_change: [], decided_by: "judge",
    options: [
      { option_id: "request", source: "request", ticker: "TSLA", weight: 0.3, rejected: true, failing_rules: ["per_asset_cap", "max_volatility", "max_drawdown", "speculative_limit"] },
      { option_id: "option_1", source: "advocate", ticker: "TSLA", weight: 0.05, rejected: false, failing_rules: [], rationale: "A small position gives exposure without breaking his limits." },
      { option_id: "option_2", source: "advocate", ticker: "TSLA", weight: 0.025, rejected: false, failing_rules: [] },
      { option_id: "option_3", source: "advocate", ticker: "TSLA", weight: 0, rejected: false, failing_rules: [] },
    ],
    material_risks: [
      { risk: "Tesla dominates portfolio risk", why_for_this_person: "Robert retires in 3 to 5 years", exhibits: [2] },
      { risk: "Volatility above the limit", exhibits: [10] },
      { risk: "Third risk not read aloud", exhibits: [11] },
    ],
  },
} as unknown as SessionView;

describe("the hearing (speeches built from the session's outputs, no model call)", () => {
  afterEach(() => vi.useRealTimers());

  it("gives the floor in court order with the live content", () => {
    const h = hearingOf(live);
    expect(h.map((s) => s.speaker)).toEqual(["bailiff", "advocate", "investigator", "bailiff", "objection", "objection", "judge", "clerk"]);
    expect(h[0].text).toBe("All rise. The court will hear TSLA at 30.0%. It breaks 4 of the investor's 7 limits: the cap per holding, volatility limit, drawdown limit and speculative limit.");
    expect(h[1].text).toContain("The investor's goal: Robert wants some Tesla growth while keeping his savings safe.");
    expect(h[1].text).toContain("I propose TSLA at 5.0% and TSLA at 2.5%.");
    expect(h[2].text).toBe("Tesla dominates portfolio risk: Robert retires in 3 to 5 years. Volatility above the limit.");
    expect(h[2].exhibits).toEqual([2, 10]);
    expect(h[3].text).toBe("5.0% and 2.5% fit within every limit.");
    expect(h[4].struck).toBe("Tesla will double next year.");
    expect(h[5].text).toContain("the Judge rules again");
    expect(h[6].text).toContain("The request is accepted with conditions at 5.0%.");
    expect(h[6].text).toContain("Condition: review the position after six months.");
    expect(h[6].exhibits).toEqual([10]);
    expect(h[7].text).toContain("simulation, not financial advice");
  });

  it("builds only what has arrived while the court sits", () => {
    const running = { ...live, status: "running", stages_done: ["snapshot", "profiler", "request_rules"], ruling: null, verdict: null, trace: [] } as unknown as SessionView;
    const h = hearingOf(running);
    expect(h.map((s) => s.speaker)).toEqual(["bailiff"]);
    expect(h[0].text).toContain("The court will hear the request.");
    const later = hearingOf({ ...running, stages_done: [...running.stages_done, "advocate", "option_rules", "investigator"] } as SessionView);
    expect(later[1].text).toBe("The investor's goal: Robert wants some Tesla growth while keeping his savings safe. I propose 2 options to the court.");
    expect(later[2].text).toBe("The Investigator names 13 material risks across 4 options.");
  });

  it("trims long speeches at a sentence and finds cited Exhibits", () => {
    const long = Array.from({ length: 12 }, (_, i) => `Sentence number ${i} has six words.`).join(" ");
    expect(trimSpeech(long).split(" ").length).toBeLessThanOrEqual(45);
    expect(exhibitsIn("See Exhibits 6 and 19, and (Exhibit 11).")).toEqual([6, 19, 11]);
  });

  it("types each speech, opens its Exhibits, and offers a replay at the end", () => {
    vi.useFakeTimers();
    const onOpen = vi.fn();
    render(<Courtroom view={live} onOpen={onOpen} />);
    expect(screen.getByTestId("speech-bubble")).toHaveTextContent("Bailiff");
    for (let i = 0; i < 2000; i++) act(() => { vi.advanceTimersByTime(100); });
    expect(screen.getByTestId("speech-bubble")).toHaveTextContent("So ordered.");
    expect(screen.getByTestId("replay")).toHaveTextContent("Replay the hearing");
    expect(screen.getByTestId("seat-clerk")).toHaveAttribute("data-active", "true");
    fireEvent.click(screen.getAllByRole("button", { name: "[Exhibit 10]" })[0]);
    expect(onOpen).toHaveBeenCalledWith(10);
  });
});

describe("court voices", () => {
  it("synthesises each speech once and plays it", async () => {
    const { createVoice } = await import("./voices");
    const synth = vi.fn(async () => ({ audio: "SUQz", content_type: "audio/mpeg" }));
    const played: string[] = [];
    const fakeAudio = (src: string) => {
      const a = { onended: null as null | (() => void), onerror: null, pause: () => undefined,
        play: () => { played.push(src); setTimeout(() => a.onended?.(), 0); return Promise.resolve(); } };
      return a as unknown as HTMLAudioElement;
    };
    const speak = createVoice(synth, fakeAudio);
    const s = { id: "j", speaker: "judge" as const, text: "So ordered.", exhibits: [] };
    await speak(s); await speak(s);
    expect(synth).toHaveBeenCalledTimes(1);
    expect(synth).toHaveBeenCalledWith("judge", "So ordered.");
    expect(played).toEqual(["data:audio/mpeg;base64,SUQz", "data:audio/mpeg;base64,SUQz"]);
  });
});
