"""Rule_Engine tests: the expected Verdicts of the design table "Demo cases"."""
from __future__ import annotations

from datetime import date

import pytest
import yaml

from guide.data.loader import LocalSource
from guide.toolkit.exhibits import ExhibitRegistry
from guide.trace.recorder import TraceRecorder
from guide.tribunal import rules
from tests.test_metrics import _Source

START, END = date(2021, 11, 12), date(2026, 11, 12)


@pytest.fixture(scope="module")
def source():
    local = LocalSource()
    names = ["assets_universe", "prices_daily", "fx_usdcad_daily", "esg_exclusions"]
    return _Source({n: local.read_csv(f"{n}.csv") for n in names}, END)


def _persona(pid: str) -> tuple[dict, dict]:
    with open("guide/contract/personas.yaml", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    entry = next(p for p in doc["personas"] if p["id"] == pid)
    cv = entry["contract_values"] if "contract_values" in entry else entry
    values = {k: v["value"] for k, v in cv.items() if isinstance(v, dict) and "value" in v}
    contract = {"risk_level": entry["risk_level"], **{k: v for k, v in values.items() if k != "base_portfolio"}}
    return contract, values["base_portfolio"]


def _run(pid, ticker, weight, source, contract_patch=None):
    contract, base = _persona(pid)
    contract.update(contract_patch or {})
    request = rules.RuleRequest(ticker, weight, base, START, END)
    reg = ExhibitRegistry()
    trace = TraceRecorder(emit_spans=False, max_summary_chars=400)
    results = rules.evaluate_rules(contract, request, reg, source=source, trace=trace)
    verdict = rules.decide(results, contract, request, reg, source=source, trace=trace)
    return results, verdict, trace, reg


def test_robert_tsla_speculative_limit_binds(source):
    results, v, trace, reg = _run("robert", "TSLA", 0.30, source)
    failed = {r.rule for r in results if r.status == "fail"}
    assert {"max_volatility", "max_drawdown", "per_asset_cap", "speculative_limit"} <= failed
    assert (v.verdict, v.max_weight) == (rules.ACCEPT_WITH_CONDITIONS, 0.05)
    assert v.tension and "per-asset cap" in v.tension
    assert len(trace.events) >= len(results)
    assert all(reg.get(n) for n in v.exhibits)


def test_robert_appeal_per_asset_cap_binds_next(source):
    _, v, _, _ = _run("robert", "TSLA", 0.30, source, {"speculative_limit": 0.10})
    assert (v.verdict, v.max_weight) == (rules.ACCEPT_WITH_CONDITIONS, 0.10)


def test_amira_tsla(source):
    _, v, _, _ = _run("amira", "TSLA", 0.30, source)
    assert (v.verdict, v.max_weight) == (rules.ACCEPT_WITH_CONDITIONS, 0.15)
    assert v.tension is None


def test_amira_btc_crypto_cap_with_existing_holding(source):
    _, v, _, _ = _run("amira", "BTC-USD", 0.40, source)
    assert (v.verdict, v.max_weight) == (rules.ACCEPT_WITH_CONDITIONS, 0.055)


def test_mateo_xom_rejected_by_esg(source):
    results, v, _, _ = _run("mateo", "XOM", 0.10, source)
    assert next(r for r in results if r.rule == "esg_exclusion").status == "fail"
    assert v.verdict == rules.REJECT and v.max_weight is None


def test_compliant_request_is_accepted(source):
    _, v, _, _ = _run("robert", "SPY", 0.02, source)
    assert v.verdict == rules.ACCEPT and v.max_weight == 0.02


def test_missing_esg_table_is_unverified_not_pass(source):
    local = LocalSource()
    names = ["assets_universe", "prices_daily", "fx_usdcad_daily"]
    src = _Source({n: local.read_csv(f"{n}.csv") for n in names}, END)
    results, v, _, _ = _run("mateo", "XOM", 0.10, src)
    assert next(r for r in results if r.rule == "esg_exclusion").status == "unverified"
    assert "esg_exclusion" in v.unverified_rules


def test_exclusion_cost_picks_same_class_non_excluded_replacement(source):
    from guide.toolkit import metrics
    reg = ExhibitRegistry()
    ex = metrics.exclusion_cost(reg, source, "XOM", START, END)
    assert not isinstance(ex, metrics.ToolError)
    v = ex.value
    assert v["excluded"] == "XOM" and v["replacement"] not in ("XOM", "ENB.TO", "CNQ.TO")
    assert reg.get(v["correlation_exhibit"]).metric == "correlation"
    assert abs(v["return_cost"] - (v["excluded_annualized_return"] - v["replacement_annualized_return"])) < 1e-12
    assert "esg_exclusions" in ex.source_files


def test_exclusion_cost_rejects_asset_not_on_list(source):
    from guide.toolkit import metrics
    reg = ExhibitRegistry()
    err = metrics.exclusion_cost(reg, source, "MSFT", START, END)
    assert isinstance(err, metrics.ToolError) and err.code == metrics.INVALID_ARGUMENT
