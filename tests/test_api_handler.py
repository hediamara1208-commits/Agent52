import json

import pytest

from api.handler import ROUTES, Deps, handler
from guide.session.store import InMemorySessionStore
from guide.tribunal.session_view import validate_document

UNIVERSE = {"TSLA", "SPY"}


class FakeRuntime:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def invoke_agent_runtime(self, **kw):
        self.calls.append(kw)
        if self.fail:
            raise ConnectionError("down")
        return {}


def make(fail=False):
    deps = Deps(
        store=InMemorySessionStore(), runtime=FakeRuntime(fail), runtime_arn="arn:test",
        cors_origin="https://ui.example", universe=lambda: UNIVERSE,
    )
    return deps


def call(deps, method, path, sub="alice", body=None):
    event = {"httpMethod": method, "path": path}
    if sub:
        event["requestContext"] = {"authorizer": {"claims": {"sub": sub}}}
    if body is not None:
        event["body"] = json.dumps(body)
    res = handler(event, None, deps)
    return res["statusCode"], json.loads(res["body"]), res["headers"]


ROBERT = {"profile": {"base_persona_id": "robert"}, "request_text": "30% in TSLA"}


def test_no_claims_is_401():
    deps = make()
    assert call(deps, "GET", "/profiles", sub=None)[0] == 401
    assert deps.runtime.calls == []


def test_unlisted_routes_are_404():
    deps = make()
    for m, p in [("DELETE", "/sessions/x"), ("POST", "/orders"), ("GET", "/sessions"), ("PUT", "/sessions/x")]:
        assert call(deps, m, p)[0] == 404


def test_route_table_is_the_allowed_list():
    assert set(ROUTES) == {
        ("GET", "/personas"), ("GET", "/profiles"), ("PUT", "/profiles/{id}"),
        ("POST", "/sessions"), ("GET", "/sessions/{id}"), ("GET", "/sessions/{id}/trace"),
    }


def test_create_get_trace_and_foreign_404():
    deps = make()
    status, body, headers = call(deps, "POST", "/sessions", body=ROBERT)
    assert status == 202 and body["status"] == "running"
    assert headers["Access-Control-Allow-Origin"] == "https://ui.example"
    sid = body["session_id"]
    sent = json.loads(deps.runtime.calls[0]["payload"])
    assert sent["owner"] == "alice" and sent["session_id"] == sid

    status, view, _ = call(deps, "GET", f"/sessions/{sid}")
    assert status == 200 and view["status"] == "running"
    validate_document(view)
    assert call(deps, "GET", f"/sessions/{sid}/trace")[1]["trace"] == []
    assert call(deps, "GET", f"/sessions/{sid}", sub="bob")[0] == 404
    assert call(deps, "GET", f"/sessions/{sid}/trace", sub="bob")[0] == 404


def test_runtime_failure_writes_failed_and_503():
    deps = make(fail=True)
    status, view, _ = call(deps, "POST", "/sessions", body=ROBERT)
    assert status == 503
    validate_document(view)
    assert view["status"] == "failed" and view["error"]["stage"] == "runtime"
    stored = deps.store.get_view("alice", view["session_id"])
    assert stored.status == "failed"


def test_missing_request_fields_is_422_and_writes_nothing():
    deps = make()
    status, body, _ = call(deps, "POST", "/sessions", body={**ROBERT, "request_text": "buy TSLA"})
    assert status == 422 and body["missing"] == {"asset": False, "size": True}
    assert deps.runtime.calls == []


def test_profiles_are_per_owner():
    deps = make()
    status, _, _ = call(deps, "PUT", "/profiles/p1", body={"base_persona_id": "amira", "values": {}})
    assert status == 200
    assert [p["profile_id"] for p in call(deps, "GET", "/profiles")[1]["profiles"]] == ["p1"]
    assert call(deps, "GET", "/profiles", sub="bob")[1]["profiles"] == []
    assert call(deps, "PUT", "/profiles/p2", body={"base_persona_id": "nobody"})[0] == 422


def test_personas_listed():
    ids = {p["id"] for p in call(make(), "GET", "/personas")[1]["personas"]}
    assert {"amira", "mateo", "robert"} <= ids



GUEST_A = "Guest " + "a" * 32
GUEST_B = "Guest " + "b" * 32


def guest_call(deps, method, path, auth, body=None):
    event = {"httpMethod": method, "path": path, "headers": {"Authorization": auth}}
    if body is not None:
        event["body"] = json.dumps(body)
    res = handler(event, None, deps)
    return res["statusCode"], json.loads(res["body"])


def test_guest_header_is_refused_unless_guest_access_is_on(monkeypatch):
    deps = make()
    monkeypatch.delenv("GUIDE_GUEST_ACCESS", raising=False)
    assert guest_call(deps, "GET", "/personas", GUEST_A)[0] == 401
    monkeypatch.setenv("GUIDE_GUEST_ACCESS", "1")
    assert guest_call(deps, "GET", "/personas", GUEST_A)[0] == 200
    for bad in ("Guest abc", "Guest " + "A" * 32, "guest " + "a" * 32, "Bearer " + "a" * 32, ""):
        assert guest_call(deps, "GET", "/personas", bad)[0] == 401


def test_guests_are_isolated_from_each_other(monkeypatch):
    monkeypatch.setenv("GUIDE_GUEST_ACCESS", "1")
    deps = make()
    status, body = guest_call(deps, "POST", "/sessions", GUEST_A, ROBERT)
    assert status == 202
    sid = body["session_id"]
    assert json.loads(deps.runtime.calls[0]["payload"])["owner"] == "guest-" + "a" * 32
    assert guest_call(deps, "GET", f"/sessions/{sid}", GUEST_A)[0] == 200
    assert guest_call(deps, "GET", f"/sessions/{sid}", GUEST_B)[0] == 404
    assert guest_call(deps, "GET", f"/sessions/{sid}/trace", GUEST_B)[0] == 404
    guest_call(deps, "PUT", "/profiles/mine", GUEST_A, {"profile_id": "mine", "base_persona_id": "robert", "values": {}})
    assert guest_call(deps, "GET", "/profiles", GUEST_B)[1] in ([], {"profiles": []})


def test_guest_hearings_are_capped_per_guest_and_overall(monkeypatch):
    import api.handler as h

    monkeypatch.setenv("GUIDE_GUEST_ACCESS", "1")
    monkeypatch.setattr(h, "GUEST_DAILY_CAP", 2)
    monkeypatch.setattr(h, "GUESTS_DAILY_CAP", 3)
    deps = make()
    assert [guest_call(deps, "POST", "/sessions", GUEST_A, ROBERT)[0] for _ in range(3)] == [202, 202, 429]
    assert guest_call(deps, "POST", "/sessions", GUEST_B, ROBERT)[0] == 202
    assert guest_call(deps, "POST", "/sessions", GUEST_B, ROBERT)[0] == 429   # global cap of 3 reached
    assert len(deps.runtime.calls) == 3
    # An invalid request is refused before it is counted; signed-in owners are never capped.
    assert guest_call(deps, "POST", "/sessions", GUEST_A, {"profile": {}, "request_text": ""})[0] == 422
    assert call(deps, "POST", "/sessions", body=ROBERT)[0] == 202
