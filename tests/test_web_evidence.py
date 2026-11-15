"""Newsroom (AgentCore Web Search) as Context Exhibits: shape, filters, limits, failures, screening."""
from datetime import datetime, timezone

from guide.toolkit.exhibits import ExhibitRegistry
from guide.toolkit.web_evidence import (
    WEB_METRIC, Newsroom, WebToolRunner, build_queries, web_context,
)

NOW = datetime(2026, 11, 15, 15, 0, tzinfo=timezone.utc)
ROBERT = {"risk_level": "low"}
MATEO = {"risk_level": "moderate", "esg_exclusions": ["XOM"]}


class FakeSearch:
    def __init__(self, results=None, error=None):
        self.calls, self.results, self.error = [], results, error

    def __call__(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        q = kw["searchQuery"]
        return {"results": self.results if self.results is not None else [
            {"title": f"{q} headline about the company today", "url": f"https://www.reuters.com/{abs(hash(q))}",
             "text": "Tesla said on Thursday ...", "publishedAt": "2026-11-13T10:00:00Z"}]}


def test_queries_add_controversy_search_only_when_esg_matters():
    assert len(build_queries("TSLA", "Tesla", ROBERT)) == 2
    q = build_queries("XOM", "Exxon Mobil", MATEO)
    assert len(q) == 3 and "controversy" in q[2][0]
    assert "investor.exxonmobil.com" not in q[2][1] and "reuters.com" in q[2][1]


def test_collect_records_context_exhibits_with_link_and_filters():
    search = FakeSearch()
    reg = ExhibitRegistry()
    found = Newsroom(search, now=lambda: NOW).collect(reg, "TSLA", "Tesla", ROBERT)
    assert len(found) == 2 and all(e.metric == WEB_METRIC for e in found)
    v = found[0].value
    assert v["url"].startswith("https://") and v["source"] == "reuters.com" and v["published"] == "2026-11-13"
    assert v["confidence"] == "Context" and found[0].source_files == (v["url"],)
    f = search.calls[0]["filters"]
    assert "reuters.com" in f["domainFilter"]["include"]
    assert f["publishedDateFilter"]["publishedAfter"].startswith("2026-10-16")
    assert search.calls[0]["webSearchId"] == "web-search.v1"
    assert [c["exhibit"] for c in web_context(reg)] == [e.number for e in found]


def test_failure_is_recorded_not_raised():
    room = Newsroom(FakeSearch(error=RuntimeError("AccessDenied")), now=lambda: NOW)
    assert room.collect(ExhibitRegistry(), "TSLA", "Tesla", ROBERT) == []
    assert room.failures


def test_guardrail_screen_drops_flagged_snippets():
    room = Newsroom(FakeSearch(), now=lambda: NOW, screen=lambda text: False)
    assert room.collect(ExhibitRegistry(), "TSLA", "Tesla", ROBERT) == []


def test_duplicates_and_bad_results_dropped():
    t = "Tesla expands recall of Model Y vehicles"
    dup = [{"title": t, "url": "https://reuters.com/a", "text": "x"},
           {"title": t, "url": "https://reuters.com/a", "text": "x"},
           {"title": "", "url": "https://reuters.com/b"},
           {"title": "Tesla Investor Relations", "url": "https://ir.tesla.com/"},
           {"title": "ExxonMobil Holdings Corporation (XOM)", "url": "https://investor.exxonmobil.com/x"},
           {"title": t + " again", "url": "javascript:alert(1)"}]
    found = Newsroom(FakeSearch(dup), now=lambda: NOW).collect(ExhibitRegistry(), "TSLA", "Tesla", ROBERT)
    assert len(found) == 1


def test_agent_tool_is_bounded_and_adds_exhibits():
    class Base:
        def tool_config(self):
            return {"tools": [{"toolSpec": {"name": "annualized_return"}}]}

        def run(self, tool_use):
            return {"status": "success", "content": [{"json": {"base": True}}]}

    reg = ExhibitRegistry()
    room = Newsroom(FakeSearch(), now=lambda: NOW, max_agent_searches=2)
    runner = WebToolRunner(Base(), room, reg)
    names = [t["toolSpec"]["name"] for t in runner.tool_config["tools"]]
    assert names == ["annualized_return", "web_search"]
    ok = runner.run({"name": "web_search", "input": {"query": "Tesla recall"}})
    assert ok["status"] == "success" and ok["content"][0]["json"]["web_exhibits"][0]["exhibit"] == 1
    runner.run({"name": "web_search", "input": {"query": "Tesla lawsuit"}})
    third = runner.run({"name": "web_search", "input": {"query": "Tesla again"}})
    assert third["status"] == "error"
    assert runner.run({"name": "annualized_return", "input": {}})["content"][0]["json"]["base"]
