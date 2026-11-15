"""Risk_Panel tests on the starter data (Robert, 30 % TSLA)."""
from __future__ import annotations

from datetime import date

import pytest

from guide.data.loader import LocalSource
from guide.toolkit import risk_panel as rp
from guide.toolkit.exhibits import ExhibitRegistry
from guide.toolkit.metrics import ToolError
from tests.test_metrics import _Source
from tests.test_rules import _persona

START, END = date(2021, 11, 12), date(2026, 11, 12)


@pytest.fixture(scope="module")
def source():
    local = LocalSource()
    names = ["assets_universe", "prices_daily", "fx_usdcad_daily", "esg_exclusions"]
    return _Source({n: local.read_csv(f"{n}.csv") for n in names}, END)


def _panel(source, weight=0.30):
    contract, base = _persona("robert")
    contract["base_portfolio"] = base
    option = {"id": "o1", "ticker": "TSLA", "weight": weight, "start": START, "end": END}
    reg = ExhibitRegistry()
    return rp.risk_panel(option, contract, registry=reg, source=source), reg


def test_fixed_exhibit_set_and_oracle(source):
    panel, reg = _panel(source)
    assert tuple(panel.items) == rp.PANEL_KEYS and not panel.errors
    assert len(reg.all()) == len(rp.PANEL_KEYS)
    comp = panel.items["portfolio_comparison"].value["proposed"]
    assert comp["annualized_volatility"] == pytest.approx(0.201, abs=0.003)
    share = panel.items["risk_contribution"].value["share_of_variance_pct"]["TSLA"]
    assert share == pytest.approx(86.7, abs=1.0)
    usd = panel.items["currency_exposure"].value
    assert usd["base"]["USD"] == pytest.approx(0.23)
    assert usd["proposed"]["USD"] == pytest.approx(0.461, abs=1e-3)
    assert sum(panel.items["sector_weights"].value["proposed"].values()) == pytest.approx(1.0)
    assert -1 <= panel.items["correlation_with_base"].value <= 1
    assert panel.items["max_weight_within_contract"].value["max_weight"] == 0.05


def test_invalid_option_creates_no_exhibit(source):
    contract, base = _persona("robert")
    contract["base_portfolio"] = base
    reg = ExhibitRegistry()
    out = rp.risk_panel({"ticker": "NOPE", "weight": 0.1, "start": START, "end": END},
                        contract, registry=reg, source=source)
    assert isinstance(out, ToolError) and not reg.all()
