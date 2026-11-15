from __future__ import annotations

from functools import partial

from guide.contract.personas import load_personas
from guide.session.store import InMemorySessionStore
from guide.tribunal import entrypoint
from runtime import app as rt
from tests.test_orchestrator import Fakes, _config, source  # noqa: F401  (fixture)


def _payload(**kw):
    p = {"session_id": "s-rt1", "owner": "user-1", "profile": {"base_persona_id": "robert"},
         "request_text": "Robert 30% in TSLA"}
    p.update(kw)
    return p


def _deps(source, store=None, run=None, memory=None):
    emitted: list[dict] = []
    deps = rt.Deps(
        config=_config(), store=store or InMemorySessionStore(),
        run_session=run or partial(entrypoint.run_session, runners=Fakes().runners()),
        source_factory=lambda: source, memory_factory=lambda owner: memory,
        personas=lambda: dict(load_personas().personas), emit=emitted.append)
    return deps, emitted


def test_ack_before_verdict_and_background_run_writes_view(source):
    deps, emitted = _deps(source)
    work: list = []
    ack = rt.handle(_payload(), deps, spawn=work.append)
    assert ack == {"status": "accepted", "session_id": "s-rt1"}
    assert deps.store.get_view("user-1", "s-rt1") is None  # nothing ran yet
    work[0]()
    view = deps.store.get_view("user-1", "s-rt1")
    assert view is not None and view.status == "completed"
    assert emitted[0] == {"SessionsStarted": 1}
    assert emitted[1]["SessionsFailed"] == 0


def test_invalid_payload_is_rejected_without_running(source):
    deps, _ = _deps(source)
    work: list = []
    ack = rt.handle({"session_id": "x", "owner": "", "profile": []}, deps, spawn=work.append)
    assert ack["status"] == "rejected" and not work
    assert "owner" in ack["error"] and "request_text" in ack["error"]


def test_period_is_used_and_failure_writes_failed_view(source):
    seen = {}

    def boom(request, sink, **kw):
        seen.update(kw, start=str(request.start), end=str(request.end))
        raise RuntimeError("model down")

    deps, emitted = _deps(source, run=boom, memory="MEM")
    rt.run_payload(_payload(period={"start": "2022-01-03", "end": "2023-01-03"}), deps)
    assert (seen["start"], seen["end"]) == ("2022-01-03", "2023-01-03")
    assert seen["memory"] == "MEM" and seen["precedents"] is deps.store
    view = deps.store.get_view("user-1", "s-rt1")
    assert view.status == "failed"
    assert emitted[-1] == {"SessionsFailed": 1}


def test_unparsable_request_ends_as_failed_view(source):
    deps, _ = _deps(source)
    rt.run_payload(_payload(request_text="hello"), deps)
    assert deps.store.get_view("user-1", "s-rt1").status == "failed"


def test_token_counts_sum_agent_call_usage_per_session_and_agent():
    from runtime.app import _trace_counts
    trace = [
        {"kind": "agent_call", "name": "advocate", "summary": {"usage": {"inputTokens": 100, "outputTokens": 10, "cacheReadInputTokens": 50, "totalTokens": 160}}},
        {"kind": "agent_call", "name": "judge", "summary": {"usage": {"inputTokens": 200, "outputTokens": 20, "totalTokens": 220}}},
        {"kind": "agent_call", "name": "investigator", "summary": {"output": "no usage"}},
        {"kind": "tool_call", "name": "x", "summary": {}},
    ]
    c = _trace_counts(trace)
    assert c["TokensInput"] == 300 and c["TokensOutput"] == 30 and c["TokensCacheRead"] == 50
    assert c["TokensTotal"] == 380 and c["TokensTotalAdvocate"] == 160 and c["TokensTotalJudge"] == 220
