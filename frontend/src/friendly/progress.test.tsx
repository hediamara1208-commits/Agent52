import { fireEvent, render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { FriendlyMode, progressOf, LiveProgress } from "./index";
import type { SessionView } from "../model/sessionView";

const rule = (rule: string, status: "pass" | "fail") => ({ rule, status });
const base = {
  session_id: "s1", status: "running", contract: null, stage: "snapshot", stages_done: ["snapshot"],
  active_agent: null, exhibits: [], rule_results: [], sensitivity: [], trace: [], summaries: {},
  snapshot: { snapshot_id: "x", source: "s3", retrieved_at: "2026-11-13T00:00:00Z", coverage_end: "2026-11-12",
    served_from: "primary", fallback_cause: null },
  data_notices: [], error: null, verdict: null, ruling: null,
} as unknown as SessionView;
const at = (stages: string[], extra: Partial<SessionView> = {}) =>
  ({ ...base, stage: stages[stages.length - 1], stages_done: stages, ...extra }) as SessionView;
const check = (name: string) => ({ seq: 0, kind: "judge_check", name });

// The order of published views seen on a live Robert / 30% TSLA session.
const S = ["snapshot", "profiler", "request_rules"];

describe("live progress (what the tribunal is doing while you wait)", () => {
  afterEach(() => vi.useRealTimers());

  it("starts with the limits check and the pinned data date", () => {
    const p = progressOf(base);
    expect(p.step).toBe(0);
    expect(p.done).toEqual(["Market prices loaded, up to Nov 12, 2026."]);
  });

  it("names the broken limits once the request is checked, then shows the Defense at work", () => {
    const v = at(S, { active_agent: "advocate", rule_results: [rule("per_asset_cap", "fail"), rule("crypto_cap", "pass"), rule("max_volatility", "fail")] as never });
    const p = progressOf(v);
    expect(p.step).toBe(1);
    expect(p.current).toMatch(/Defense is reading recent news/);
    expect(p.done[1]).toBe("Your request checked against 3 limits: it breaks the cap per holding and volatility limit.");
  });

  it("counts news, comparisons and options as the stages finish", () => {
    const v = at([...S, "advocate", "option_rules"], {
      active_agent: "investigator",
      exhibits: [{ number: 16, metric: "web_news" }, { number: 17, metric: "web_news" }, { number: 3, metric: "volatility" }] as never,
      trace: [check("per_asset_cap"), { seq: 1, kind: "tool_call", name: "portfolio_comparison" }, check("per_asset_cap"), check("per_asset_cap")] as never,
    });
    const p = progressOf(v);
    expect(p.step).toBe(2);
    expect(p.done).toContain("2 recent news articles found for the court.");
    expect(p.done).toContain("1 portfolio comparison computed from the price history.");
    expect(p.done).toContain("Each of the 2 options checked against your limits.");
  });

  it("keeps the court in session while the Clerk writes (active_agent is null then)", () => {
    const v = at([...S, "advocate", "option_rules", "investigator", "judge"]);
    expect(progressOf(v).step).toBe(4);
    render(<FriendlyMode view={v} onSeeDetails={() => {}} />);
    fireEvent.click(screen.getByTestId("follow-toggle"));
    expect(screen.getByText(/Clerk is writing the ruling/)).toBeInTheDocument();
    expect(screen.queryByText("The tribunal has risen.")).toBeNull();
    expect(screen.getByTestId("seat-clerk")).toHaveAttribute("data-active", "true");
  });

  it("shows an elapsed clock and says when it takes longer than usual", () => {
    vi.useFakeTimers();
    let t = 0;
    render(<LiveProgress view={base} now={() => t} />);
    expect(screen.getByTestId("live-clock")).toHaveTextContent("0:00 · usually about 1:10");
    act(() => { t = 23_000; vi.advanceTimersByTime(1000); });
    expect(screen.getByTestId("live-clock")).toHaveTextContent("0:23");
    act(() => { t = 95_000; vi.advanceTimersByTime(1000); });
    expect(screen.getByTestId("live-clock")).toHaveTextContent("1:35 · taking longer than usual");
  });

  it("opens with 'in session', not an options check, before the first update arrives", () => {
    render(<FriendlyMode view={{ ...base, stage: "advocate", stages_done: [], snapshot: null } as SessionView} onSeeDetails={() => {}} />);
    fireEvent.click(screen.getByTestId("follow-toggle"));
    expect(screen.getByText("The tribunal is in session…")).toBeInTheDocument();
  });

  it("disappears once the session completes", () => {
    render(<FriendlyMode view={{ ...base, status: "completed" } as SessionView} onSeeDetails={() => {}} />);
    fireEvent.click(screen.getByTestId("follow-toggle"));
    expect(screen.queryByTestId("live-progress")).toBeNull();
    expect(screen.getByText("The tribunal has risen.")).toBeInTheDocument();
  });
});
