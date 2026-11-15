"""Tests for the Persona_File loader and the Profiler (tasks 2.2)."""
from __future__ import annotations

from pathlib import Path

import pytest

from guide.contract.personas import PersonaFileError, SHIPPED_PATH, load_personas
from guide.contract.profiler import (
    build_contract_from_form,
    build_contract_from_persona,
    validate_contract,
    validate_contract_for_persona,
)

CONTEXT = Path(__file__).resolve().parents[1] / "data" / "context.md"


@pytest.fixture(scope="module")
def personas():
    result = load_personas(SHIPPED_PATH)
    assert result.field_errors == ()
    return result.personas


def test_shipped_file_has_three_templates_and_quoted_excerpts_match_context(personas):
    assert list(personas) == ["amira", "mateo", "robert"]
    context = CONTEXT.read_text(encoding="utf-8")
    for p in personas.values():
        items = [*p.facts.values(), *p.contract_values.values()]
        for item in items:
            ex = item.excerpt
            for text in ([ex] if isinstance(ex, str) else ex or []):
                assert text in context, (p.id, text)
        for name, cv in p.contract_values.items():
            assert cv.basis and cv.rationale, (p.id, name)
            if cv.basis == "quoted":
                assert cv.excerpt, (p.id, name)


@pytest.mark.parametrize("pid", ["amira", "mateo", "robert"])
def test_template_contracts_are_valid_and_meet_persona_limits(personas, pid):
    c = build_contract_from_persona(personas[pid])
    assert validate_contract(c) == []
    assert validate_contract_for_persona(c, pid) == []


def test_provenance_follows_basis(personas):
    c = build_contract_from_persona(personas["robert"])
    assert c["provenance"]["risk_level"] == "persona_quoted"
    assert c["provenance"]["horizon_years"] == "persona_quoted"
    assert c["provenance"]["crypto_cap"] == "persona_assumption"
    assert c["horizon_years"] == 3 and c["horizon_range"] == {"min": 3, "max": 5}


def test_form_edit_marks_only_changed_fields_as_user(personas):
    c = build_contract_from_form({"max_drawdown": 0.2, "crypto_cap": 0.02}, base=personas["robert"])
    assert c["provenance"]["max_drawdown"] == "user"
    assert c["provenance"]["crypto_cap"] == "persona_assumption"  # unchanged value
    assert validate_contract(c) == []
    assert validate_contract_for_persona(c, "robert") == []  # edited: no persona rule


def test_blank_form_uses_form_and_default_provenance():
    c = build_contract_from_form({"risk_level": "low", "horizon": {"min": 5, "max": 7}})
    assert c["horizon_years"] == 5 and c["horizon_range"] == {"min": 5, "max": 7}
    assert c["provenance"]["risk_level"] == "form"
    assert c["provenance"]["horizon_years"] == "form"
    assert c["provenance"]["max_volatility"] == "default"
    assert validate_contract(c) == []


def test_unedited_template_violation_is_reported(personas):
    c = build_contract_from_persona(personas["mateo"])
    c["esg_exclusions"] = []
    assert [e.field for e in validate_contract_for_persona(c, "mateo")] == ["esg_exclusions"]


def test_loader_is_tolerant(tmp_path, personas):
    path = tmp_path / "p.yaml"
    path.write_text(
        "personas:\n"
        "  - {id: x, display_name: X, risk_level: low, horizon: 4, contract_values: {}}\n"
        "  - id: amira\n    display_name: A\n    risk_level: high\n    horizon: 15\n"
        "    contract_values:\n"
        "      horizon_years: {value: 15}\n      max_volatility: {value: 2}\n"
        "      max_drawdown: {value: 0.4}\n      per_asset_cap: {value: 0.1}\n"
        "      per_asset_class_caps: {value: {}}\n      sector_caps: {value: {}}\n"
        "      crypto_cap: {value: 0.1}\n      esg_exclusions: {value: []}\n",
        encoding="utf-8",
    )
    result = load_personas(path)
    assert result.personas == {}
    assert ("x", "contract_values.crypto_cap") in result.field_errors
    assert ("amira", "contract_values.max_volatility") in result.field_errors


def test_unparsable_or_missing_file_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("personas: [", encoding="utf-8")
    with pytest.raises(PersonaFileError):
        load_personas(bad)
    with pytest.raises(PersonaFileError):
        load_personas(tmp_path / "missing.yaml")


@pytest.mark.parametrize("pid", ["amira", "mateo", "robert"])
def test_template_soft_preferences_are_verbatim_and_in_contract(personas, pid):
    """Req. 29.1: at least two Soft_Preferences per template, excerpts verbatim from context.md."""
    context = CONTEXT.read_text(encoding="utf-8")
    c = build_contract_from_persona(personas[pid])
    prefs = c["soft_preferences"]
    assert len(prefs) >= 2
    assert len({p["id"] for p in prefs}) == len(prefs)
    for p in prefs:
        assert p["provenance"] == "persona_quoted"
        assert p["excerpt"] in context
    assert validate_contract(c) == []


def test_form_soft_preferences_default_to_form_provenance_and_validate():
    c = build_contract_from_form({"soft_preferences": [{"id": "x", "text": "Prefers dividends."}]})
    assert c["soft_preferences"][0]["provenance"] == "form"
    assert validate_contract(c) == []
    c["soft_preferences"][0]["id"] = "bad id"
    assert [e.field for e in validate_contract(c)] == ["soft_preferences.0.id"]
