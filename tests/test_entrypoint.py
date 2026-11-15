from __future__ import annotations

from guide.run_session import build_request
from guide.session.store import InMemorySessionStore, StoreSink
from guide.tribunal import entrypoint, orchestrator
from tests.test_orchestrator import Fakes, _config, source  # noqa: F401  (fixture)
from tests.test_orchestrator import _request


def test_entrypoint_delegates_to_orchestrator_and_publishes(source):
    store = InMemorySessionStore()
    sink = StoreSink(store, "owner")
    view = entrypoint.run_session(_request(), sink, config=_config(), source=source,
                                  runners=Fakes().runners())
    assert store.get_view("owner", "s1") is not None
    assert view.session_id == "s1"
    assert entrypoint.SessionRequest is orchestrator.SessionRequest


def test_local_runner_builds_robert_request(source):
    req = build_request("Robert 30% in TSLA", "robert", source)
    assert (req.ticker, req.weight) == ("TSLA", 0.30)
    assert req.end > req.start
