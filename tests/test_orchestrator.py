"""Orchestrator: fixed flow, bounds and fallbacks of Req. 36, with fake agents (no AWS)."""
from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pytest

from guide.agents.advocate import AdvocateOption, AdvocateOutput
from guide.agents.base import StageFailure
from guide.agents.investigator import InvestigatorResult
from guide.agents.judge import JudgeResult
from guide.config import Config
from guide.contract.personas import SHIPPED_PATH, load_personas
from guide.contract.profiler import build_contract_from_persona
from guide.data.loader import LocalSource
from guide.tribunal import orchestrator as orch
from guide.tribunal.orchestrator import AgentRunners, SessionRequest, SessionError, run_session
from guide.tribunal.session_view import validate_document
from tests.test_metrics import _Source

START, END = date(2021, 11, 12), date(2026, 11, 12)
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def source():
    local = LocalSource()
    names = ["assets_universe", "prices_daily", "fx_usdcad_daily", "esg_exclusions"]
    return _Source({n: local.read_csv(f"{n}.csv") for n in names}, END)


class Sink:
    def __init__(self):
        self.views = []

    def publish(self, view):
        self.views.append(view)


def _config(**kw):
    return Config(s3_bucket="b", model_id="m", guardrail_id="g", guardrail_version="1",
                  instruction_dir=str(ROOT / "guide/agents"), **kw)


def _request(persona="robert", ticker="TSLA", weight=0.30):
    p = load_personas(SHIPPED_PATH).personas[persona]
    return SessionRequest(build_contract_from_persona(p), ticker, weight, START, END,
                          text=f"{weight:.0%} in {ticker}", session_id="s1",
                          base_portfolio=p.contract_values["base_portfolio"].value)


def lawful_ruling(options, narrative="Options weighed against stated preferences.", **extra):
    """A Judge ruling like a careful judge: the request if it passes, else the largest passing size."""
    request = options[0]
    same = [o for o in options if o["ticker"] == request["ticker"] and not o["rejected"]]
    if not request["rejected"]:
        decision = {"verdict": "accept", "option_id": "request", "conditions": [],
                    "reason": "The request meets every Hard_Rule.", "exhibits": [1]}
    elif same:
        best = max(same, key=lambda o: o["weight"])
        decision = {"verdict": "accept_with_conditions", "option_id": best["option_id"],
                    "conditions": [], "reason": "A smaller position meets every Hard_Rule.", "exhibits": [1]}
    else:
        decision = {"verdict": "reject", "option_id": None, "conditions": [],
                    "reason": "No option in this asset meets the Hard_Rules.", "exhibits": [1]}
    return JudgeResult(narrative=narrative, decision=decision, **extra)


class Fakes:
    def __init__(self, advocate=None, investigator=None, judge=None):
        self.calls = []
        self._a, self._i, self._j = advocate, investigator, judge

    def runners(self):
        def adv(**kw):
            self.calls.append("advocate")
            return self._a(**kw) if self._a else AdvocateOutput(
                "Keep exposure to one stock small.",
                (AdvocateOption("TSLA", 0.05, "A smaller position.", (1,)),
                 AdvocateOption("TSLA", 0.20, "A mid-size position.", (1,))))

        def inv(**kw):
            self.calls.append("investigator")
            if self._i:
                return self._i(**kw)
            return InvestigatorResult(per_option=[{"option_id": "request", "material_risks": [
                {"risk": "Single-stock concentration.", "exhibits": [1],
                 "why_for_this_person": "Low risk tolerance.", "contract_fields": ["per_asset_cap"]}]}])

        def judge(**kw):
            self.calls.append("judge")
            return self._j(**kw) if self._j else lawful_ruling(kw["options"])

        return AgentRunners(adv, inv, judge)


def _run(fakes, req=None, source=None, **kw):
    sink = Sink()
    view = run_session(req or _request(), sink=sink, config=_config(), source=source,
                       runners=fakes.runners(), **kw)
    return view, sink


def test_fixed_flow_three_calls_and_valid_view(source):
    fakes = Fakes()
    view, sink = _run(fakes, source=source)
    assert fakes.calls == ["advocate", "investigator", "judge"]
    assert view.status == "completed"
    assert view.stages_done == ["snapshot", "profiler", "request_rules", "advocate",
                                "option_rules", "investigator", "judge", "clerk"]
    assert len(sink.views) == 8  # one publication per stage
    from guide.tribunal.session_view import session_view_to_dict
    validate_document(session_view_to_dict(view))
    assert view.verdict["verdict"] == "accept_with_conditions"
    assert view.verdict["max_weight"] == 0.05  # Robert TSLA, ruled by the Judge
    assert ruling_decided(view) == "judge"
    ruling = view.ruling
    assert ruling["agents"] == {"ran": ["advocate", "investigator", "judge"], "failed": []}
    ids = [o["option_id"] for o in ruling["options"]]
    assert ids == ["request", "option_1", "option_2"]
    assert next(o for o in ruling["options"] if o["option_id"] == "request")["rejected"] is True
    assert {"advocate", "investigator", "judge"} <= set(view.summaries)
    kinds = {e["kind"] for e in view.trace}
    assert "snapshot_pinned" in kinds and "judge_check" in kinds
    assert view.snapshot["snapshot_id"] == source.snapshot.snapshot_id


def ruling_decided(view):
    return view.ruling["decided_by"]


def test_no_verdict_is_published_before_the_judge_rules(source):
    _, sink = _run(Fakes(), source=source)
    before = [v for v in sink.views if "judge" not in v.stages_done]
    assert before and all(v.verdict is None for v in before)
    assert sink.views[-2].stages_done[-1] == "judge" and sink.views[-2].verdict is not None


def test_judge_can_reject_even_when_a_smaller_size_passes(source):
    def judge(**kw):
        return JudgeResult(narrative="n", decision={
            "verdict": "reject", "option_id": None, "conditions": [],
            "reason": "The Investigator's concentration risk outweighs a small position.", "exhibits": [1]})

    view, _ = _run(Fakes(judge=judge), source=source)
    assert view.verdict["verdict"] == "reject" and view.verdict["max_weight"] is None
    assert ruling_decided(view) == "judge"


def test_unlawful_ruling_is_sent_back_once_then_stands(source):
    calls = []

    def judge(**kw):
        calls.append(kw.get("objection"))
        if len(calls) == 1:  # adopts the 30% request, which breaks the Hard_Rules
            return JudgeResult(narrative="n", decision={
                "verdict": "accept", "option_id": "request", "conditions": [], "reason": "r", "exhibits": [1]})
        return lawful_ruling(kw["options"])

    fakes = Fakes(judge=judge)
    view, _ = _run(fakes, source=source)
    assert fakes.calls == ["advocate", "investigator", "judge", "judge"]
    assert calls[0] is None and "breaks the Hard_Rules" in calls[1][0]
    assert ruling_decided(view) == "judge" and view.verdict["max_weight"] == 0.05
    checks = [e for e in view.trace if e["kind"] == "judge_check" and e["name"] == "judge_ruling"]
    assert [c["summary"]["result"].split(":")[0] for c in checks] == ["failed", "passed"]


def test_unlawful_twice_uses_labeled_code_fallback(source):
    def judge(**kw):
        return JudgeResult(narrative="n", decision={
            "verdict": "accept", "option_id": "option_2", "conditions": [], "reason": "r", "exhibits": [1]})

    fakes = Fakes(judge=judge)
    view, _ = _run(fakes, source=source)
    assert fakes.calls.count("judge") == 2
    assert ruling_decided(view) == "code" and view.ruling["narrative"] == orch.TEMPLATE_NARRATIVE
    assert view.verdict["verdict"] == "accept_with_conditions" and view.verdict["max_weight"] == 0.05


def test_code_max_weight_option_is_always_offered(source):
    def adv(**kw):
        return AdvocateOutput("Goal.", (AdvocateOption("TSLA", 0.02, "Small.", (1,)),
                                        AdvocateOption("TSLA", 0.20, "Mid.", (1,))))

    view, _ = _run(Fakes(advocate=adv), source=source)
    ids = [(o["option_id"], o["weight"]) for o in view.ruling["options"]]
    assert ("max_weight", 0.05) in ids


def test_advocate_failure_offers_request_and_code_max_weight(source):
    def boom(**kw):
        raise StageFailure("advocate", "invalid output")

    view, _ = _run(Fakes(advocate=boom), source=source)
    assert [o["option_id"] for o in view.ruling["options"]] == ["request", "max_weight"]
    assert view.ruling["options"][1]["weight"] == 0.05
    assert view.ruling["agents"]["failed"] == [{"agent": "advocate", "reason": "invalid output"}]
    assert view.status == "completed" and "advocate" not in view.summaries


def test_investigator_failure_keeps_risk_panels_without_explanation(source):
    def boom(**kw):
        raise StageFailure("investigator", "invalid output")

    view, _ = _run(Fakes(investigator=boom), source=source)
    assert view.ruling["material_risks"] == []
    assert all(o["risk_panel"] for o in view.ruling["options"])
    assert [f["agent"] for f in view.ruling["agents"]["failed"]] == ["investigator"]


def test_judge_failure_uses_code_verdict_and_template_sentence(source):
    def boom(**kw):
        raise TimeoutError

    view, _ = _run(Fakes(judge=boom), source=source)
    assert view.ruling["narrative"] == orch.TEMPLATE_NARRATIVE
    assert ruling_decided(view) == "code"
    assert view.verdict["verdict"] == "accept_with_conditions"
    assert [f["agent"] for f in view.ruling["agents"]["failed"]] == ["judge"]


def test_all_agents_fail_still_valid_ruling(source):
    def boom(**kw):
        raise RuntimeError("x")

    view, _ = _run(Fakes(boom, boom, boom), source=source)
    assert view.status == "completed" and view.verdict["verdict"] == "accept_with_conditions"
    assert len(view.ruling["agents"]["failed"]) == 3


def test_agent_timeout_is_a_failed_stage(source):
    def slow(**kw):
        time.sleep(0.5)

    sink = Sink()
    fakes = Fakes(judge=slow)
    view = run_session(_request(), sink=sink, config=_config(agent_timeout_seconds=0.05), source=source,
                       runners=fakes.runners())
    failed = view.ruling["agents"]["failed"]
    assert failed[0]["agent"] == "judge" and "timed out" in failed[0]["reason"]


def test_judge_accepts_a_request_that_passes(source):
    view, _ = _run(Fakes(), _request("robert", "SPY", 0.02), source=source)
    assert view.verdict["verdict"] == "accept" and ruling_decided(view) == "judge"


def test_ruling_without_decision_falls_back_to_code(source):
    def judge(**kw):
        return JudgeResult(narrative="n")

    fakes = Fakes(judge=judge)
    view, _ = _run(fakes, _request("robert", "SPY", 0.02), source=source)
    assert fakes.calls.count("judge") == 2 and ruling_decided(view) == "code"
    assert view.verdict["verdict"] == "accept"


def test_mateo_esg_reject_stays_reject(source):
    view, _ = _run(Fakes(), _request("mateo", "XOM", 0.10), source=source)
    assert view.verdict["verdict"] == "reject"
    assert view.ruling["options"][0]["rejected"] is True


def test_order_instructing_agent_text_is_dropped(source):
    def adv(**kw):
        return AdvocateOutput("Goal.", (
            AdvocateOption("TSLA", 0.05, "Place an order for the smaller position now.", (1,)),
            AdvocateOption("TSLA", 0.10, "A modest position.", (1,))))

    view, _ = _run(Fakes(advocate=adv), source=source)
    texts = [o["rationale"] for o in view.ruling["options"]]
    assert not any("Place an order" in t for t in texts)
    assert any(e["kind"] == "claim_removed" for e in view.trace)


def test_invalid_contract_publishes_failed_view_and_raises(source):
    req = _request()
    bad = SessionRequest({**req.contract, "per_asset_cap": 5}, "TSLA", 0.3, START, END, session_id="s2",
                         base_portfolio=req.base_portfolio)
    sink = Sink()
    with pytest.raises(SessionError) as exc:
        run_session(bad, sink=sink, config=_config(), source=source, runners=Fakes().runners())
    assert exc.value.stage == "profiler"
    last = sink.views[-1]
    assert last.status == "failed" and last.error.stage == "profiler"


def test_snapshot_failure_surfaces_stage(monkeypatch):
    class Boom:
        def __init__(self, *a, **k): ...
        def pin(self):
            from guide.data.loader import DatasetUnavailable
            raise DatasetUnavailable("s3://b/k")

    monkeypatch.setattr(orch, "SnapshotStore", Boom)
    sink = Sink()
    with pytest.raises(SessionError) as exc:
        run_session(_request(), sink=sink, config=_config(), runners=Fakes().runners())
    assert exc.value.stage == "snapshot" and sink.views[-1].status == "failed"


def test_memory_failure_does_not_change_ruling(source):
    class Mem:
        def save_contract(self, *a):
            raise RuntimeError("down")

        def save_summary(self, *a): ...

    req = _request()
    req = SessionRequest(**{**req.__dict__, "profile_id": "p1"})
    view, _ = _run(Fakes(), req, source=source, memory=Mem())
    assert view.status == "completed"


class _Client:
    def __init__(self):
        self.calls = 0

    def converse(self, **kw):
        self.calls += 1
        text = {1: '{"goal": "g", "options": [{"asset": "TSLA", "weight": 0.05, "rationale": "r", "exhibits": [1]}]}',
                2: '{"per_option": []}',
                3: '{"assessments": [], "narrative": "ok", "decision": {"verdict": "accept_with_conditions", '
                   '"option_id": "option_1", "conditions": [], "reason": "A smaller position meets every rule.", '
                   '"exhibits": [1]}}'}[self.calls]
        return {"stopReason": "end_turn", "output": {"message": {"role": "assistant", "content": [{"text": text}]}}}


def test_default_bedrock_runners_make_exactly_three_calls(source):
    client = _Client()
    sink = Sink()
    view = run_session(_request(), sink=sink, config=_config(), source=source, client=client)
    assert client.calls == 3 and view.status == "completed"
    assert view.ruling["agents"]["failed"] == [] and ruling_decided(view) == "judge"


def test_precedent_saved_and_passed_to_judge_on_next_session(source):
    from dataclasses import replace
    from guide.tribunal.precedents import InMemoryPrecedentStore

    store = InMemoryPrecedentStore()
    seen = {}

    def judge(**kw):
        seen["precedent"] = kw.get("precedent")
        return lawful_ruling(kw["options"])

    first = replace(_request(), profile_id="robert", session_id="s1")
    _run(Fakes(), first, source=source, precedents=store)
    second = replace(_request(), profile_id="robert", session_id="s2")
    _run(Fakes(judge=judge), second, source=source, precedents=store)
    assert seen["precedent"]["session_id"] == "s1"
    assert seen["precedent"]["asset"] == "TSLA"


def test_sink_failure_does_not_change_ruling(source):
    class Flaky(Sink):
        def publish(self, view):
            if len(self.views) % 2 == 0:
                self.views.append(None)
                raise RuntimeError("sink down")
            super().publish(view)

    baseline, _ = _run(Fakes(), source=source)
    view = run_session(_request(), sink=Flaky(), config=_config(), source=source,
                       runners=Fakes().runners())
    assert view.status == "completed"
    assert view.ruling["verdict"] == baseline.ruling["verdict"]
    assert any(e.get("check") == "sink_publish" or "sink_publish" in str(e) for e in view.trace)


def test_agents_receive_exhibit_values_not_just_numbers(source):
    seen = {}

    def advocate(**kw):
        seen["advocate"] = kw
        raise StageFailure("advocate", "stop after capture")

    def investigator(**kw):
        seen["investigator"] = kw["options"]
        raise StageFailure("investigator", "stop after capture")

    view, _ = _run(Fakes(advocate=advocate, investigator=investigator), source=source)
    panel = seen["advocate"]["risk_panel"]
    assert any(isinstance(v, dict) and {"exhibit", "value"} <= set(v) for v in panel.values())
    assert seen["advocate"]["hard_rule_results"]
    assert any(isinstance(v, dict) and "value" in v
               for o in seen["investigator"] for v in o["risk_panel"].values())
    # The published ruling keeps its original shape (Exhibit numbers only) for the UI.
    assert all(not isinstance(v, dict) for o in view.ruling["options"] for v in o["risk_panel"].values())
