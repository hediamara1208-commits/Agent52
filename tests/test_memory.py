from datetime import datetime, timedelta, timezone

import pytest

from guide.config import Config
from guide.memory import MemoryError, MemoryStore


class FakeAgentCore:
    """In-memory stand-in implementing the two AgentCore calls used."""

    def __init__(self):
        self.events = []

    def create_event(self, **kw):
        self.events.append(dict(kw, eventTimestamp=kw["eventTimestamp"] + timedelta(seconds=len(self.events))))

    def list_events(self, **kw):
        evs = [
            {"eventTimestamp": e["eventTimestamp"], "payload": e["payload"]}
            for e in self.events
            if e["actorId"] == kw["actorId"] and e["sessionId"] == kw["sessionId"]
        ]
        return {"events": evs}


def _store(client, user_id="u1"):
    return MemoryStore(Config(s3_bucket="b", agentcore_memory_id="mem-1"), user_id, client=client)


def test_roundtrip_returns_latest_contract():
    s = _store(FakeAgentCore())
    s.save_contract("p1", {"v": 1})
    s.save_contract("p1", {"v": 2})
    s.save_summary("p1", "summary")
    assert s.load_contract("p1") == {"v": 2}


def test_other_profile_and_missing_return_none():
    s = _store(FakeAgentCore())
    s.save_contract("p1", {"v": 1})
    assert s.load_contract("p2") is None


def test_requires_memory_id_and_profile_id():
    with pytest.raises(MemoryError):
        MemoryStore(Config(s3_bucket="b"), "u1", client=FakeAgentCore())
    with pytest.raises(ValueError):
        _store(FakeAgentCore()).save_contract(" ", {})


def test_entries_keyed_by_user_and_profile_and_isolated():
    client = FakeAgentCore()
    a, b = _store(client, "userA"), _store(client, "userB")
    a.save_contract("p1", {"owner": "A"})
    assert client.events[0]["actorId"] == "userA/p1"
    assert b.load_contract("p1") is None
    b.save_contract("p1", {"owner": "B"})
    assert a.load_contract("p1") == {"owner": "A"}


def test_rejects_bad_user_id_and_slash_ids():
    for bad in ("", " ", "a/b"):
        with pytest.raises(ValueError):
            _store(FakeAgentCore(), bad)
    with pytest.raises(ValueError):
        _store(FakeAgentCore()).save_contract("p/1", {})
