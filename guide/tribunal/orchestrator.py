"""Tribunal_Orchestrator: the fixed flow of Req. 36, behind ``run_session``.

Order, once each: Profiler gate (code) -> Risk_Panel and Hard_Rules of the request (code) ->
Advocate (1 call) -> Risk_Panel and Hard_Rules of every Option (code; failing Options are kept
and marked rejected) -> Investigator (1 call) -> Judge (1 call) -> Clerk template, citation
validator, guidance-only check (code). At most 3 agent calls. Agents never call each other: this
module is the only place that passes data between stages.

The Verdict comes from ``rules.decide``. The Judge can only make it more cautious through
``apply_soft_preferences``. Any agent failure (error, timeout, invalid output, Guardrail block)
still ends in a valid Ruling (Req. 36.5 to 36.7). Nothing here reads an agent's self-report.
"""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping

from guide.agents import clerk
from guide.agents.advocate import AdvocateOutput, run_advocate
from guide.agents.base import StageFailure
from guide.agents.instructions import SystemPrompt, load_all
from guide.agents.investigator import InvestigatorResult, contract_field_names, run_investigator
from guide.agents.judge import JudgeResult, apply_soft_preferences, run_judge
from guide.config import AGENT_NAMES, Config, load_config
from guide.contract.validate import validate_contract
from guide.data import quality
from guide.data.loader import DataSource, SnapshotStore
from guide.session.store import SessionSink
from guide.toolkit import metrics
from guide.toolkit.exhibits import ExhibitRegistry
from guide.toolkit.risk_panel import RiskPanel, risk_panel
from guide.toolkit.tools import ToolRunner
from guide.trace.recorder import TraceRecorder
from guide.tribunal import session_view as sv
from guide.tribunal.citations import Claim, enforce
from guide.tribunal.guidance_only import check_guidance_only, strip_violations
from guide.session.store import PrecedentItemStore
from guide.tribunal import precedents as precedent_store
from guide.tribunal.option_ids import MAX_WEIGHT_OPTION_ID, REQUEST_OPTION_ID
from guide.tribunal.rules import ACCEPT_WITH_CONDITIONS, RuleRequest, RuleResult, Verdict, decide, evaluate_rules
from guide.tribunal.sensitivity import run_sensitivity
from guide.tribunal.summaries import build_summary

MAX_AGENT_CALLS = 3
TEMPLATE_NARRATIVE = (
    "The verdict below is the result of the Hard_Rules computed by code; no narrative was "
    "written by the Judge for this session."
)
SAFE_GOAL = "The goal could not be stated."


class SessionError(RuntimeError):
    """A stage that must succeed failed. ``stage`` names it; the failed view was published."""

    def __init__(self, stage: str, message: str) -> None:
        self.stage = stage
        self.message = message
        super().__init__(f"{stage}: {message}")


@dataclass(frozen=True)
class SessionRequest:
    contract: Mapping[str, Any]  # a valid Investor_Contract; it carries no Base_Portfolio
    ticker: str
    weight: float
    start: date
    end: date
    as_of: date | None = None
    text: str = ""
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    profile_id: str | None = None
    rationales: Mapping[str, str] = field(default_factory=dict)
    base_portfolio: Mapping[str, float] | None = None  # from the Persona_File or the form


@dataclass
class AgentRunners:
    """The three agent calls. Replace them in tests; the defaults call Bedrock Converse."""

    advocate: Callable[..., AdvocateOutput]
    investigator: Callable[..., InvestigatorResult]
    judge: Callable[..., JudgeResult]


def bedrock_runners(config: Config, prompts: Mapping[str, SystemPrompt], client: Any | None = None) -> AgentRunners:
    """Runners over the agent modules; ``client`` is an injectable Bedrock runtime client."""
    return AgentRunners(
        advocate=lambda **kw: run_advocate(
            config, system_prompt=prompts.get("advocate"), client=client, **kw),
        investigator=lambda **kw: run_investigator(config, client=client, **kw),
        judge=lambda **kw: run_judge(config, system_prompt=prompts.get("judge"), client=client, **kw),
    )


def _call_with_timeout(fn: Callable[[], Any], seconds: float, agent: str) -> Any:
    """Run one agent call; a call that outlives ``agent_timeout_seconds`` is a failed stage."""
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"agent-{agent}")
    future = pool.submit(fn)
    try:
        return future.result(timeout=seconds)
    except FutureTimeout:
        raise StageFailure(agent, f"timed out after {seconds:g} seconds") from None
    finally:
        pool.shutdown(wait=False)


def _failure_reason(error: BaseException) -> str:
    return error.reason if isinstance(error, StageFailure) else f"{type(error).__name__}"


def _panel_summary(panel: RiskPanel | metrics.ToolError) -> dict[str, Any]:
    if isinstance(panel, metrics.ToolError):
        return {"error": panel.message}
    return {k: (v.number if hasattr(v, "number") else "unavailable") for k, v in panel.items.items()}


def _rule_dicts(results: list[RuleResult]) -> list[dict[str, Any]]:
    return [asdict(r) for r in results]


def _drop_failing(agent: str, texts: list[str], trace: TraceRecorder) -> set[str]:
    """Guidance-only check on agent output; return the failing statements."""
    findings = check_guidance_only(agent, texts, trace)
    _, _ = strip_violations(texts, findings, trace)  # records each removal in the Trace
    return {f.statement for f in findings if not f.passed}


def run_session(
    request: SessionRequest,
    *,
    sink: SessionSink,
    config: Config | None = None,
    source: DataSource | None = None,
    runners: AgentRunners | None = None,
    client: Any | None = None,
    prompts: Mapping[str, SystemPrompt] | None = None,
    memory: Any | None = None,
    trace: TraceRecorder | None = None,
    precedents: PrecedentItemStore | None = None,
) -> sv.SessionView:
    """Run one Tribunal_Session and return the final SessionView (also published to ``sink``)."""
    config = config or load_config()
    trace = trace or TraceRecorder(emit_spans=False)
    view = sv.new_session_view(request.session_id)
    registry: ExhibitRegistry | None = None

    def safe_publish(doc: sv.SessionView) -> None:
        # A sink failure is recorded and never changes the Ruling or aborts the session.
        try:
            sink.publish(doc)
        except Exception as error:
            trace.judge_check("sink_publish", {"session_id": request.session_id},
                              f"failed: {type(error).__name__}")

    def publish(new: sv.SessionView) -> sv.SessionView:
        safe_publish(replace(new, trace=trace.to_list()))
        return new

    def abort(stage: str, message: str, cause: BaseException | None = None) -> SessionError:
        publish(sv.failed(view, stage, message))
        err = SessionError(stage, message)
        err.__cause__ = cause
        return err

    # ---- stage: instructions and snapshot (no session starts on failure) ----
    try:
        prompts = prompts or load_all(AGENT_NAMES, Path(config.instruction_dir))
    except Exception as error:
        raise abort("instructions", str(error), error)
    try:
        source = source or SnapshotStore(config).pin()
    except Exception as error:
        raise abort("snapshot", f"{type(error).__name__}: {error}", error)
    snapshot = source.snapshot
    registry = ExhibitRegistry(snapshot)
    fallback = snapshot.served_from == "cache_fallback"
    trace.data_event("cache_fallback" if fallback else "snapshot_pinned", snapshot.snapshot_id,
                     snapshot.retrieved_at.isoformat(), snapshot.fallback_cause if fallback else None)
    view = sv.new_session_view(request.session_id, snapshot=snapshot)
    if fallback:
        view = sv.with_data_notice(view, quality.fallback_note(snapshot))
    view = publish(sv.stage_finished(view, "snapshot"))

    # ---- stage: Profiler gate ----
    contract = dict(request.contract)
    errors = validate_contract(contract)
    if errors:
        raise abort("profiler", "invalid contract: " + ", ".join(e.field for e in errors))
    view = publish(sv.stage_finished(view, "profiler", contract=contract))

    runners = runners or bedrock_runners(config, prompts, client)
    timeout = config.agent_timeout_seconds
    base = request.base_portfolio or contract.get("base_portfolio")
    if not base:
        raise abort("profiler", "no Base_Portfolio for this session")
    base = dict(base)
    # The Toolkit reads the Base_Portfolio from the contract mapping; the published contract stays clean.
    working = {**contract, "base_portfolio": base}
    tools = ToolRunner(registry, source, request.as_of, working)
    universe = set(source.read_table(metrics.UNIVERSE_TABLE)["ticker"])
    agents_run: list[str] = []
    agents_failed: list[dict[str, str]] = []

    def rule_request(ticker: str, weight: float) -> RuleRequest:
        return RuleRequest(ticker, weight, base, request.start, request.end, request.as_of)

    def option_panel(option_id: str, ticker: str, weight: float):
        return risk_panel(
            {"id": option_id, "ticker": ticker, "weight": weight, "start": request.start,
             "end": request.end, "as_of": request.as_of},
            working, registry=registry, source=source)

    # ---- stage: Risk_Panel and Hard_Rules of the request (code) ----
    try:
        req = rule_request(request.ticker, request.weight)
        request_panel = option_panel(REQUEST_OPTION_ID, request.ticker, request.weight)
        results = evaluate_rules(contract, req, registry, source=source, trace=trace)
        verdict = decide(results, contract, req, registry, source=source, trace=trace)
    except Exception as error:
        raise abort("request_rules", f"{type(error).__name__}: {error}", error)
    options: list[dict[str, Any]] = [{
        "option_id": REQUEST_OPTION_ID, "ticker": request.ticker, "weight": request.weight,
        "rationale": "The request as stated.", "source": "request",
        "rejected": any(r.status == "fail" for r in results),
        "failing_rules": [r.rule for r in results if r.status == "fail"],
        "hard_rule_results": _rule_dicts(results),
        "risk_panel": _panel_summary(request_panel),
    }]
    view = publish(sv.stage_finished(
        view, "request_rules", next_agent="advocate", exhibits=registry.all(),
        verdict=asdict(verdict), rule_results=_rule_dicts(results)))

    # ---- stage: Advocate (1 call) ----
    advocate_options: list[tuple[str, float, str, str]] = []  # ticker, weight, rationale, source
    advocate_goal = ""
    try:
        agents_run.append("advocate")
        out = _call_with_timeout(lambda: runners.advocate(
            request_text=request.text, request_ticker=request.ticker, request_weight=request.weight,
            contract=contract, risk_panel=_panel_summary(request_panel), tools=tools, trace=trace,
            universe=universe), timeout, "advocate")
        bad = _drop_failing("advocate", [out.goal] + [o.rationale for o in out.options], trace)
        advocate_goal = SAFE_GOAL if out.goal in bad else out.goal
        advocate_options = [(o.asset, o.weight, o.rationale, "advocate")
                            for o in out.options if o.rationale not in bad]
        if not advocate_options:
            raise StageFailure("advocate", "no option passed the guidance-only check")
    except Exception as error:
        agents_failed.append({"agent": "advocate", "reason": _failure_reason(error)})
        # Req. 36.5: the request and the maximum weight within the contract, computed by code.
        if verdict.verdict == ACCEPT_WITH_CONDITIONS and verdict.max_weight:
            advocate_options = [(request.ticker, verdict.max_weight,
                                 "Largest position size meeting every Hard_Rule, computed by code.", "code")]
        else:
            advocate_options = []
    summary = None
    if "advocate" not in {f["agent"] for f in agents_failed}:
        summary = build_summary("advocate", {"goal": advocate_goal, "options": [{"rejected": False}] * len(advocate_options)}, registry)
    view = publish(sv.stage_finished(view, "advocate", next_agent=None, summary=summary,
                                     summary_key="advocate", exhibits=registry.all()))

    # ---- stage: Risk_Panel and Hard_Rules of every Option (code) ----
    for index, (ticker, weight, rationale, origin) in enumerate(advocate_options, start=1):
        option_id = MAX_WEIGHT_OPTION_ID if origin == "code" else f"option_{index}"
        try:
            panel = option_panel(option_id, ticker, weight)
            opt_results = evaluate_rules(contract, rule_request(ticker, weight), registry,
                                         source=source, trace=trace)
        except Exception as error:
            trace.judge_check("option_rules", {"option": option_id}, f"failed: {type(error).__name__}")
            continue
        failing = [r.rule for r in opt_results if r.status == "fail"]
        options.append({
            "option_id": option_id, "ticker": ticker, "weight": weight, "rationale": rationale,
            "source": origin, "rejected": bool(failing), "failing_rules": failing,
            "hard_rule_results": _rule_dicts(opt_results), "risk_panel": _panel_summary(panel),
        })
    view = publish(sv.stage_finished(view, "option_rules", next_agent="investigator",
                                     exhibits=registry.all()))

    # ---- stage: Investigator (1 call) ----
    risks: list[dict[str, Any]] = []
    try:
        agents_run.append("investigator")
        res = _call_with_timeout(lambda: runners.investigator(
            options=options, contract=contract, registry=registry, tools=tools, trace=trace),
            timeout, "investigator")
        if res.blocked:
            raise StageFailure("investigator", "guardrail intervened")
        claims = [
            Claim(r["risk"], list(r["exhibits"]), contract_ref=r["contract_fields"][0])
            for entry in res.per_option for r in entry["material_risks"]
        ]
        kept, _ = enforce("investigator", claims, registry, recorder=trace,
                          require_contract_ref=True, known_contract_refs=sorted(contract_field_names(contract)))
        kept_ids = {id(c) for c in kept}
        bad = _drop_failing("investigator", [c.text for c in kept], trace)
        claim_iter = iter(claims)
        for entry in res.per_option:
            for r in entry["material_risks"]:
                claim = next(claim_iter)
                if id(claim) in kept_ids and r["risk"] not in bad:
                    risks.append({"option": entry["option_id"], **r})
        investigator_summary = build_summary("investigator", {"risks": risks}, registry)
    except Exception as error:
        agents_failed.append({"agent": "investigator", "reason": _failure_reason(error)})
        investigator_summary = None
    view = publish(sv.stage_finished(view, "investigator", next_agent="judge", summary=investigator_summary,
                                     summary_key="investigator"))

    # ---- stage: Judge (1 call) ----
    passing = [o["option_id"] for o in options if not o["rejected"]]
    assessments: list[dict[str, Any]] = []
    narrative = TEMPLATE_NARRATIVE
    final = verdict
    judge_extra: dict[str, Any] = {}
    precedent_doc: dict[str, Any] | None = None
    if precedents is not None:  # Req. 31.2: code looks up the closest Precedent; a failure is ignored
        try:
            found = precedent_store.closest(precedents, request.ticker, request.weight,
                                            exclude_session=request.session_id)
            if found:
                judge_extra["precedent"] = found
        except Exception as error:
            trace.judge_check("precedent_lookup", {"asset": request.ticker}, f"failed: {type(error).__name__}")
    try:
        agents_run.append("judge")
        res = _call_with_timeout(lambda: runners.judge(
            hard_rule_results=_rule_dicts(results), options=options, investigator_findings=risks,
            contract=contract, verdict=asdict(verdict), passing_option_ids=passing,
            registry=registry, trace=trace, **judge_extra), timeout, "judge")
        if res.blocked:
            raise StageFailure("judge", "guardrail intervened")
        claims = [Claim(a["findings"], list(a["exhibits"])) for a in res.assessments]
        kept, _ = enforce("judge", claims, registry, recorder=trace)
        kept_ids = {id(c) for c in kept}
        assessments = [a for a, c in zip(res.assessments, claims) if id(c) in kept_ids]
        bad = _drop_failing("judge", [res.narrative] + [a["findings"] for a in assessments], trace)
        assessments = [a for a in assessments if a["findings"] not in bad]
        narrative = TEMPLATE_NARRATIVE if res.narrative in bad else res.narrative
        final = apply_soft_preferences(verdict, assessments, REQUEST_OPTION_ID, contract)
        if "precedent" in judge_extra:  # Req. 31.2: code checks that each named field exists
            cited = judge_extra["precedent"]
            named = list(getattr(res, "precedent_fields", []) or [])
            for name in getattr(res, "unknown_precedent_fields", []) or []:
                trace.judge_check("precedent_field", {"field": name}, "failed: field does not exist")
            if cited.get("verdict") != final.verdict and not named:
                trace.judge_check("precedent_field", {"precedent": cited.get("session_id")},
                                  "failed: no existing differing field named")
            precedent_doc = {"session_id": cited.get("session_id"), "profile_id": cited.get("profile_id"),
                             "verdict": cited.get("verdict"), "weight": cited.get("weight"),
                             "differing_fields": named}
    except Exception as error:
        agents_failed.append({"agent": "judge", "reason": _failure_reason(error)})
    judge_failed = "judge" in {f["agent"] for f in agents_failed}
    judge_summary = None if judge_failed else build_summary("judge", asdict(final), registry)
    view = publish(sv.stage_finished(view, "judge", next_agent=None, summary=judge_summary,
                                     summary_key="judge", verdict=asdict(final)))

    # ---- stage: Clerk template, citation validator, guidance-only check (code) ----
    try:
        sensitivity = run_sensitivity(contract, req, results, registry, source=source)
        ruling = clerk.build_ruling(
            verdict=final, rule_results=results, sensitivity=sensitivity, contract=contract,
            request=req, registry=registry, snapshot=snapshot, rationales=request.rationales,
            requested_text=request.text)
        facts = [Claim(s.text, list(s.citations)) for s in ruling.facts]
        kept, _ = enforce("clerk", facts, registry, recorder=trace)
        removed = {c.text for c in facts} - {c.text for c in kept}
        if removed:
            ruling = replace(ruling, facts=[s for s in ruling.facts if s.text not in removed])
        findings = check_guidance_only("clerk", ruling.statements() + [narrative], trace)
        ruling, _ = strip_violations(ruling, findings, trace)
        if any(not f.passed and f.statement == narrative for f in findings):
            narrative = TEMPLATE_NARRATIVE
        ruling_doc = ruling.to_dict()
        ruling_doc["narrative"] = narrative
        ruling_doc["options"] = options
        ruling_doc["assessments"] = assessments
        ruling_doc["material_risks"] = risks
        if precedent_doc is not None:
            ruling_doc["precedent"] = precedent_doc
        ruling_doc["agents"] = {"ran": list(agents_run), "failed": list(agents_failed)}
    except Exception as error:
        raise abort("clerk", f"{type(error).__name__}: {error}", error)

    # ---- memory save and Trace export (a memory failure never changes the Ruling) ----
    if memory is not None and request.profile_id:
        try:
            memory.save_contract(request.profile_id, contract)
            memory.save_summary(request.profile_id, {"verdict": final.verdict, "ticker": request.ticker,
                                                     "weight": request.weight})
        except Exception as error:
            trace.judge_check("memory_save", {"profile_id": request.profile_id}, f"failed: {type(error).__name__}")
    view = sv.stage_finished(
        view, "clerk", completed=True, ruling=ruling_doc, verdict=asdict(final),
        sensitivity=[asdict(s) for s in sensitivity], exhibits=registry.all(),
        trace=trace.to_list())
    safe_publish(view)
    if precedents is not None and request.profile_id:  # Req. 31.1; never changes the Ruling
        try:
            precedent_store.put_precedent(precedents, view, request.profile_id)
        except Exception as error:
            trace.judge_check("precedent_save", {"profile_id": request.profile_id}, f"failed: {type(error).__name__}")
    return view
