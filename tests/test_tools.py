"""Tests for Converse tool specs and the tool runner."""
from __future__ import annotations

from datetime import date

import pytest

from guide.toolkit.exhibits import ExhibitRegistry
from guide.toolkit.tools import ToolRunner, tool_config
from tests.test_metrics import _small_source


def _use(name, **args):
    return {"toolUseId": "t1", "name": name, "input": args}


def test_specs_hide_bound_parameters_and_list_required_inputs():
    specs = {s["toolSpec"]["name"]: s["toolSpec"] for s in tool_config()["tools"]}
    assert set(specs) == {
        "annualized_return", "annualized_volatility", "max_drawdown",
        "correlation", "drawdown_in_period", "portfolio_metrics",
        "risk_contribution", "portfolio_comparison", "max_weight_within_contract",
    }
    schema = specs["correlation"]["inputSchema"]["json"]
    assert schema["required"] == ["ticker_a", "ticker_b", "start", "end"]
    for spec in specs.values():
        props = spec["inputSchema"]["json"]["properties"]
        assert not {"registry", "source", "as_of"} & set(props)


def test_runner_returns_exhibit_number_and_value():
    reg = ExhibitRegistry()
    runner = ToolRunner(reg, _small_source(), as_of=date(2025, 1, 1))
    res = runner(_use("annualized_return", ticker="AAA.TO", start="2024-01-01", end="2025-01-01"))
    assert res["status"] == "success" and res["exhibit_number"] == 1
    payload = res["content"][0]["json"]
    assert payload["value"] == pytest.approx(1.01 ** 252 - 1)
    assert len(reg) == 1


def test_runner_errors_create_no_exhibit():
    reg = ExhibitRegistry()
    runner = ToolRunner(reg, _small_source())
    bad = [
        _use("annualized_return", ticker="ZZZ", start="2024-01-01", end="2025-01-01"),
        _use("annualized_return", ticker="AAA.TO", start="nope", end="2025-01-01"),
        _use("annualized_return", ticker="AAA.TO"),
        _use("annualized_return", ticker="AAA.TO", start="2024-01-01", end="2025-01-01", as_of="2020-01-01"),
        _use("place_order", ticker="AAA.TO"),
    ]
    for use in bad:
        assert runner(use)["status"] == "error"
    assert len(reg) == 0


def test_runner_handles_portfolio_weights_and_period_range():
    reg = ExhibitRegistry()
    runner = ToolRunner(reg, _small_source())
    res = runner(_use("portfolio_metrics", weights={"AAA.TO": 0.5, "BBB.TO": 0.5},
                      start="2024-01-01", end="2025-01-01"))
    assert res["status"] == "success"
    res = runner(_use("drawdown_in_period", ticker="BBB.TO", period_name_or_range=["2024-01-01", "2025-01-01"]))
    assert res["status"] == "success" and res["exhibit_number"] == 2


def test_new_tool_specs_hide_session_bound_contract():
    from guide.toolkit.tools import tool_specs

    specs = {s["toolSpec"]["name"]: s["toolSpec"]["inputSchema"]["json"] for s in tool_specs()}
    for name in ("risk_contribution", "portfolio_comparison", "max_weight_within_contract"):
        assert name in specs
    assert "contract" not in specs["max_weight_within_contract"]["properties"]
    assert set(specs["portfolio_comparison"]["required"]) == {"base", "proposed", "start", "end"}
