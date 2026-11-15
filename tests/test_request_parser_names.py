"""Company names in a request resolve to universe tickers."""
import pytest

from guide.tribunal.request_parser import MissingFields, ParsedRequest, parse_request

UNIVERSE = {"TSLA", "NVDA", "BTC-USD", "RY.TO", "XOM", "SPY"}


@pytest.mark.parametrize("text, ticker, weight", [
    ("I want 30% in tesla.", "TSLA", 0.30),
    ("Put 10 percent in Nvidia", "NVDA", 0.10),
    ("40% bitcoin", "BTC-USD", 0.40),
    ("5% in Royal Bank", "RY.TO", 0.05),
    ("30% in TSLA", "TSLA", 0.30),
])
def test_names_and_tickers(text, ticker, weight):
    assert parse_request(text, UNIVERSE) == ParsedRequest(ticker, pytest.approx(weight))


def test_name_outside_the_universe_is_missing():
    assert parse_request("20% in apple", UNIVERSE) == MissingFields(asset=True, size=False)


def test_word_inside_another_word_does_not_match():
    assert parse_request("20% in teslanova", UNIVERSE) == MissingFields(asset=True, size=False)
