import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PortfolioComparison, asFractions, personaPortfolio, withPosition } from "./Portfolio";

const ROBERT = { "XBB.TO": 0.4, "ZST.TO": 0.15, "XIU.TO": 0.15, SPY: 0.15, JNJ: 0.08, "RY.TO": 0.07 };
const sum = (w: Record<string, number>) => Object.values(w).reduce((a, b) => a + b, 0);

describe("portfolio scenarios", () => {
  it("funds a new position by reducing every holding in proportion, like the toolkit, and stays at 100%", () => {
    const p = withPosition(ROBERT, "TSLA", 0.3);
    expect(p.TSLA).toBeCloseTo(0.3);
    expect(p["XBB.TO"]).toBeCloseTo(0.28);
    expect(p["RY.TO"]).toBeCloseTo(0.049);
    expect(sum(p)).toBeCloseTo(1);
    // Adding to a security already held adds to what is left of it.
    const q = withPosition(ROBERT, "SPY", 0.2);
    expect(q.SPY).toBeCloseTo(0.15 * 0.8 + 0.2);
    expect(sum(q)).toBeCloseTo(1);
  });

  it("reads the persona's own holdings and typed holdings in percent", () => {
    expect(personaPortfolio({ contract_values: { base_portfolio: { value: ROBERT } } } as never)).toEqual(ROBERT);
    expect(personaPortfolio({ contract_values: {} } as never)).toBeNull();
    expect(asFractions({ "XIU.TO": 60, SPY: 40 })).toEqual({ "XIU.TO": 0.6, SPY: 0.4 });
  });

  it("shows today, the request and the accepted size side by side, labelled as hypothetical", () => {
    render(<PortfolioComparison base={ROBERT} ticker="TSLA" requested={0.3} accepted={0.05} />);
    const table = screen.getByTestId("portfolio-table");
    expect(table).toHaveTextContent("Today");
    expect(table).toHaveTextContent("At 30% TSLA");
    expect(table).toHaveTextContent("At 5% TSLA");
    expect(table).toHaveTextContent("Royal Bank of Canada");
    expect(table).toHaveTextContent("28.0%");   // XBB.TO at 30% TSLA
    expect(table).toHaveTextContent("38.0%");   // XBB.TO at 5% TSLA
    expect(table).toHaveTextContent("TSLA 30.0%"); // largest holding in the requested scenario
    expect(screen.getByTestId("portfolio-note")).toHaveTextContent("nothing is bought or sold");
  });
});
