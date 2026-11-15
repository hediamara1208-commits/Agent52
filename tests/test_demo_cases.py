"""Demo cases (Req. 33.3): every expected Verdict in demo/cases.yaml, decided by code only."""
from __future__ import annotations

import pytest
import yaml

from tests.test_rules import _persona, _run, source  # noqa: F401  (source is a fixture)

with open("demo/cases.yaml", encoding="utf-8") as _f:
    DOC = yaml.safe_load(_f)

# (case id, patch, expected) including the Appeal as its own run
RUNS = []
for _c in DOC["cases"]:
    RUNS.append((_c["id"], _c, {}, _c["expected"]))
    if "appeal" in _c:
        _a = _c["appeal"]
        RUNS.append((_a["id"], _c, _a["contract_patch"], _a["expected"]))


def _run_case(case, patch, source):
    profile = case["profile"]
    req = case["request"]
    if profile in DOC["custom_profiles"]:
        cp = DOC["custom_profiles"][profile]
        contract, _ = _persona(cp["based_on"])
        base = cp["base_portfolio"]
        from datetime import date
        from guide.toolkit.exhibits import ExhibitRegistry
        from guide.trace.recorder import TraceRecorder
        from guide.tribunal import rules
        contract.update(patch)
        request = rules.RuleRequest(req["ticker"], req["weight"], base, date(2021, 11, 12), date(2026, 11, 12))
        reg = ExhibitRegistry()
        trace = TraceRecorder(emit_spans=False, max_summary_chars=400)
        results = rules.evaluate_rules(contract, request, reg, source=source, trace=trace)
        return results, rules.decide(results, contract, request, reg, source=source, trace=trace)
    results, verdict, _, _ = _run(profile, req["ticker"], req["weight"], source, patch)
    return results, verdict


def test_set_covers_accept_conditions_and_reject():
    verdicts = {e for _, _, _, exp in RUNS for e in [exp["verdict"]]}
    assert {"accept", "accept_with_conditions", "reject"} <= verdicts
    assert len(DOC["cases"]) == 5 and "canadian_heavy" in DOC["custom_profiles"]


@pytest.mark.parametrize("case_id,case,patch,expected", RUNS, ids=[r[0] for r in RUNS])
def test_expected_verdict_and_max_weight(case_id, case, patch, expected, source):  # noqa: F811
    results, v = _run_case(case, patch, source)
    assert v.verdict == expected["verdict"]
    if expected["max_weight"] is None:
        assert v.max_weight is None
    else:
        assert v.max_weight == pytest.approx(expected["max_weight"])
    if "failing_rules" in expected:
        failed = {r.rule for r in results if r.status == "fail"}
        assert failed == set(expected["failing_rules"])
