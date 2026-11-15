from pathlib import Path

import pandas as pd

from guide.ingest.validate import UniverseAddition, restrict_universe, validate_tables

DATA = Path(__file__).resolve().parents[1] / "data"


def _frames():
    return pd.read_csv(DATA / "prices_daily.csv"), pd.read_csv(DATA / "assets_universe.csv")


def test_starter_data_is_valid():
    prices, universe = _frames()
    assert validate_tables(prices, universe) == ()


def test_detects_each_violation():
    prices, universe = _frames()
    bad = pd.concat([prices, prices.iloc[[0]]], ignore_index=True)
    bad = bad[bad["ticker"] != "SPY"].copy()
    bad.loc[bad["ticker"] == "RY.TO", "currency"] = "USD"
    bad.loc[bad.index[5], "adj_close"] = 0
    v = " | ".join(validate_tables(bad, universe))
    assert "duplicate" in v and "SPY" in v and "RY.TO" in v and "adj_close" in v


ADD = UniverseAddition("NEW.TO", "New", "equity", "TSX", "CAD", "Financials", "SrcCo", "new.csv")
DOC_OK = """## SrcCo NEW.TO
| Terms of use | https://example.com/terms |
| Permitted use | Use and redistribution permitted in this project |
"""


def test_restrict_universe():
    r = restrict_universe(["RY.TO", "NEW.TO", "ZZZ"], ["RY.TO"], [ADD], DOC_OK)
    assert r.accepted == ("RY.TO", "NEW.TO")
    assert list(r.rejected) == ["ZZZ"]


def test_addition_rejected_without_documentation_or_with_restricted_terms():
    assert "NEW.TO" in restrict_universe(["NEW.TO"], [], [ADD], "").rejected
    restricted = DOC_OK + "| Limits | personal use only |\n"
    assert "NEW.TO" in restrict_universe(["NEW.TO"], [], [ADD], restricted).rejected
