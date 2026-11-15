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


def test_forecast_and_valuation_headlines_are_not_evidence():
    from guide.toolkit.web_evidence import is_informative
    for t in ("Here's What Needs to Happen for Tesla's Bull Case to Materialize and Push Past $500 Next Year",
              "Is ExxonMobil Holdings (XOM) Undervalued After Its $12.5b Guyana Longtail Approval?",
              "Glj Research Reaffirms Sell Rating for Tesla shares today",
              "After a 3.9% Raise, Here's How Many Shares of ExxonMobil You'd Now Need for $1,000 a Month"):
        assert not is_informative(t), t
    for t in ("Incoming Texas AG vows rigorous scrutiny of potential SpaceX-Tesla merger",
              "Tesla (TSLA) Breaks Ground On $10 Billion Texas Solar Factory As EU Approvals Advance"):
        assert is_informative(t), t


def test_recent_context_fits_the_session_view_schema():
    """The UI's news cards read ruling.recent_context; it must validate as the SessionView contract."""
    import pytest
    from guide.tribunal.session_view import SessionViewError, validate_document

    reg = ExhibitRegistry()
    Newsroom(FakeSearch(), now=lambda: NOW).collect(reg, "TSLA", "Tesla", ROBERT)
    ruling = {"verdict": "reject", "facts": [], "what_would_change": [], "disclaimers": [],
              "recent_context": web_context(reg)}
    doc = {"session_id": "s1", "status": "completed", "contract": None, "stage": "clerk", "stages_done": [],
           "active_agent": None, "exhibits": [], "verdict": None, "ruling": ruling, "rule_results": [],
           "sensitivity": [], "trace": [], "summaries": {}, "snapshot": None, "data_notices": [], "error": None}
    validate_document(doc)
    ruling["recent_context"] = [{"title": "no link"}]
    with pytest.raises(SessionViewError):
        validate_document(doc)


# --- news quality, from the live 2026-11-15 Tesla session ---------------------------------------
from guide.toolkit.web_evidence import MAX_PER_SOURCE, clean_snippet, is_informative, mentions_subject  # noqa: E402


def test_promotional_and_digest_headlines_are_dropped():
    for t in [
        "A 68-Year-Old Retiree Bought 1,000 Tesla Shares at $108 in January 2023. Now Musk Could Merge "
        "Tesla Into SpaceX by December, and a 15% Premium Would Turn Her Stake Into About 3,270 SpaceX Shares",
        "The Zacks Analyst Blog Highlights Tesla, SpaceX and Ford",
        "Tesla : The Tech Radar — Tesla",
        "If You'd Invested $1,000 in Tesla 10 Years Ago, Here's How Much You'd Have",
        "3 Stocks to Watch This Week: Tesla, Nvidia and Shopify",
    ]:
        assert not is_informative(t), t
    for t in ["SpaceX's S&P 500 Bid Gets New Life as Musk Pitches Tesla Merger",
              "Incoming Texas AG vows rigorous scrutiny of potential SpaceX-Tesla merger",
              "Tesla (TSLA) Breaks Ground On $10 Billion Texas Solar Factory As EU Approvals Advance"]:
        assert is_informative(t), t


def test_headline_must_name_the_asset():
    assert mentions_subject("Incoming Texas AG vows scrutiny of potential SpaceX-Tesla merger", "TSLA", "Tesla")
    assert mentions_subject("TSLA slips after delivery miss", "TSLA", "Tesla")
    assert mentions_subject("Exxon settles Gulf spill claims", "XOM", "Exxon Mobil")
    assert mentions_subject("Shopify adds AI checkout tools", "SHOP.TO", "Shopify Inc.")
    assert not mentions_subject("Fed holds rates steady as inflation cools", "TSLA", "Tesla")


def test_snippets_keep_sentences_and_drop_page_furniture():
    yahoo = ("Rates Commodities Currencies U.S. markets closed ADVERTISEMENT Trending Tesla (TSLA) Breaks "
             "-30.73 -0.40% -8.57 -0.31% ADVERTISEMENT Incoming Texas AG Ken Paxton said Thursday his office "
             "will closely review any proposed combination of SpaceX and Tesla.")
    assert clean_snippet(yahoo) == ("Incoming Texas AG Ken Paxton said Thursday his office will closely review "
                                    "any proposed combination of SpaceX and Tesla.")
    table = "| subject_name | Tesla | | subject_type | organization | | Answer | Tesla (TSLA): Shares rose"
    assert clean_snippet(table) == ""
    tickers = ("SPCX TSLA ^GSPC Explore stocks on Coinbase Trading disclosure (Bloomberg) -- Just months after "
               "SpaceX was denied a swift entry into the index, Elon Musk is pitching a merger with Tesla.")
    assert clean_snippet(tickers).startswith("(Bloomberg) -- Just months after SpaceX")
    plain = ("Tesla said on Thursday it would recall 12,000 Model Y vehicles in the U.S. over a seat-belt "
             "warning. Shares fell 2% in early trading.")
    assert clean_snippet(plain) == plain
    assert clean_snippet("word " * 200).endswith("…") and len(clean_snippet("word " * 200)) <= 301


def test_at_most_two_articles_per_source():
    results = [{"title": f"Tesla recall update number {i} from regulators", "url": f"https://finance.yahoo.com/{i}",
                "text": "Tesla said it would expand the recall to more vehicles in Canada this week."}
               for i in range(5)]
    results.append({"title": "Tesla recall widens to Canada, regulator says", "url": "https://www.reuters.com/x",
                    "text": "Transport Canada said the recall now covers vehicles built in 2025 and 2026."})
    found = Newsroom(FakeSearch(results), now=lambda: NOW).collect(ExhibitRegistry(), "TSLA", "Tesla", ROBERT)
    sources = [e.value["source"] for e in found]
    assert sources.count("finance.yahoo.com") == MAX_PER_SOURCE and "reuters.com" in sources


# --- second live run (runtime v16) ----------------------------------------------------------------
from guide.toolkit.web_evidence import _domain  # noqa: E402


def test_buy_questions_and_page_title_prefixes():
    assert not is_informative("Is Tesla Stock Worth Buying Now on Robotaxi & FSD Progress?")
    assert not is_informative("Tesla: Buy, Sell or Hold?")
    found = Newsroom(FakeSearch([{"title": "Tesla : Tesla and SpaceX Stock Selloff and Merger Exploration",
                                  "url": "https://www.morningstar.com/news/x",
                                  "text": "Shares in Tesla have risen 2% in premarket trading on Friday after a fall."}]),
                     now=lambda: NOW).collect(ExhibitRegistry(), "TSLA", "Tesla", ROBERT)
    assert found[0].value["title"] == "Tesla and SpaceX Stock Selloff and Merger Exploration"


def test_sources_are_sites_not_servers():
    assert _domain("https://ca.finance.yahoo.com/x") == "finance.yahoo.com"
    assert _domain("https://kessler-prod.reta52d8.eas.morningstar.com/x") == "morningstar.com"
    assert _domain("https://news.bbc.co.uk/a") == "bbc.co.uk"
    results = [{"title": f"Tesla recall widens again in report {i}", "url": f"https://{h}/r{i}",
                "text": "Tesla said it would expand the recall to more vehicles in Canada this week."}
               for i, h in enumerate(["finance.yahoo.com", "ca.finance.yahoo.com", "uk.finance.yahoo.com"])]
    found = Newsroom(FakeSearch(results), now=lambda: NOW).collect(ExhibitRegistry(), "TSLA", "Tesla", ROBERT)
    assert len(found) == MAX_PER_SOURCE


def test_bylines_datelines_and_cut_tails():
    s = ("Tesla reports Q3 earnings beat, positive free cash flow, and better-than-expected capex Pras Subramanian "
         "· Senior Reporter Wed, October at 6:01 PM. Tesla beat Wall Street estimates for third-quarter profit "
         "as cost cuts offset lower prices.")
    assert clean_snippet(s) == "Tesla beat Wall Street estimates for third-quarter profit as cost cuts offset lower prices."
    cut = ("(Bloomberg) -- Just months after SpaceX was denied a swift entry into the S&P 500 Index, Elon Musk "
           "may have found a backdoor: Merging with T")
    assert clean_snippet(cut).endswith("Merging with…")
