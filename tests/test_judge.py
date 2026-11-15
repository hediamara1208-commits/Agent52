"""Judge: schema, existence checks, and no-upgrade rule (Req. 29.2 to 29.4, 5.9)."""
from __future__ import annotations

import json
from datetime import date

import pytest

from guide.agents.base import StageFailure
from guide.agents.judge import apply_soft_preferences, check_assessments, parse_output
from guide.toolkit.exhibits import ExhibitRegistry
from guide.tribunal.rules import ACCEPT, ACCEPT_WITH_CONDITIONS, REJECT, Verdict

CONTRACT = {"soft_preferences": [{"id": "stable", "text": "I want a stable portfolio.", "provenance": "p"}]}


def _registry() -> ExhibitRegistry:
    reg = ExhibitRegistry()
    reg.add(
        metric="max_drawdown", value=-0.3, period_start=date(2021, 11, 12), period_end=date(2026, 11, 12),
        assets=("TSLA",), currency="CAD", source_files=("prices_daily",), processing_notes=(), inputs={},
    )
    return reg


def _item(option="o1", pref="stable", assessment="not_satisfied", exhibits=(1,)):
    return {"option_id": option, "preference_id": pref, "assessment": assessment,
            "findings": "f", "exhibits": list(exhibits)}


def _verdict(kind):
    return Verdict(kind, 0.1 if kind != REJECT else None, [], [], ["c"] if kind != ACCEPT else [], None, [1], "r")


def test_valid_assessment_kept_and_bad_ones_rejected():
    data = {"assessments": [_item(), _item(option="o2"), _item(pref="nope"), _item(exhibits=(9,))], "narrative": "n"}
    res = check_assessments(data, CONTRACT, _registry(), ["o1"])
    assert len(res.assessments) == 1
    assert len(res.rejected) == 3
    assert res.narrative == "n"


def test_not_satisfied_turns_accept_into_conditions():
    out = apply_soft_preferences(_verdict(ACCEPT), [_item()], "o1", CONTRACT)
    assert out.verdict == ACCEPT_WITH_CONDITIONS
    assert "stable portfolio" in out.conditions[-1]


@pytest.mark.parametrize("kind", [ACCEPT_WITH_CONDITIONS, REJECT])
@pytest.mark.parametrize("assessment", ["satisfied", "tension", "not_satisfied"])
def test_never_upgrades(kind, assessment):
    v = _verdict(kind)
    assert apply_soft_preferences(v, [_item(assessment=assessment)], "o1", CONTRACT) == v


def test_satisfied_or_other_option_leaves_accept():
    v = _verdict(ACCEPT)
    assert apply_soft_preferences(v, [_item(assessment="tension")], "o1", CONTRACT) == v
    assert apply_soft_preferences(v, [_item(option="o2")], "o1", CONTRACT) == v


def test_parse_output_rejects_bad_json_schema_and_enum():
    with pytest.raises(StageFailure):
        parse_output("nope")
    with pytest.raises(StageFailure):
        parse_output(json.dumps({"assessments": [_item(assessment="great")], "narrative": "n"}))
    decision = {"verdict": "reject", "option_id": None, "conditions": [], "reason": "r", "exhibits": [1]}
    with pytest.raises(StageFailure):  # a ruling without a decision is invalid
        parse_output(json.dumps({"assessments": [_item()], "narrative": "n"}))
    assert parse_output("```json\n" + json.dumps({"assessments": [_item()], "narrative": "n",
                                                    "decision": decision}) + "\n```")


def test_check_decision_applies_the_law():
    from guide.agents.judge import check_decision
    reg = ExhibitRegistry()
    options = [{"option_id": "request", "ticker": "TSLA", "weight": 0.3, "rejected": True, "failing_rules": ["per_asset_cap"]},
               {"option_id": "option_1", "ticker": "TSLA", "weight": 0.05, "rejected": False, "failing_rules": []}]

    def d(verdict, option):
        return {"verdict": verdict, "option_id": option, "conditions": [], "reason": "r", "exhibits": []}

    assert check_decision(d("accept_with_conditions", "option_1"), options, reg, "request") == []
    assert check_decision(d("reject", None), options, reg, "request") == []
    assert "breaks the Hard_Rules" in check_decision(d("accept", "request"), options, reg, "request")[0]
    assert "does not exist" in check_decision(d("accept_with_conditions", "zz"), options, reg, "request")[0]
    assert "accept means the request" in check_decision(d("accept", "option_1"), options, reg, "request")[0]
    assert check_decision(None, options, reg, "request") == ["the Judge returned no decision"]


def test_adopting_a_zero_size_option_is_a_rejection():
    from guide.agents.judge import verdict_from_decision
    from guide.tribunal.rules import Verdict
    facts = Verdict(verdict="accept_with_conditions", max_weight=None, failing_rules=["esg_exclusion"],
                    unverified_rules=[], conditions=[], tension="", exhibits=[1], reason="")
    options = [{"option_id": "option_3", "ticker": "XOM", "weight": 0.0}]
    v = verdict_from_decision({"verdict": "accept_with_conditions", "option_id": "option_3",
                               "conditions": ["Keep XOM out."], "reason": "Only 0% passes.", "exhibits": [1]},
                              options, facts)
    assert v.verdict == "reject" and v.max_weight is None and v.conditions == ["Keep XOM out."]
