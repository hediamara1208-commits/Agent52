"""Base_Portfolio in the Persona_File and contract.portfolio.propose (Req. 28.1, 28.2)."""
import csv
import math
from pathlib import Path

import pytest

from guide.contract.personas import load_personas
from guide.contract.portfolio import propose

UNIVERSE = Path(__file__).resolve().parents[1] / "data" / "assets_universe.csv"


def _tickers() -> set[str]:
    with UNIVERSE.open(encoding="utf-8") as f:
        return {r["ticker"] for r in csv.DictReader(f)}


@pytest.mark.parametrize("pid", ["amira", "mateo", "robert"])
def test_shipped_base_portfolio(pid):
    result = load_personas()
    assert not result.field_errors
    cv = result.personas[pid].contract_values["base_portfolio"]
    assert cv.basis == "assumption" and cv.rationale
    assert math.isclose(sum(cv.value.values()), 1.0, abs_tol=1e-9)
    assert set(cv.value) <= _tickers()


def test_robert_weights():
    cv = load_personas().personas["robert"].contract_values["base_portfolio"]
    assert cv.value == {"XBB.TO": 0.40, "ZST.TO": 0.15, "XIU.TO": 0.15, "SPY": 0.15, "JNJ": 0.08, "RY.TO": 0.07}


def test_mateo_esg_exclusion():
    cv = load_personas().personas["mateo"].contract_values["esg_exclusions"]
    assert cv.value == ["fossil_fuel_screen"] and cv.basis == "assumption"


def test_propose_new_asset():
    out = propose({"A": 0.6, "B": 0.4}, "TSLA", 0.3)
    assert out == pytest.approx({"A": 0.42, "B": 0.28, "TSLA": 0.3})
    assert sum(out.values()) == pytest.approx(1.0)


def test_propose_held_asset_adds_weight():
    out = propose({"A": 0.6, "B": 0.4}, "A", 0.1)
    assert out["A"] == pytest.approx(0.6 * 0.9 + 0.1)
    assert sum(out.values()) == pytest.approx(1.0)


def test_propose_does_not_mutate_base():
    base = {"A": 1.0}
    propose(base, "B", 0.5)
    assert base == {"A": 1.0}


def test_propose_rejects_bad_weight():
    with pytest.raises(ValueError):
        propose({"A": 1.0}, "B", 1.5)
