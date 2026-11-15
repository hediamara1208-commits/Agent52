from datetime import date

from guide.toolkit.exhibits import ExhibitRegistry
from guide.tribunal.citations import Claim, NumberRef, enforce, validate_claim


def _registry():
    reg = ExhibitRegistry()
    reg.add(metric="vol", value={"vol": 0.20123}, period_start=date(2021, 11, 12),
            period_end=date(2026, 11, 12), assets=("TSLA",), currency="CAD",
            source_files=("prices_daily@x",), processing_notes=(), inputs={})
    return reg


def test_valid_claim_rounds_to_stated_decimals():
    c = Claim("vol 20.1%", [1], [NumberRef(0.201, 1, "vol", 3)])
    assert validate_claim(c, _registry()) == []


def test_invalid_claims():
    reg = _registry()
    assert validate_claim(Claim("x", []), reg)[0].code == "no_citation"
    assert validate_claim(Claim("x", [9]), reg)[0].code == "unknown_exhibit"
    bad = Claim("x", [1], [NumberRef(0.3, 1, "vol", 3)])
    assert validate_claim(bad, reg)[0].code == "number_mismatch"


def test_enforce_revises_then_removes():
    reg = _registry()
    bad = Claim("bad", [1], [NumberRef(0.3, 1, "vol", 3)])
    calls = []

    def revise(claim, issues):
        calls.append(1)
        return claim

    kept, events = enforce("advocate", [bad, Claim("ok", [1])], reg, revise=revise)
    assert [c.text for c in kept] == ["ok"]
    assert len(calls) == 2
    assert [e.kind for e in events] == ["claim_removed"]


def test_enforce_accepts_fixed_revision():
    reg = _registry()
    bad = Claim("bad", [])
    kept, events = enforce("investigator", [bad], reg, revise=lambda c, i: Claim("fixed", [1]))
    assert [c.text for c in kept] == ["fixed"] and events == []
