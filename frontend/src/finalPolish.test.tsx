import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { useState } from "react";
import recorded from "./replay/recorded_session.json";
import type { SessionView } from "./model/sessionView";
import { PortfolioBuilder, checkRows, readPaste, type HoldingRow } from "./PortfolioBuilder";
import { TribunalArguments, argumentsOf } from "./friendly/Arguments";
import { FriendlyMode } from "./friendly";
import { AdvancedMode } from "./advanced/AdvancedMode";

const view = recorded as unknown as SessionView;

function Harness({ start = [] as HoldingRow[] }) {
  const [rows, setRows] = useState(start);
  return <PortfolioBuilder rows={rows} onChange={setRows} example={{ "XIU.TO": 0.6, SPY: 0.4 }} />;
}

describe("own portfolio", () => {
  it("accepts holdings only when every share is given and they total 100%", () => {
    expect(checkRows([])).toMatchObject({ ok: false });
    expect(checkRows([{ ticker: "SPY", pct: "60" }])).toMatchObject({ ok: false, error: "40% left to allocate." });
    expect(checkRows([{ ticker: "SPY", pct: "60" }, { ticker: "XIU.TO", pct: "55" }])).toMatchObject({ ok: false, error: "15% over 100%." });
    expect(checkRows([{ ticker: "SPY", pct: "60" }, { ticker: "XIU.TO", pct: "" }])).toMatchObject({ ok: false });
    expect(checkRows([{ ticker: "SPY", pct: "-5" }])).toMatchObject({ ok: false });
    expect(checkRows([{ ticker: "SPY", pct: "60" }, { ticker: "XIU.TO", pct: "40" }])).toEqual({ ok: true, total: 100, value: { SPY: 60, "XIU.TO": 40 } });
  });

  it("imports a pasted list, names what it does not recognise, and keeps nothing else", () => {
    const got = readPaste("XIU.TO 40\nry 20%\nFAKE 10\n<script>alert(1)</script>\nSPY: 30");
    expect(got.rows).toEqual([{ ticker: "XIU.TO", pct: "40" }, { ticker: "RY.TO", pct: "20" }, { ticker: "SPY", pct: "30" }]);
    expect(got.unknown).toEqual(["FAKE"]);
    expect(got.unread).toBe(1);
  });

  it("adds by search, edits, shows the running total and removes", async () => {
    render(<Harness />);
    const user = userEvent.setup();
    await user.type(screen.getByRole("combobox", { name: "Add a holding" }), "royal{Enter}");
    await user.type(screen.getByLabelText("Share of Royal Bank of Canada (%)"), "70");
    expect(screen.getByTestId("builder-total")).toHaveTextContent("Total 70% 30% left to allocate.");
    await user.type(screen.getByRole("combobox", { name: "Add a holding" }), "spy{Enter}");
    await user.type(screen.getByLabelText(/Share of SPDR/), "30");
    expect(screen.getByTestId("builder-total")).toHaveTextContent("Total 100% Ready.");
    await user.click(screen.getByRole("button", { name: "Remove Royal Bank of Canada" }));
    expect(screen.getByTestId("builder-total")).toHaveTextContent("Total 30%");
    await user.click(screen.getByRole("button", { name: "Start from the example" }));
    expect(screen.getByTestId("builder-total")).toHaveTextContent("Total 100% Ready.");
  });
});

describe("view the arguments", () => {
  it("builds each member's argument from the hearing's own outputs", () => {
    const parts = argumentsOf(view);
    expect(parts.map((p) => p.who)).toEqual(["advocate", "investigator", "bailiff", "judge", "clerk"]);
    const pros = parts.find((p) => p.who === "investigator")!;
    expect(pros.main).toBe("Single-stock concentration.");
    expect(pros.why).toBe("Low risk tolerance.");
    expect(pros.evidence[0].exhibits).toEqual([1]);
    expect(JSON.stringify(parts)).not.toMatch(/Hard_Rule|per_asset_cap|Snapshot_Id|option_\d|@\d{8}T/);
  });

  it("lets the reader pick a member and open the evidence behind a point", () => {
    const onOpen = vi.fn();
    render(<TribunalArguments view={view} onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("tab", { name: "Judge" }));
    const panel = screen.getByRole("tabpanel", { name: "Judge" });
    expect(panel).toHaveTextContent("Main argument");
    expect(panel).toHaveTextContent("accepted with conditions");
    fireEvent.click(screen.getByRole("tab", { name: "Prosecutor" }));
    fireEvent.click(within(screen.getByRole("tabpanel", { name: "Prosecutor" })).getByRole("button", { name: "Evidence 1" }));
    expect(onOpen).toHaveBeenCalledWith(1);
  });

  it("is closed by default under the decision, and the courtroom has no audio or stage scene", () => {
    const { container } = render(<FriendlyMode view={view} onSeeDetails={() => undefined} />);
    expect(screen.getByTestId("view-arguments")).not.toHaveAttribute("open");
    fireEvent.click(screen.getByTestId("follow-toggle"));
    expect(screen.getByTestId("seat-judge")).toHaveTextContent("Judge");
    expect(container.querySelector("audio, .court-camera, .character")).toBeNull();
  });
});

describe("evidence by topic", () => {
  it("groups the evidence and names its sources in plain words", () => {
    render(<AdvancedMode view={view} focus={null} onFocus={() => undefined} />);
    const risk = screen.getByTestId("evidence-group-portfolio-risk");
    expect(risk).toHaveTextContent("Daily market prices (Yahoo Finance), in CAD using the Bank of Canada USD/CAD rate. Period Nov 2021 to Nov 2026.");
    expect(screen.getByTestId("evidence-group-investor-constraints")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-group-historical-performance")).toBeInTheDocument();
  });
});
