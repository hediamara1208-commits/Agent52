"""Investigator: schema validation and existence checks of Exhibits and contract fields (Req. 4.4, 4.5)."""
from __future__ import annotations

import json
from datetime import date

import pytest

from guide.agents.base import StageFailure
from guide.agents.investigator import check_findings, contract_field_names, parse_output
from guide.toolkit.exhibits import ExhibitRegistry

CONTRACT = {
    "risk_level": "low_to_moderate",
    "sector_caps": {"Technology": 0.2},
    "soft_preferences": [{"id": "stable", "text": "t", "provenance": "persona_quoted"}],
}


def _registry() -> ExhibitRegistry:
    reg = ExhibitRegistry()
    reg.add(
        metric="max_drawdown", value=-0.3, period_start=date(2021, 11, 12), period_end=date(2026, 11, 12),
        assets=("TSLA",), currency="CAD", source_files=("prices_daily",), processing_notes=(), inputs={},
    )
    return reg


def _risk(exhibits=(1,), fields=("max_drawdown",)):
    return {"risk": "r", "exhibits": list(exhibits), "why_for_this_person": "w", "contract_fields": list(fields)}


def _data(*risks):
    return {"per_option": [{"option_id": "o1", "material_risks": list(risks)}]}


def test_valid_risk_is_kept():
    res = check_findings(_data(_risk(fields=("sector_caps.Technology", "stable"))), CONTRACT, _registry(), ["o1"])
    assert not res.rejected
    assert len(res.per_option[0]["material_risks"]) == 1


def test_unknown_field_and_missing_exhibit_are_rejected():
    res = check_findings(_data(_risk(fields=("made_up",)), _risk(exhibits=(9,))), CONTRACT, _registry(), ["o1"])
    assert res.per_option[0]["material_risks"] == []
    assert len(res.rejected) == 2
    assert "made_up" in res.rejected[0].reasons[0]
    assert "Exhibit 9" in res.rejected[1].reasons[0]


def test_unknown_option_is_rejected():
    res = check_findings(_data(_risk()), CONTRACT, _registry(), ["other"])
    assert res.rejected


def test_field_names_include_soft_preference_ids():
    names = contract_field_names(CONTRACT)
    assert {"max_drawdown", "stable", "sector_caps.Technology"} <= names
    assert "provenance" not in names


def test_parse_output_rejects_bad_json_and_schema():
    with pytest.raises(StageFailure):
        parse_output("not json")
    with pytest.raises(StageFailure):
        parse_output(json.dumps({"per_option": [{"option_id": "o1"}]}))
    assert parse_output("```json\n" + json.dumps(_data(_risk())) + "\n```")["per_option"]
