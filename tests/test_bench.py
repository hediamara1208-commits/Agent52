"""Benchmark (Req. 34.1-34.3, 34.5): Wilson intervals, labels, budget guard, baseline arm. Fakes only."""
from datetime import date

import pytest
from hypothesis import given, strategies as st

from guide.bench import run as bench
from guide.bench.baseline import BASELINE_SYSTEM_PROMPT, BaselineAgent, parse_verdict
from guide.bench.stats import confidence_label, wilson_interval
from guide.config import Config


def _case(i, expected=("reject",), violates=True):
    return bench.Case(id=f"c{i}", ticker="TSLA", weight=0.3, expected=expected, violates_hard_rule=violates,
                      start=date(2020, 1, 1), end=date(2024, 1, 1), contract={"x": 1}, base_portfolio={"A": 1.0})


def _rec(verdict, calls=1, total=0, matched=0):
    return bench.RunRecord(verdict, 1.0, 100, total, matched, calls)


def test_wilson_known_values():
    lo, hi = wilson_interval(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    assert wilson_interval(0, 0) == (0.0, 1.0)
    lo, hi = wilson_interval(10, 10)
    assert hi == pytest.approx(1.0) and lo == pytest.approx(0.722, abs=1e-3)


@given(st.integers(0, 200).flatmap(lambda n: st.tuples(st.integers(0, n), st.just(n))))
def test_wilson_contains_rate_and_is_bounded(kn):
    k, n = kn
    lo, hi = wilson_interval(k, n)
    assert 0 <= lo <= hi <= 1
    if n:
        assert lo - 1e-12 <= k / n <= hi + 1e-12


def test_labels():
    assert confidence_label((50, 50), (0, 50)) == "Measured"
    assert confidence_label((5, 10), (4, 10)) == "Indicative"
    assert confidence_label((5, 10), None) == "Context"
    assert confidence_label((0, 0), (3, 10)) == "Context"


def test_budget_guard_asks_above_300_and_aborts_without_calls():
    cases = [_case(i) for i in range(10)]  # 10*8*4 = 320 > 300
    assert bench.planned_calls(10, 8) == 320
    calls = []
    out = []
    res = bench.run_benchmark(cases, 8, lambda c: calls.append(1), lambda c: calls.append(1),
                              confirm=lambda q: False, out=out.append)
    assert res is None and not calls
    assert "320" in out[0]


def test_budget_guard_no_prompt_at_or_below_300():
    asked = []
    assert bench.check_budget(10, 7, confirm=lambda q: asked.append(q) or False, out=lambda s: None)  # 280
    assert not asked


def test_call_count_guard_aborts_on_extra_model_calls():
    cases = [_case(1)]
    with pytest.raises(RuntimeError, match="guide arm used 4"):
        bench.run_benchmark(cases, 1, lambda c: _rec("reject", calls=4), lambda c: _rec("accept"), out=lambda s: None)
    with pytest.raises(RuntimeError, match="baseline arm used 2"):
        bench.run_benchmark(cases, 1, lambda c: _rec("reject", calls=3), lambda c: _rec("accept", calls=2),
                            out=lambda s: None)


def test_results_rates_labels_and_outputs(tmp_path):
    cases = [_case(i) for i in range(10)]
    res = bench.run_benchmark(
        cases, 5, lambda c: _rec("reject", calls=3, total=4, matched=4),
        lambda c: _rec("accept", total=4, matched=0), out=lambda s: None)
    g, b = res["overall"]["guide"], res["overall"]["baseline"]
    assert g["verdict_match"]["rate"] == 1.0 and b["verdict_match"]["rate"] == 0.0
    assert g["yes_man"]["rate"] == 0.0 and b["yes_man"]["rate"] == 1.0
    assert b["number_unverifiable"]["rate"] == 1.0
    assert res["labels"]["verdict_match"] == "Measured" and res["labels"]["latency_seconds"] == "Context"
    assert res["published"] is True
    js, md = bench.write_outputs(res, tmp_path)
    assert js.name == "benchmark.json" and "Measured" in md.read_text()


def test_yes_man_only_counts_violating_cases():
    c_ok = _case(1, expected=("accept",), violates=False)
    counts = bench.arm_counts([(c_ok, _rec("accept"))])
    assert counts["yes_man"] == (0, 0)


def test_count_numbers_matches_exhibit_values():
    total, matched = bench.count_numbers("Vol is 18.2% and drawdown 0.35, plus 99", [{"value": {"v": 0.182, "d": 0.35}}])
    assert (total, matched) == (3, 2)


def test_load_cases(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text("cases:\n- {id: a, ticker: XOM, weight: 0.1, expected: reject, violates_hard_rule: true,"
                 " start: 2020-01-01, end: 2024-01-01, persona: mateo}\n")
    (case,) = bench.load_cases([f])
    assert case.expected == ("reject",) and case.end == date(2024, 1, 1)


class FakeClient:
    def __init__(self, text="Too risky. VERDICT: reject"):
        self.requests = []
        self.text = text

    def converse(self, **kw):
        self.requests.append(kw)
        return {"output": {"message": {"role": "assistant", "content": [{"text": self.text}]}},
                "stopReason": "end_turn", "usage": {"totalTokens": 42}}


def test_baseline_agent_one_call_no_tools_with_guardrail():
    cfg = Config(s3_bucket="b", model_id="m", guardrail_id="g", guardrail_version="1")
    client = FakeClient()
    res = BaselineAgent(cfg, client=client).run({"risk_level": "high"}, "30% TSLA")
    (req,) = client.requests
    assert "toolConfig" not in req and req["guardrailConfig"]["guardrailIdentifier"] == "g"
    assert req["system"][0]["text"] == BASELINE_SYSTEM_PROMPT and req["modelId"] == "m"
    assert '"risk_level": "high"' in req["messages"][0]["content"][0]["text"]
    assert (res.verdict, res.tokens, res.calls) == ("reject", 42, 1)


def test_baseline_requires_guardrail():
    with pytest.raises(ValueError):
        BaselineAgent(Config(s3_bucket="b", model_id="m"), client=FakeClient())


def test_parse_verdict():
    assert parse_verdict("I would accept with conditions.\nVERDICT: accept_with_conditions") == "accept_with_conditions"
    assert parse_verdict("no idea") == "unclear"
