import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { FriendlyMode, newsDate, safeUrl } from "./index";
import { ExhibitList } from "../advanced/ExhibitList";
import type { Exhibit, SessionView } from "../model/sessionView";

const news = [
  { exhibit: 41, title: "Tesla recalls 12,000 vehicles over a seat-belt issue", source: "reuters.com",
    url: "https://www.reuters.com/business/tesla-recall", published: "2026-11-13T14:02:00Z",
    snippet: "The recall covers Model Y units built in 2025.", confidence: "Context" },
  { exhibit: 42, title: "Untrusted link", url: "javascript:alert(1)", published: null },
];

const view: SessionView = {
  session_id: "s1", status: "completed", contract: null, stage: "clerk", stages_done: [],
  active_agent: null, exhibits: [], rule_results: [], sensitivity: [], trace: [], summaries: {},
  snapshot: null, data_notices: [], error: null,
  verdict: { verdict: "reject", max_weight: null, failing_rules: [], exhibits: [] },
  ruling: { verdict: "reject", facts: [], disclaimers: [], what_would_change: [], recent_context: news },
};

describe("news cards (AgentCore Web Search terms: title, source, date, link)", () => {
  it("shows each article with its source, date, link and Context badge", () => {
    const onSee = vi.fn();
    render(<FriendlyMode view={view} onSeeDetails={onSee} />);
    const card = screen.getByTestId("news-41");
    const link = within(card).getByRole("link", { name: /Tesla recalls/ });
    expect(link).toHaveAttribute("href", "https://www.reuters.com/business/tesla-recall");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
    expect(card).toHaveTextContent("reuters.com");
    expect(card).toHaveTextContent("Nov 13, 2026");
    expect(card).toHaveTextContent("Context");
    fireEvent.click(within(card).getByRole("button", { name: "[Exhibit 41]" }));
    expect(onSee).toHaveBeenCalledWith({ kind: "exhibit", number: 41 });
  });

  it("never renders a non-http URL as a link", () => {
    render(<FriendlyMode view={view} onSeeDetails={() => {}} />);
    expect(within(screen.getByTestId("news-42")).queryByRole("link")).toBeNull();
    expect(safeUrl("javascript:alert(1)")).toBeNull();
    expect(safeUrl("https://example.com/a")).toBe("https://example.com/a");
  });

  it("hides the section when there is no news", () => {
    render(<FriendlyMode view={{ ...view, ruling: { ...view.ruling!, recent_context: [] } }} onSeeDetails={() => {}} />);
    expect(screen.queryByTestId("news-cards")).toBeNull();
  });

  it("formats dates and keeps unparseable ones", () => {
    expect(newsDate("2026-11-13")).toBe("Nov 13, 2026");
    expect(newsDate("yesterday")).toBe("yesterday");
    expect(newsDate(null)).toBeNull();
  });
});

describe("web Exhibit in Advanced_Mode", () => {
  const exhibits: Exhibit[] = [
    { number: 1, metric: "volatility", value: 0.58, currency: "CAD", snapshot_id: "s" },
    { number: 41, metric: "web_news", currency: "", snapshot_id: null, source_files: [news[0].url],
      value: { title: news[0].title, url: news[0].url, source: "reuters.com", published: news[0].published,
        snippet: news[0].snippet }, inputs: { query: "Tesla news", days: 30 } },
  ];

  it("shows the article as a link, not raw JSON, and counts news apart", () => {
    render(<ExhibitList exhibits={exhibits} focusedNumber={41} onFocus={() => {}} />);
    expect(screen.getByText("1 calculations · 1 news")).toBeInTheDocument();
    const details = screen.getByTestId("exhibit-details-41");
    expect(within(details).getByRole("link", { name: /Tesla recalls/ })).toHaveAttribute("href", news[0].url);
    expect(details).not.toHaveTextContent("{\"title\"");
    expect(details).toHaveTextContent("reuters.com");
  });
});
