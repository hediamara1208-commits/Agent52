import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AdvancedMode } from "./index";
import type { SessionView } from "../model/sessionView";

const view: SessionView = {
  session_id: "s1", status: "completed", contract: null, stage: "clerk", stages_done: [], active_agent: null,
  exhibits: [{ number: 2, metric: "volatility", value: 0.12, currency: "CAD", snapshot_id: "snap-abc" }],
  verdict: null, ruling: null,
  rule_results: [{ rule: "speculative_limit", status: "fail", observed: 0.1, limit: 0.05, exhibits: [2] }],
  sensitivity: [{ variable: "speculative_limit", changed: true, threshold: 0.1, baseline_verdict: "reject", verdict_at_threshold: "accept", exhibit: 2 }],
  trace: [
    { seq: 1, kind: "agent_call", name: "Judge", summary: { input: "i", output: "o", instruction_hash: "deadbeef" } },
    { seq: 2, kind: "guardrail_block", name: "judge", summary: { rule: "no_orders" } },
  ],
  summaries: {}, snapshot: null, data_notices: [], error: null,
};

describe("Advanced_Mode", () => {
  it("shows limits and sensitivity, and no execution trace", () => {
    render(<AdvancedMode view={view} focus={null} onFocus={() => {}} />);
    expect(screen.getByTestId("rule-speculative_limit")).toHaveTextContent("fail");
    expect(screen.getByTestId("rule-speculative_limit")).toHaveTextContent("5.0%");
    expect(screen.getByTestId("sensitivity-speculative_limit")).toHaveTextContent("accept");
    expect(screen.queryByTestId("instruction-hash")).toBeNull();
    expect(screen.queryByTestId("trace-2")).toBeNull();
    expect(screen.queryByTestId("trace-download")).toBeNull();
  });

  it("opens the focused Exhibit without its snapshot id; citations call onFocus", () => {
    const onFocus = vi.fn();
    const { rerender } = render(<AdvancedMode view={view} focus={null} onFocus={onFocus} />);
    expect(screen.queryByTestId("exhibit-details-2")).toBeNull();
    fireEvent.click(screen.getAllByRole("button", { name: "[Exhibit 2]" })[0]);
    expect(onFocus).toHaveBeenCalledWith({ kind: "exhibit", number: 2 });
    rerender(<AdvancedMode view={view} focus={{ kind: "exhibit", number: 2 }} onFocus={onFocus} />);
    expect(screen.getByTestId("exhibit-details-2")).not.toHaveTextContent("snap-abc");
  });

  it("marks and scrolls to the focused rule", () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    render(<AdvancedMode view={view} focus={{ kind: "rule", rule: "speculative_limit" }} onFocus={() => {}} />);
    expect(screen.getByTestId("rule-speculative_limit")).toHaveAttribute("data-focused", "true");
    expect(scroll).toHaveBeenCalled();
  });
});
