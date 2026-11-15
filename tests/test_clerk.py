from datetime import date, datetime, timezone

from guide.agents.clerk import CHANGE_SECTION_TITLE, build_ruling
from guide.data import quality
from guide.data.snapshot import SnapshotInfo
from guide.toolkit.exhibits import ExhibitRegistry
from guide.tribunal.rules import RuleRequest, RuleResult, Verdict
from guide.tribunal.sensitivity import SensitivityResult

SNAP = SnapshotInfo("snap-1", "s3", datetime(2026, 11, 12, tzinfo=timezone.utc),
                    date(2026, 11, 12), "primary", None)


def _build(esg=False, text=""):
    reg = ExhibitRegistry(SNAP)
    for _ in range(2):
        reg.add(metric="portfolio_metrics", value=1.0, period_start=date(2021, 11, 12),
                period_end=date(2026, 11, 12), assets=("TSLA",), currency="CAD",
                source_files=("prices_daily",), processing_notes=(), inputs={})
    req = RuleRequest("TSLA", 0.30, {"XBB.TO": 1.0}, date(2021, 11, 12), date(2026, 11, 12))
    contract = {"horizon_years": 4, "max_drawdown": 0.15, "crypto_cap": 0.02,
                "esg_exclusions": ["fossil_fuel_screen"] if esg else [],
                "provenance": {"max_drawdown": "persona_assumption", "crypto_cap": "persona_quoted"}}
    results = [RuleResult("max_drawdown", "fail", 0.30, 0.15, [1]),
               RuleResult("crypto_cap", "pass", 0.0, 0.02, [])]
    verdict = Verdict("accept_with_conditions", 0.05, ["max_drawdown"], [],
                      ["keeping TSLA at or below 5.0 %"], None, [1], "r")
    sens = [SensitivityResult("position_size", True, 0.05, "reject", "accept", 2, "At 5.0 % the verdict changes.")]
    return build_ruling(verdict=verdict, rule_results=results, sensitivity=sens, contract=contract,
                        request=req, registry=reg, snapshot=SNAP,
                        rationales={"max_drawdown": "Robert dislikes large losses"}, requested_text=text)


def test_sections_citations_and_disclaimers():
    r = _build()
    assert r.facts and all(f.citations for f in r.facts)
    assert any("simulation" in d for d in r.disclaimers)
    assert quality.survivorship_bias_text() in r.limits
    assert any("horizon" in l for l in r.limits)
    assert any("snap-1" in a and "2026-11-12" in a for a in r.assumptions)
    assert any("max_drawdown" in a and "Robert dislikes" in a for a in r.assumptions)
    assert not any("crypto_cap" in a for a in r.assumptions)
    assert all(s.startswith("Simulation") for s in r.fictional_scenarios)
    assert r.what_would_change[0].citations == (2,)
    assert any(s.text.startswith("You may wish to consider") for s in r.what_would_change)
    assert CHANGE_SECTION_TITLE in r.to_dict()


def test_unsupported_and_esg_notices():
    r = _build(esg=True, text="what do the news say?")
    joined = " ".join(r.limits)
    assert "news" in joined and "ESG scores" in joined


def test_four_answers_built_by_code_and_valid_in_session_view():
    import json
    from guide.tribunal.session_view import new_session_view, session_view_to_json, stage_finished

    r = _build(esg=True)
    d = r.to_dict()
    assert [q["heading"] for q in d["questions"]] == [
        "Which data?", "Why this choice?", "Which limits?", "What would change the answer?"]
    by = {q["id"]: q["statements"] for q in d["questions"]}
    assert any("prices_daily" in s["text"] and s["citations"] for s in by["which_data"])
    assert any("snap-1" in s["text"] for s in by["which_data"])
    assert any("max_drawdown" in s["text"] and s["citations"] == [1] for s in by["why_this_choice"])
    assert any(quality.survivorship_bias_text() == s["text"] for s in by["which_limits"])
    assert any(s["citations"] == [2] for s in by["what_would_change"])
    assert any("Appeal" in s["text"] and "max_drawdown" in s["text"] for s in by["what_would_change"])
    v = stage_finished(new_session_view("s1"), "clerk", ruling=d)
    assert json.loads(session_view_to_json(v))["ruling"]["questions"] == d["questions"]
