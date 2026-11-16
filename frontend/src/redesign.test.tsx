import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe as group, it, expect, vi } from "vitest";
import { ExhibitCard, describe, sourceLabels } from "./advanced/ExhibitCard";
import { FriendlyMode } from "./friendly";
import { ProfileForm, EMPTY_VALUES, esgChoice, FOSSIL } from "./ProfileForm";
import { AppealControl, whatIfsOf } from "./appeal/AppealView";
import type { Exhibit, SessionView } from "./model/sessionView";

// Shapes copied from a live Robert / 30% TSLA session.
const comparison = { number: 1, metric: "portfolio_comparison", currency: "CAD", snapshot_id: "20261115T154221Z-esg",
  period_start: "2021-11-13", period_end: "2026-11-12", source_files: ["prices_daily@20261115T154221Z-esg", "fx_usdcad_daily@20261115T154221Z-esg"],
  processing_notes: ["TSLA: converted from USD to CAD"], inputs: { ticker: "TSLA", weight: 0.3 },
  value: { base: { annualized_volatility: 0.1038, max_drawdown: -0.1557 }, proposed: { annualized_volatility: 0.2253, max_drawdown: -0.3265 } } } as unknown as Exhibit;
const risk = { number: 2, metric: "risk_contribution", currency: "CAD", snapshot_id: "s",
  value: { share_of_variance_pct: { TSLA: 76.07, SPY: 5.96, "XIU.TO": 6.09 } } } as unknown as Exhibit;

group("Exhibit cards (plain reading first, trace one click away)", () => {
  it("reads a comparison as title, reason, key result and human sources", () => {
    const d = describe(comparison);
    expect(d.title).toBe("Your portfolio, before and after the request");
    expect(d.key).toBe("10.4% → 22.5%");
    expect(d.rows?.[0]).toMatchObject({ label: "Yearly swings (volatility)", worse: true, textA: "10.4%", text: "22.5%" });
    expect(sourceLabels(comparison)).toEqual(["Daily prices, adjusted for splits and dividends (Yahoo Finance)", "USD/CAD exchange rate (Bank of Canada)"]);
    expect(describe(risk).keyNote).toBe("of the risk comes from TSLA");
  });

  it("shows method and limits in plain words, with no file name or snapshot id", () => {
    render(<ExhibitCard exhibit={comparison} />);
    const card = screen.getByTestId("exhibit-details-1");
    expect(within(card).getByText("Method and limits")).toBeInTheDocument();
    expect(card).not.toHaveTextContent("20261115T154221Z");
    expect(card).not.toHaveTextContent("prices_daily");
    expect(card).not.toHaveTextContent("{");
    expect(card).toHaveTextContent("converted at the Bank of Canada daily rate");
    expect(card).toHaveTextContent("Nov 13, 2021 to Nov 12, 2026");
  });

  it("opens an Exhibit beside the hearing instead of leaving it", () => {
    const view = { session_id: "s", status: "completed", contract: null, stage: "clerk", stages_done: [], active_agent: null,
      exhibits: [risk], rule_results: [], sensitivity: [], trace: [], summaries: {}, snapshot: null, data_notices: [], error: null,
      verdict: { verdict: "reject", max_weight: null, failing_rules: [], exhibits: [2] },
      ruling: { what_would_change: [{ text: "A smaller size.", citations: [2] }] } } as unknown as SessionView;
    const onSee = vi.fn();
    render(<FriendlyMode view={view} onSeeDetails={onSee} inlineExhibits />);
    fireEvent.click(screen.getByRole("button", { name: /Evidence 2/ }));
    expect(screen.getByRole("dialog", { name: "Evidence 2" })).toHaveTextContent("Where the portfolio's risk comes from");
    expect(onSee).not.toHaveBeenCalled();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

group("investor form", () => {
  it("shows limits as percentages and stores fractions", () => {
    const onChange = vi.fn();
    render(<ProfileForm values={{ ...EMPTY_VALUES, max_volatility: 0.12 }} onChange={onChange} />);
    const input = screen.getByLabelText(/Max volatility/) as HTMLInputElement;
    expect(input.value).toBe("12");
    fireEvent.change(input, { target: { value: "15" } });
    expect(onChange.mock.calls[0][0].max_volatility).toBeCloseTo(0.15);
  });

  it("separates 'not specified', 'no restriction' and the fossil-fuel screen", () => {
    expect(esgChoice(EMPTY_VALUES, false)).toBe("unspecified");
    expect(esgChoice(EMPTY_VALUES, true)).toBe("none");
    const onChange = vi.fn();
    render(<ProfileForm values={EMPTY_VALUES} onChange={onChange} />);
    expect((screen.getByRole("radio", { name: /Not specified yet/ }) as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: /Avoid fossil fuels/ }));
    expect(onChange.mock.calls[0][0].esg_exclusions).toEqual([FOSSIL]);
  });
});

group("what-if appeals", () => {
  const view = { contract: { horizon_years: { min: 3, max: 5 }, speculative_limit: 0.05, max_drawdown: 0.15, esg_exclusions: [] },
    sensitivity: [{ variable: "position_size", changed: true, threshold: 0.05 }] } as unknown as SessionView;

  it("offers one-click changes from the session's own contract", () => {
    const w = whatIfsOf(view);
    expect(w.map((x) => x.label)).toEqual(["What if my horizon were 10 years?", "What if I asked for 5%?",
      "What if my speculative limit were 10%?", "What if my max drawdown were 30%?"]);
    const onSubmit = vi.fn();
    render(<AppealControl busy={false} onSubmit={onSubmit} view={view} />);
    fireEvent.click(screen.getByRole("button", { name: /horizon were 10 years/ }));
    expect(onSubmit).toHaveBeenCalledWith({ field: "horizon_years", value: 10 });
  });
});
