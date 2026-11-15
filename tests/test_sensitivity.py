"""Sensitivity_Analysis: thresholds flip the Verdict when applied (Req. 6.5 to 6.7, 10.8)."""
from __future__ import annotations

from dataclasses import replace

from guide.toolkit.exhibits import ExhibitRegistry
from guide.tribunal import rules, sensitivity
from tests.test_rules import END, START, _persona, source  # noqa: F401  (fixture)


def _analyse(source, pid, ticker, weight):
    contract, base = _persona(pid)
    request = rules.RuleRequest(ticker, weight, base, START, END)
    reg = ExhibitRegistry()
    res = rules.evaluate_rules(contract, request, reg, source=source)
    return contract, request, sensitivity.run_sensitivity(contract, request, res, reg, source=source), reg


def test_position_size_threshold_flips_verdict(source):
    contract, request, out, reg = _analyse(source, "amira", "TSLA", 0.30)
    size = out[0]
    assert size.changed and size.threshold == 0.15
    at = replace(request, weight=size.threshold)
    results = rules.evaluate_rules(contract, at, ExhibitRegistry(), source=source)
    assert rules.decide(results, contract, at, ExhibitRegistry(), source=source).verdict == rules.ACCEPT
    assert size.verdict_at_threshold == rules.ACCEPT


def test_horizon_reports_no_change_and_every_result_is_an_exhibit(source):
    _, _, out, reg = _analyse(source, "robert", "TSLA", 0.30)
    horizon = next(r for r in out if r.variable == "horizon_years")
    assert not horizon.changed and horizon.threshold == sensitivity.NO_CHANGE
    for r in out:
        assert reg.get(r.exhibit).metric == "sensitivity"


def test_accepted_request_reports_size_threshold_above(source):
    _, request, out, _ = _analyse(source, "robert", "SPY", 0.02)
    size = out[0]
    assert (not size.changed) or size.threshold > request.weight
