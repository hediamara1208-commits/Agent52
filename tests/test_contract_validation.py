"""Tests for Investor_Contract JSON schema validation."""
from __future__ import annotations

from copy import deepcopy

import pytest

from guide.contract.validate import FieldError, validate_contract


VALID_CONTRACT = {
    "risk_level": "low_to_moderate",
    "horizon_years": 3,
    "max_volatility": 0.12,
    "max_drawdown": 0.15,
    "per_asset_cap": 0.10,
    "per_asset_class_caps": {"equity": 0.75, "crypto": 0.02},
    "crypto_cap": 0.02,
    "sector_caps": {"Information Technology": 0.25},
    "esg_exclusions": ["XOM"],
    "speculative_limit": 0.05,
    "provenance": {
        "risk_level": "persona_quoted",
        "horizon_years": "persona_quoted",
        "max_volatility": "persona_assumption",
        "max_drawdown": "persona_assumption",
        "per_asset_cap": "persona_assumption",
        "per_asset_class_caps": "persona_assumption",
        "crypto_cap": "persona_assumption",
        "sector_caps": "persona_assumption",
        "esg_exclusions": "persona_quoted",
        "speculative_limit": "persona_assumption",
    },
}


def test_validate_contract_returns_empty_list_for_valid_contract():
    assert validate_contract(VALID_CONTRACT) == []


@pytest.mark.parametrize(
    ("field", "value", "expected_path"),
    [
        ("risk_level", "cautious", "risk_level"),
        ("horizon_years", 0, "horizon_years"),
        ("max_drawdown", 1.01, "max_drawdown"),
        ("sector_caps", {"Information Technology": -0.01}, "sector_caps.Information Technology"),
    ],
)
def test_validate_contract_reports_invalid_field(field, value, expected_path):
    contract = deepcopy(VALID_CONTRACT)
    contract[field] = value

    errors = validate_contract(contract)

    assert all(isinstance(error, FieldError) for error in errors)
    assert expected_path in {error.field for error in errors}


def test_validate_contract_reports_missing_required_field():
    contract = deepcopy(VALID_CONTRACT)
    del contract["speculative_limit"]

    errors = validate_contract(contract)

    assert "speculative_limit" in {error.field for error in errors}


def test_validate_contract_requires_provenance_for_every_contract_field():
    contract = deepcopy(VALID_CONTRACT)
    del contract["provenance"]["crypto_cap"]

    errors = validate_contract(contract)

    assert "provenance.crypto_cap" in {error.field for error in errors}


def test_validate_contract_reports_non_object_contract():
    assert validate_contract([]) == [
        FieldError("<contract>", "contract must be a JSON object")
    ]
