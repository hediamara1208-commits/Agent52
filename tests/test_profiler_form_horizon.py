"""Web form horizon fields (horizon_min / horizon_max) map to horizon_years and horizon_range."""
import pytest

from guide.contract.personas import SHIPPED_PATH, load_personas
from guide.contract.profiler import build_contract_from_form
from guide.contract.validate import validate_contract

FORM = {"risk_level": "low_to_moderate", "max_volatility": 0.12, "max_drawdown": 0.15,
        "per_asset_cap": 0.1, "crypto_cap": 0.02, "esg_exclusions": []}


@pytest.mark.parametrize("lo, hi, persona, years, rng", [
    (3, 5, "robert", 3, {"min": 3, "max": 5}),
    (15, None, "amira", 15, {"min": 15}),
    (7, 7, None, 7, {"min": 7, "max": 7}),
])
def test_form_horizon_fields_build_a_valid_contract(lo, hi, persona, years, rng):
    base = load_personas(SHIPPED_PATH).personas[persona] if persona else None
    contract = build_contract_from_form({**FORM, "horizon_min": lo, "horizon_max": hi}, base)
    assert validate_contract(contract) == []
    assert contract["horizon_years"] == years
    assert contract["horizon_range"] == rng
    assert "horizon_min" not in contract and "horizon_max" not in contract


def test_empty_form_horizon_keeps_the_persona_horizon():
    base = load_personas(SHIPPED_PATH).personas["mateo"]
    contract = build_contract_from_form({**FORM, "horizon_min": None, "horizon_max": None}, base)
    assert validate_contract(contract) == []
    assert contract["horizon_range"] == {"min": 8, "max": 12}


def test_blank_form_fields_keep_persona_or_default_values():
    robert = load_personas(SHIPPED_PATH).personas["robert"]
    blank = {"risk_level": "low_to_moderate", "horizon_min": None, "horizon_max": None, "max_volatility": None,
             "max_drawdown": None, "per_asset_cap": None, "crypto_cap": None, "esg_exclusions": []}
    with_persona = build_contract_from_form(blank, robert)
    assert validate_contract(with_persona) == []
    assert with_persona["max_volatility"] == 0.12 and with_persona["crypto_cap"] == 0.02
    no_persona = build_contract_from_form({**blank, "risk_level": "moderate"}, None)
    assert validate_contract(no_persona) == []
    assert no_persona["max_volatility"] == 0.20
