from hypothesis import given, strategies as st

from guide.tribunal.request_parser import MissingFields, ParsedRequest, parse_request

U = {"SPY", "QQQ", "XIU.TO"}


def test_percent_and_ticker():
    assert parse_request("What if I put 5% in SPY?", U) == ParsedRequest("SPY", 0.05)


def test_fraction_and_lowercase():
    assert parse_request("add qqq at 0.1", U) == ParsedRequest("QQQ", 0.1)


def test_missing_reports():
    assert parse_request("buy 5%", U) == MissingFields(asset=True, size=False)
    assert parse_request("buy SPY", U) == MissingFields(asset=False, size=True)
    assert parse_request("hello", U) == MissingFields(asset=True, size=True)


def test_unknown_ticker_not_in_universe():
    assert parse_request("5% in TSLA", U) == MissingFields(asset=True, size=False)


def test_fallback_fills_and_is_validated():
    fb = lambda t: {"ticker": "qqq", "weight_fraction": 0.2}
    assert parse_request("some tech fund, a fifth", U, fb) == ParsedRequest("QQQ", 0.2)
    bad = lambda t: {"ticker": "TSLA", "weight_fraction": 3}
    assert parse_request("x", U, bad) == MissingFields(True, True)

    def boom(t):
        raise RuntimeError

    assert parse_request("x", U, boom) == MissingFields(True, True)


def test_fallback_not_called_when_rules_succeed():
    def fb(t):
        raise AssertionError("should not be called")

    assert parse_request("5% SPY", U, fb) == ParsedRequest("SPY", 0.05)


@given(st.integers(1, 100), st.sampled_from(sorted(U)))
def test_roundtrip(pct, ticker):
    r = parse_request(f"put {pct}% into {ticker}", U)
    assert isinstance(r, ParsedRequest)
    assert r.ticker == ticker and abs(r.weight_fraction - pct / 100) < 1e-9
