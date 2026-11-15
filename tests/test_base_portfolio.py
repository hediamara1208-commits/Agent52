"""Custom Base_Portfolio: the investor's own holdings (National Bank example: 'my portfolio is
very Canadian, would SPY improve diversification?')."""
from __future__ import annotations

import pytest

from api.handler import Deps, handler
from guide.contract.base_portfolio import BasePortfolioError, split_profile, validate_base_portfolio
from guide.session.store import InMemorySessionStore
from runtime import app as rt
from tests.test_api_handler import UNIVERSE as API_UNIVERSE, FakeRuntime, call
from tests.test_orchestrator import source  # noqa: F401  (fixture)
from tests.test_runtime_app import _deps, _payload

CANADIAN = {"XIU.TO": 40, "RY.TO": 15, "TD.TO": 10, "ENB.TO": 10, "XBB.TO": 25}
UNIVERSE = {"XIU.TO", "RY.TO", "TD.TO", "ENB.TO", "XBB.TO", "SPY", "TSLA"}


def test_percent_or_fraction_weights_are_normalised():
    a = validate_base_portfolio(CANADIAN, UNIVERSE)
    b = validate_base_portfolio({k: v / 100 for k, v in CANADIAN.items()}, UNIVERSE)
    assert a == pytest.approx(b) and sum(a.values()) == pytest.approx(1.0)
    assert a["XIU.TO"] == pytest.approx(0.40)
    assert validate_base_portfolio({"xiu.to": 0.5, "XBB.TO": 0.505}, UNIVERSE)["XIU.TO"] == pytest.approx(0.5 / 1.005)


@pytest.mark.parametrize("raw, words", [
    ({}, "map tickers"),
    ([("SPY", 1)], "map tickers"),
    ({"SPY": 0.5, "XBB.TO": 0.2}, "sum to 100%"),
    ({"SPY": -0.5, "XBB.TO": 1.5}, "positive"),
    ({"SPY": True}, "positive"),
    ({"SPY": 0.5, "ZZZ": 0.5}, "not in the assets universe: ZZZ"),
])
def test_unusable_portfolios_are_refused_with_a_reason(raw, words):
    with pytest.raises(BasePortfolioError, match=words):
        validate_base_portfolio(raw, UNIVERSE)


def test_split_profile_takes_the_base_out_of_the_contract_values():
    values, raw = split_profile({"values": {"max_volatility": 0.1, "base_portfolio": {"SPY": 1}}})
    assert values == {"max_volatility": 0.1} and raw == {"SPY": 1}
    assert split_profile({"base_portfolio": {"SPY": 1}, "values": {}}) == ({}, {"SPY": 1})


def _api():
    universe = API_UNIVERSE | set(CANADIAN)
    return Deps(store=InMemorySessionStore(), runtime=FakeRuntime(), runtime_arn="arn:test",
                cors_origin="https://ui.example", universe=lambda: universe)


def test_session_api_passes_a_normalised_base_to_the_runtime():
    deps = _api()
    body = {"profile": {"base_persona_id": "robert", "base_portfolio": CANADIAN},
            "request_text": "Would adding 10% SPY improve diversification?"}
    status, out, _ = call(deps, "POST", "/sessions", body=body)
    assert status == 202
    import json
    sent = json.loads(deps.runtime.calls[0]["payload"])
    assert sent["profile"]["base_portfolio"]["XBB.TO"] == pytest.approx(0.25)
    assert "base_portfolio" not in (sent["profile"].get("values") or {})


def test_session_api_refuses_an_unusable_base_with_422():
    deps = _api()
    body = {"profile": {"base_persona_id": "robert", "values": {"base_portfolio": {"SPY": 0.5, "ZZZ": 0.5}}},
            "request_text": "10% in TSLA"}
    status, out, _ = call(deps, "POST", "/sessions", body=body)
    assert status == 422 and out.get("fields") == ["base_portfolio"] and "ZZZ" in out["error"]
    assert deps.runtime.calls == []


def test_runtime_uses_the_investors_own_holdings(source):  # noqa: F811
    deps, _ = _deps(source)
    payload = _payload(profile={"base_persona_id": "robert", "base_portfolio": CANADIAN},
                       request_text="Would adding 10% SPY improve diversification?")
    request = rt.build_request(payload, deps, source)
    assert request.base_portfolio == pytest.approx(validate_base_portfolio(CANADIAN))
    assert request.ticker == "SPY" and request.weight == pytest.approx(0.10)
    assert "base_portfolio" not in request.contract


def test_a_whole_session_runs_on_the_custom_base(source):  # noqa: F811
    deps, _ = _deps(source)
    payload = _payload(profile={"base_persona_id": "robert", "base_portfolio": CANADIAN},
                       request_text="Would adding 10% SPY improve diversification?")
    rt.run_payload(payload, deps)
    view = deps.store.get_view("user-1", "s-rt1")
    assert view.status == "completed", view.error
    comparison = [e for e in view.exhibits if e["metric"] == "portfolio_comparison"]
    assert any("XBB.TO" in str(e.get("value")) or "XBB.TO" in str(e.get("assets")) for e in view.exhibits)
    assert comparison, "the comparison Exhibit is built from the custom base"
