import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { FriendlyMode, timelineOf } from "./index";
import type { SessionView } from "../model/sessionView";

const rules = (fail: string[]) => ["per_asset_cap", "max_volatility", "max_drawdown", "speculative_limit", "crypto_cap"]
  .map((rule) => ({ rule, status: fail.includes(rule) ? "fail" : "pass" }));

// Shape of the live Robert / 30% TSLA session.
const view = {
  session_id: "s1", status: "completed", contract: null, stage: "clerk", stages_done: [],
  active_agent: null, rule_results: [], sensitivity: [], summaries: {}, snapshot: null, data_notices: [], error: null,
  exhibits: [
    { number: 3, metric: "volatility", value: 0.58, currency: "CAD", snapshot_id: "s" },
    { number: 41, metric: "web_news", value: { title: "Tesla recall" }, currency: "", snapshot_id: null },
  ],
  trace: [
    { kind: "agent_call", name: "advocate" }, { kind: "judge_check", name: "guidance_only" },
    { kind: "judge_check", name: "guidance_only" }, { kind: "judge_check", name: "per_asset_cap" },
  ],
  verdict: { verdict: "accept_with_conditions", max_weight: 0.025, failing_rules: [], exhibits: [],
    reason: "2.5% keeps you within every limit.", conditions: ["Review in 6 months", "Stop at 2.5%"] },
  ruling: {
    verdict: "accept_with_conditions", facts: [], disclaimers: [], what_would_change: [], decided_by: "judge",
    agents: { ran: ["advocate", "investigator", "judge"], failed: [] },
    options: [
      { option_id: "request", source: "request", ticker: "TSLA", weight: 0.3, rejected: true,
        failing_rules: ["per_asset_cap", "max_volatility", "max_drawdown", "speculative_limit"],
        hard_rule_results: rules(["per_asset_cap", "max_volatility", "max_drawdown", "speculative_limit"]) },
      { option_id: "option_1", source: "advocate", ticker: "TSLA", weight: 0.05, rejected: false, failing_rules: [], hard_rule_results: rules([]) },
      { option_id: "option_2", source: "advocate", ticker: "TSLA", weight: 0.025, rejected: false, failing_rules: [], hard_rule_results: rules([]) },
    ],
    material_risks: [
      { risk: "Tesla swings far more than your portfolio", exhibits: [3] },
      { risk: "A recall is in the news", exhibits: [41] },
    ],
  },
} as unknown as SessionView;

describe("courtroom timeline (who contributed what)", () => {
  it("lists the Defense, Investigator, code and Judge in order", () => {
    const steps = timelineOf(view);
    expect(steps.map((s) => s.agent)).toEqual(["advocate", "investigator", "code", "judge"]);
    expect(steps[0].lines[0]).toBe("Proposed 2 options: TSLA 5.0% and TSLA 2.5%.");
    expect(steps[0].note).toBe("Your request: TSLA at 30.0%.");
    expect(steps[1].lines[0]).toBe("Flagged 2 risks, 1 citing recent news.");
    expect(steps[2].lines[0]).toBe("your request (TSLA 30.0%): breaks the cap per holding, volatility limit, drawdown limit and speculative limit.");
    expect(steps[2].lines[1]).toBe("TSLA 5.0%: within all 5 limits.");
    expect(steps[2].lines[3]).toBe("2 agent statements screened for buy or sell wording.");
    expect(steps[3].title).toBe("Judge ruled");
    expect(steps[3].lines).toEqual(["Chose TSLA 2.5%, with 2 conditions.", "2.5% keeps you within every limit."]);
  });

  it("renders after the verdict and opens cited Exhibits", () => {
    const onSee = vi.fn();
    render(<FriendlyMode view={view} onSeeDetails={onSee} />);
    const inv = screen.getByTestId("timeline-investigator");
    fireEvent.click(within(inv).getByRole("button", { name: "[Exhibit 41]" }));
    expect(onSee).toHaveBeenCalledWith({ kind: "exhibit", number: 41 });
  });

  it("says when an agent failed and the code ruled", () => {
    const ruling = { ...(view.ruling as object), decided_by: "code",
      agents: { ran: ["investigator"], failed: [{ agent: "advocate" }, { agent: "judge" }] } };
    const steps = timelineOf({ ...view, ruling } as unknown as SessionView);
    expect(steps[0].lines[0]).toMatch(/could not run/);
    expect(steps[3].title).toBe("The code ruled (Judge unavailable)");
  });

  it("leaves out 0% options and names the ESG rule (live Mateo / XOM shape)", () => {
    const ruling = { ...(view.ruling as object), options: [
      { option_id: "request", source: "request", ticker: "XOM", weight: 0.1, rejected: true, failing_rules: ["esg_exclusion"] },
      { option_id: "option_1", source: "advocate", ticker: "XOM", weight: 0.05, rejected: true, failing_rules: ["esg_exclusion"] },
      { option_id: "option_2", source: "advocate", ticker: "XOM", weight: 0, rejected: false, failing_rules: [] },
    ] };
    const steps = timelineOf({ ...view, ruling, verdict: { verdict: "reject", max_weight: null, failing_rules: [], exhibits: [] } } as unknown as SessionView);
    expect(steps[0].lines[0]).toBe("Proposed 1 option: XOM 5.0%.");
    expect(steps[2].lines).toEqual(["your request (XOM 10.0%): breaks the ESG exclusion.", "XOM 5.0%: breaks the ESG exclusion.", "2 agent statements screened for buy or sell wording."]);
    expect(steps[3].lines[0]).toBe("Rejected the request: no option fits your limits.");
  });

  it("is hidden before the Ruling exists", () => {
    render(<FriendlyMode view={{ ...view, ruling: null, verdict: null } as SessionView} onSeeDetails={() => {}} />);
    expect(screen.queryByTestId("court-timeline")).toBeNull();
  });
});
