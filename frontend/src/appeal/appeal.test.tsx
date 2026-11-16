import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AppealControl, AppealView } from "./AppealView";
import { diffSessions } from "./diff";
import type { SessionView } from "../model/sessionView";

const base = (over: Partial<SessionView>): SessionView => ({
  session_id: "s1", status: "completed", contract: null, stage: "clerk", stages_done: [], active_agent: null,
  exhibits: [], verdict: { verdict: "accept" }, ruling: null, rule_results: [], sensitivity: [], trace: [],
  summaries: {}, snapshot: null, data_notices: [], error: null, ...over,
});
const ex = (number: number, value: number) => ({ number, metric: "vol", value, currency: "CAD", assets: ["TSLA"], snapshot_id: "x" });
const original = base({ exhibits: [ex(1, 0.4)], rule_results: [{ rule: "per_asset_cap", status: "pass", observed: 0.1, limit: 0.2 }] });
const appealed = base({
  session_id: "s2", verdict: { verdict: "reject" }, exhibits: [ex(7, 0.5)],
  rule_results: [{ rule: "per_asset_cap", status: "fail", observed: 0.3, limit: 0.2 }],
});

describe("appeal", () => {
  it("diffs verdict, rules and exhibits", () => {
    const d = diffSessions(original, appealed);
    expect(d.verdict.changed).toBe(true);
    expect(d.hard_rules.map((r) => r.rule)).toEqual(["per_asset_cap"]);
    expect(d.exhibits[0].appeal.number).toBe(7);
    expect(diffSessions(original, original).verdict.changed).toBe(false);
  });
  it("AppealView shows both verdicts and the changed input", () => {
    render(<AppealView original={original} appeal={appealed} change={{ field: "per_asset_cap", value: 0.3 }} />);
    expect(screen.getByTestId("appeal-original").textContent).toContain("accept");
    expect(screen.getByTestId("appeal-appeal").textContent).toContain("reject");
    expect(screen.getByTestId("appeal-change").textContent).toContain("Cap per holding");
    expect(screen.getByTestId("appeal-change").textContent).not.toContain("per_asset_cap");
    expect(screen.getByTestId("appeal-verdict-changed").textContent).toContain("changed");
  });
  it("reads like a person would: percentages, limits, and what moved", () => {
    const o = base({ contract: { speculative_limit: 0.05 } as never,
      verdict: { verdict: "accept_with_conditions", max_weight: 0.025 } as never,
      rule_results: [{ rule: "speculative_limit", status: "fail", observed: 0.3, limit: 0.05 }],
      exhibits: [{ number: 3, metric: "currency_exposure", value: { base: { CAD: 0.77, USD: 0.22999999999999998 } },
        currency: "", assets: ["TSLA"], snapshot_id: "x" }] });
    const a = base({ session_id: "s3", verdict: { verdict: "accept_with_conditions", max_weight: 0.05 } as never,
      rule_results: [{ rule: "speculative_limit", status: "fail", observed: 0.3, limit: 0.1 }],
      exhibits: [{ number: 9, metric: "currency_exposure", value: { base: { CAD: 0.75, USD: 0.25 } },
        currency: "", assets: ["TSLA"], snapshot_id: "x" }] });
    render(<AppealView original={o} appeal={a} change={{ field: "speculative_limit", value: 0.1 }} />);
    expect(screen.getByTestId("appeal-change").textContent).toContain("Speculative limit 5.0% → 10.0%");
    expect(screen.getByTestId("appeal-original").textContent).toContain("accept with conditions, up to 2.5%");
    expect(screen.getByTestId("appeal-verdict-changed").textContent)
      .toBe("Same verdict; the largest lawful size changed from 2.5% to 5.0%.");
    const view = screen.getByTestId("appeal-view").textContent ?? "";
    expect(view).toContain("Speculative limit: fail (30.0% vs limit 5.0%) → fail (30.0% vs limit 10.0%)");
    expect(view).not.toContain("0.22999999999999998");
  });
  it("control submits exactly one change", async () => {
    const onSubmit = vi.fn();
    render(<AppealControl busy={false} onSubmit={onSubmit} />);
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Appeal field"), "per_asset_cap");
    await user.type(screen.getByLabelText("Appeal value"), "0.3");
    await user.click(screen.getByRole("button", { name: "Submit appeal" }));
    expect(onSubmit).toHaveBeenCalledWith({ field: "per_asset_cap", value: 0.3 });
  });
});
