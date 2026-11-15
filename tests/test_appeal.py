import json

import pytest

from guide.tribunal.appeal import diff_sessions
from guide.tribunal.session_view import new_session_view, session_view_to_dict, stage_finished
from tests.test_api_handler import ROBERT, call, make


def _doc(sid, verdict, weight, rule_status, exhibit_value, pref):
    v = new_session_view(sid)
    v = stage_finished(
        v, "clerk", completed=True,
        verdict={"verdict": verdict, "max_weight": weight},
        rule_results=[{"rule": "speculative_limit", "status": rule_status, "observed": 0.3, "limit": 0.05}],
        exhibits=[{"number": 1, "metric": "max_weight", "value": exhibit_value, "currency": "CAD",
                   "snapshot_id": "s", "assets": ["TSLA"]}],
        ruling={"verdict": verdict, "facts": [], "what_would_change": [], "disclaimers": [],
                "assessments": [{"preference": "established", "assessment": pref}]},
    )
    return session_view_to_dict(v)


def test_diff_reports_changed_rules_preferences_exhibits():
    a = _doc("a", "accept_with_conditions", 0.05, "fail", 0.05, "satisfied")
    b = _doc("b", "accept_with_conditions", 0.10, "pass", 0.10, "tension")
    d = diff_sessions(a, b)
    assert d["verdict"]["changed"] and d["verdict"]["appeal"]["max_weight"] == 0.10
    assert d["hard_rules"][0]["original"]["status"] == "fail" and d["hard_rules"][0]["appeal"]["status"] == "pass"
    assert d["soft_preferences"] == [{"preference": "established", "original": "satisfied", "appeal": "tension"}]
    assert d["exhibits"][0]["original"]["value"] == 0.05 and d["exhibits"][0]["appeal"]["value"] == 0.10
    assert diff_sessions(a, a) == {**diff_sessions(a, a), "hard_rules": [], "soft_preferences": [], "exhibits": []}


def _completed(deps, sid):
    view = stage_finished(new_session_view(sid), "clerk", completed=True,
                          verdict={"verdict": "accept", "max_weight": 0.3})
    deps.store.put_view("alice", view)


def _original(deps):
    status, body, _ = call(deps, "POST", "/sessions", body=ROBERT)
    assert status == 202
    sid = body["session_id"]
    _completed(deps, sid)
    return sid


def test_appeal_changes_contract_value_and_links_original():
    deps = make()
    sid = _original(deps)
    before = deps.store.get_view("alice", sid)
    status, body, _ = call(deps, "POST", "/sessions",
                           body={"appeal_of": sid, "change": {"field": "speculative_limit", "value": 0.10}})
    assert status == 202
    sent = json.loads(deps.runtime.calls[-1]["payload"])
    assert sent["appeal_of"] == sid and sent["profile"]["values"] == {"speculative_limit": 0.10}
    assert sent["request_text"] == "30% in TSLA"
    assert deps.store.get_view("alice", sid) == before
    assert call(deps, "GET", "/profiles")[1]["profiles"] == []


def test_appeal_position_size_and_period():
    deps = make()
    sid = _original(deps)
    assert call(deps, "POST", "/sessions", body={"appeal_of": sid, "change": {"field": "position_size", "value": 0.1}})[0] == 202
    assert json.loads(deps.runtime.calls[-1]["payload"])["request_text"] == "10% in TSLA"
    p = {"start": "2020-01-01", "end": "2023-01-01"}
    assert call(deps, "POST", "/sessions", body={"appeal_of": sid, "change": {"field": "period", "value": p}})[0] == 202
    assert json.loads(deps.runtime.calls[-1]["payload"])["period"] == p


@pytest.mark.parametrize("change", [
    {"field": "ticker", "value": "SPY"},
    {"field": "position_size", "value": 2},
    {"field": "period", "value": {"start": "2023-01-01", "end": "2020-01-01"}},
    {"field": "speculative_limit", "value": 0.1, "extra": 1},
])
def test_invalid_change_is_422_and_nothing_runs(change):
    deps = make()
    sid = _original(deps)
    n = len(deps.runtime.calls)
    assert call(deps, "POST", "/sessions", body={"appeal_of": sid, "change": change})[0] == 422
    assert len(deps.runtime.calls) == n


def test_appeal_foreign_unknown_or_running_session():
    deps = make()
    sid = _original(deps)
    chg = {"field": "speculative_limit", "value": 0.1}
    assert call(deps, "POST", "/sessions", sub="bob", body={"appeal_of": sid, "change": chg})[0] == 404
    assert call(deps, "POST", "/sessions", body={"appeal_of": "nope", "change": chg})[0] == 404
    _, body, _ = call(deps, "POST", "/sessions", body=ROBERT)
    assert call(deps, "POST", "/sessions", body={"appeal_of": body["session_id"], "change": chg})[0] == 409
