import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CourtroomScene, FriendlyMode } from "./index";
import { createSessionStore } from "../model/sessionView";
import type { SessionView } from "../model/sessionView";

const view: SessionView = {
  session_id: "s1", status: "completed", contract: null, stage: "clerk", stages_done: [],
  active_agent: "Judge", exhibits: [], rule_results: [], sensitivity: [], trace: [],
  summaries: { advocate: "Two options proposed." }, snapshot: null, data_notices: [], error: null,
  verdict: { verdict: "accept_with_conditions", max_weight: 0.05, failing_rules: ["speculative_limit"], exhibits: [2] },
  ruling: {
    verdict: "accept_with_conditions", facts: [], disclaimers: [],
    what_would_change: [{ text: "Raising the limit to 10% moves the maximum to 10%.", citations: [3] }],
  },
};

describe("Friendly_Mode", () => {
  it("shows four seats and highlights only the active agent", () => {
    render(<CourtroomScene activeAgent="Judge" />);
    for (const a of ["investigator", "advocate", "judge", "clerk"])
      expect(screen.getByTestId(`seat-${a}`)).toBeInTheDocument();
    expect(screen.getByTestId("seat-judge")).toHaveAttribute("data-active", "true");
    expect(screen.getByTestId("seat-clerk")).toHaveAttribute("data-active", "false");
  });

  it("renders verdict, summary, and exhibit links that call See details", () => {
    const onSee = vi.fn();
    render(<FriendlyMode view={view} onSeeDetails={onSee} />);
    expect(screen.getByTestId("verdict")).toHaveTextContent("Accepted with conditions");
    fireEvent.click(screen.getByTestId("follow-toggle"));
    expect(screen.getByTestId("court-record")).toHaveTextContent("So ordered.");
    fireEvent.click(screen.getByRole("button", { name: "[Exhibit 3]" }));
    expect(onSee).toHaveBeenCalledWith({ kind: "exhibit", number: 3 });
  });
});

describe("four answers card (Req. 33.4)", () => {
  const long = Array.from({ length: 90 }, (_, i) => `w${i}`).join(" ");
  const withAnswers: SessionView = {
    ...view,
    ruling: {
      ...view.ruling!,
      questions: [
        { id: "which_data", heading: "Which data?", statements: [{ text: "Prices to 2026.", citations: [1, 2] }] },
        { id: "why_this_choice", heading: "Why this choice?", statements: [{ text: long, citations: [] }] },
        { id: "which_limits", heading: "Which limits?", statements: [{ text: "Simulation only.", citations: [] }] },
        { id: "what_would_change", heading: "What would change the answer?", statements: [{ text: "Raise the limit.", citations: [3] }] },
      ],
    },
  };

  it("shows four headed answers, caps each at 60 words, and links Exhibits", () => {
    const onSee = vi.fn();
    render(<FriendlyMode view={withAnswers} onSeeDetails={onSee} />);
    for (const h of ["Which data?", "Why this choice?", "Which limits?", "What would change the answer?"])
      expect(screen.getByRole("heading", { name: h })).toBeInTheDocument();
    const text = screen.getByTestId("answer-text-why_this_choice").textContent ?? "";
    expect(text.split(/\s+/).length).toBeLessThanOrEqual(60);
    fireEvent.click(within(screen.getByTestId("answer-which_data")).getByRole("button", { name: "[Exhibit 2]" }));
    expect(onSee).toHaveBeenCalledWith({ kind: "exhibit", number: 2 });
  });

  it("renders no card when the ruling has no answers", () => {
    render(<FriendlyMode view={view} onSeeDetails={vi.fn()} />);
    expect(screen.queryByTestId("four-answers")).toBeNull();
  });
});

describe("view store", () => {
  it("defaults to friendly; mode switch changes only mode; openDetails sets focus and advanced", () => {
    const store = createSessionStore({ view });
    expect(store.getState().mode).toBe("friendly");
    store.setMode("advanced");
    expect(store.getState().view).toBe(view);
    expect(store.getState().focus).toBeNull();
    store.setMode("friendly");
    store.openDetails({ kind: "rule", rule: "speculative_limit" });
    expect(store.getState()).toMatchObject({ mode: "advanced", focus: { kind: "rule", rule: "speculative_limit" } });
    store.setFocus({ kind: "trace", seq: 4 });
    expect(store.getState().focus).toEqual({ kind: "trace", seq: 4 });
  });
});
