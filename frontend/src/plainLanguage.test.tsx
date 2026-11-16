import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AdvancedMode } from "./advanced";
import { FriendlyMode } from "./friendly";
import { plain } from "./friendly/plain";
import { courtWords } from "./friendly/hearing";
import type { SessionView } from "./model/sessionView";
import recorded from "./replay/recorded_session.json";

const view = recorded as unknown as SessionView;
// File names, snapshot ids, internal rule and class names, JSON, cloud service names.
const TECHNICAL = /\.csv|\.parquet|\.json|_daily|napshot|Hard_Rule|Soft_Pref|per_asset_cap|max_drawdown|max_volatility|speculative_limit|instruction|sha256|\{"|s3:\/\/|arn:aws|Bedrock|AgentCore|Polly|option_\d|\d{8}T\d{6}Z/;

describe("no technical detail reaches the investor", () => {
  it("summary view of a real recorded hearing, with the courtroom and every section open", () => {
    const { container } = render(<FriendlyMode view={view} onSeeDetails={() => {}} inlineExhibits portfolio={{ "XBB.TO": 0.6, SPY: 0.4 }} />);
    fireEvent.click(screen.getByTestId("follow-toggle"));
    expect(container.textContent ?? "").not.toMatch(TECHNICAL);
    expect(screen.queryByRole("button", { name: /sound|voice/i })).toBeNull();
  });

  it("detailed analysis of the same hearing, with every Exhibit opened in turn", () => {
    for (const e of view.exhibits) {
      const { container, unmount } = render(<AdvancedMode view={view} focus={{ kind: "exhibit", number: e.number }} onFocus={() => {}} />);
      expect(container.textContent ?? "", `Exhibit ${e.number}`).not.toMatch(TECHNICAL);
      unmount();
    }
  });

  it("rewrites the agents' internal wording", () => {
    expect(plain("Tables used: assets_universe@20261115T154221Z-esg, prices_daily@20261115T154221Z-esg. Period: 2021 to 2026. Snapshot_Id 20261115T154221Z-esg, retrieved 2026-11-13."))
      .toBe("Sources: daily market prices (Yahoo Finance) and the Bank of Canada USD/CAD rate. Period: 2021 to 2026. Data retrieved 2026-11-13.");
    expect(plain("Keep TSLA at or below 5.0%; failing rules: per_asset_cap, max_volatility.")).toBe("Keep TSLA at or below 5.0%.");
    expect(plain("Some Hard_Rules fail; the Advocate cited Exhibit 3.")).toBe("Some limits fail; the Defense cited Exhibit 3.");
    expect(plain("At 2.5%, option_2 passes all Hard_Rules.")).toBe("At 2.5%, option 2 passes all limits.");
    expect(courtWords("Judge's reason: option_2 passes; no Hard_Rule fails.")).toBe("Judge's reason: option 2 passes; no limit fails.");
  });
});
