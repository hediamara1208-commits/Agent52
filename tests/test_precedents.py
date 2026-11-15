import pytest

from guide.session.store import InMemorySessionStore
from guide.tribunal.precedents import closest, put_precedent
from guide.tribunal.session_view import SessionView


def _view(sid, ticker, weight, verdict="reject", status="completed"):
    return SessionView(
        session_id=sid,
        status=status,
        contract={"per_asset_cap": 0.1},
        exhibits=[{"number": 1, "metric": "volatility", "value": 0.2, "snapshot_id": "s1"}],
        verdict={"verdict": verdict, "max_weight": 0.05, "failing_rules": ["per_asset_cap"],
                 "unverified_rules": []},
        ruling={"options": [{"option_id": "request", "ticker": ticker, "weight": weight}],
                "assessments": [{"preference": "established", "assessment": "weak",
                                 "findings": "x", "exhibits": [1]}]},
    )


def test_put_and_closest_by_weight():
    store = InMemorySessionStore()
    put_precedent(store, _view("a", "TSLA", 0.30), "robert")
    put_precedent(store, _view("b", "TSLA", 0.10), "amira")
    put_precedent(store, _view("c", "XOM", 0.15), "mateo")
    got = closest(store, "TSLA", 0.12)
    assert got["session_id"] == "b" and got["profile_id"] == "amira"
    assert got["deciding_rules"] == ["per_asset_cap"]
    assert closest(store, "TSLA", 0.28)["session_id"] == "a"
    assert closest(store, "AAPL", 0.1) is None
    assert closest(store, "TSLA", 0.12, exclude_session="b")["session_id"] == "a"


def test_precedent_has_no_user_identifier_and_requires_completed():
    store = InMemorySessionStore()
    doc = put_precedent(store, _view("a", "TSLA", 0.3), "robert")
    assert "owner" not in doc and "user" not in doc
    with pytest.raises(ValueError):
        put_precedent(store, _view("z", "TSLA", 0.3, status="failed"), "robert")
    with pytest.raises(ValueError):
        put_precedent(store, _view("y", "TSLA", 0.3), "")
