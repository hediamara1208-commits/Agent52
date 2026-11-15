"""AgentCore Runtime entry point (Req. 23.1, 23.2, 23.3, 23.5, 25.4).

Payload: ``{session_id, owner, profile, request_text, period?, appeal_of?}`` as ``api/handler.py``
sends it. ``handle`` validates it, returns an acknowledgement at once, and runs the one shared
``run_session`` in a background thread with a StoreSink on the DynamoDB Session_Store. No credentials
live in the image or the code: boto3 uses the runtime's execution role.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable

from guide.tribunal import session_view as sv

logger = logging.getLogger(__name__)

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
NAMESPACE = "AlphaForgeGuide"


class PayloadError(ValueError):
    """The payload is not a valid session start request."""


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise PayloadError("payload must be a JSON object")
    bad = []
    if not isinstance(payload.get("session_id"), str) or not _ID.match(payload["session_id"]):
        bad.append("session_id")
    if not isinstance(payload.get("owner"), str) or not payload["owner"].strip() or "/" in payload["owner"]:
        bad.append("owner")
    if not isinstance(payload.get("profile"), dict):
        bad.append("profile")
    if not isinstance(payload.get("request_text"), str) or not payload["request_text"].strip():
        bad.append("request_text")
    period = payload.get("period")
    if period is not None:
        if not (isinstance(period, dict) and set(period) == {"start", "end"}):
            bad.append("period")
        else:
            try:
                if date.fromisoformat(period["start"]) >= date.fromisoformat(period["end"]):
                    bad.append("period")
            except (TypeError, ValueError):
                bad.append("period")
    if payload.get("appeal_of") is not None and not (
            isinstance(payload["appeal_of"], str) and _ID.match(payload["appeal_of"])):
        bad.append("appeal_of")
    if bad:
        raise PayloadError("invalid payload fields: " + ", ".join(bad))
    return payload


def emit_metrics(counts: dict[str, int], out: Any = None) -> None:
    """Write one CloudWatch Embedded Metric Format line (Req. 25.4)."""
    doc = {
        "_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [
            {"Namespace": NAMESPACE, "Dimensions": [[]], "Metrics": [{"Name": k, "Unit": "Count"} for k in counts]}]},
        **counts,
    }
    print(json.dumps(doc), file=out or sys.stdout, flush=True)


def _trace_counts(trace: list[dict[str, Any]]) -> dict[str, int]:
    text = [json.dumps(e, default=str) for e in trace]
    return {
        "GuardrailInterventions": sum(1 for e in trace if e.get("kind") == "guardrail_block"),
        "BedrockThrottles": sum(1 for t in text if "ThrottlingException" in t),
        "CacheFallbacks": sum(1 for e in trace if e.get("kind") == "cache_fallback"),
    }


@dataclass
class Deps:
    """Everything the runner touches; tests inject fakes, ``default_deps`` builds the real ones."""

    config: Any
    store: Any  # DynamoSessionStore (also the PrecedentItemStore)
    run_session: Callable[..., Any]
    source_factory: Callable[[], Any]
    memory_factory: Callable[[str], Any | None] = lambda owner: None
    personas: Callable[[], dict[str, Any]] = field(default=lambda: {})
    emit: Callable[[dict[str, int]], None] = emit_metrics
    tracer: Any = None


def default_deps() -> Deps:
    from guide.config import load_config
    from guide.contract.personas import load_personas
    from guide.data.loader import SnapshotStore
    from guide.memory import MemoryStore
    from guide.session.store import DynamoSessionStore
    from guide.tribunal.entrypoint import run_session

    config = load_config()

    def memory(owner: str) -> Any | None:
        if not config.agentcore_memory_id:
            return None
        return MemoryStore(config, owner)

    return Deps(config=config, store=DynamoSessionStore(config.session_table), run_session=run_session,
                source_factory=lambda: SnapshotStore(config).pin(), memory_factory=memory,
                personas=lambda: dict(load_personas().personas))


_RISK_ORDER = ("low", "low_to_moderate", "moderate", "high", "very_high")
# The fallback base comes from the case-study personas only, so a custom profile gets a
# Base_Portfolio grounded in the official case (the extra personas are team-written).
CASE_PERSONAS = ("amira", "mateo", "robert")


def closest_persona_base(risk_level: Any, personas: dict[str, Any]) -> dict[str, float] | None:
    """Base_Portfolio for a profile without a persona: the persona with the closest risk level."""
    target = _RISK_ORDER.index(risk_level) if risk_level in _RISK_ORDER else _RISK_ORDER.index("moderate")
    best = None
    case = [pid for pid in sorted(personas) if pid in CASE_PERSONAS]
    for pid in case or sorted(personas):
        persona = personas[pid]
        values = persona.contract_values
        if "base_portfolio" not in values:
            continue
        level = getattr(persona, "risk_level", None)
        if level not in _RISK_ORDER:
            continue
        distance = abs(_RISK_ORDER.index(level) - target)
        if best is None or distance < best[0]:
            best = (distance, values["base_portfolio"].value)
    return dict(best[1]) if best else None


def build_request(payload: dict[str, Any], deps: Deps, source: Any):
    """Build the SessionRequest like ``guide/run_session.py`` (ValueError on bad input)."""
    from guide.contract.base_portfolio import split_profile, validate_base_portfolio
    from guide.contract.profiler import build_contract_from_form, build_contract_from_persona
    from guide.toolkit import metrics
    from guide.tribunal.entrypoint import SessionRequest
    from guide.tribunal.request_parser import MissingFields, parse_request

    profile = payload["profile"]
    personas = deps.personas()
    persona = None
    if profile.get("base_persona_id") is not None:
        persona = personas.get(profile["base_persona_id"])
        if persona is None:
            raise ValueError("unknown base_persona_id")
    values, custom_base = split_profile(profile)
    values = values or {}
    contract = (build_contract_from_form(values, persona) if (values or persona is None)
                else build_contract_from_persona(persona))
    universe = set(source.read_table(metrics.UNIVERSE_TABLE)["ticker"])
    # Base_Portfolio: the investor's own holdings first, then the persona's, then the closest case persona's.
    base = validate_base_portfolio(custom_base, universe) if custom_base is not None else None
    if not base and persona is not None and "base_portfolio" in persona.contract_values:
        base = persona.contract_values["base_portfolio"].value
    if not base:
        base = closest_persona_base(contract.get("risk_level"), personas)

    parsed = parse_request(payload["request_text"], universe)
    if isinstance(parsed, MissingFields):
        raise ValueError(f"request is missing: {parsed.as_dict()}")
    period = payload.get("period")
    if period:
        start, end = date.fromisoformat(period["start"]), date.fromisoformat(period["end"])
    else:
        end = date.fromisoformat(str(source.read_table("prices_daily")["date"].max())[:10])
        start = end - timedelta(days=365 * 5)
    return SessionRequest(
        contract, parsed.ticker, parsed.weight_fraction, start, end, text=payload["request_text"],
        session_id=payload["session_id"], profile_id=profile.get("profile_id"),
        base_portfolio=dict(base) if base else None)


def run_payload(payload: dict[str, Any], deps: Deps) -> sv.SessionView | None:
    """Run one session to the end; every failure ends as a failed SessionView in the store."""
    from guide.session.store import StoreSink
    from guide.trace.recorder import TraceRecorder

    owner, session_id = payload["owner"], payload["session_id"]
    deps.emit({"SessionsStarted": 1})
    stage, view = "runtime", None
    try:
        source = deps.source_factory()
        request = build_request(payload, deps, source)
        memory = None
        try:
            memory = deps.memory_factory(owner)
        except Exception as error:  # memory is optional; a failure never blocks the session
            logger.warning("memory unavailable: %s", type(error).__name__)
        trace = TraceRecorder(emit_spans=True, tracer=deps.tracer)
        view = deps.run_session(request, StoreSink(deps.store, owner), config=deps.config, source=source,
                                memory=memory, precedents=deps.store, trace=trace)
        counts = _trace_counts(list(getattr(view, "trace", None) or trace.to_list()))
        counts["SessionsFailed"] = 1 if getattr(view, "status", "") == "failed" else 0
        deps.emit(counts)
        return view
    except Exception as error:
        stage = getattr(error, "stage", stage)
        message = getattr(error, "message", None) or f"{type(error).__name__}"
        logger.error("session %s failed at %s: %s", session_id, stage, type(error).__name__)
        try:
            deps.store.put_view(owner, sv.failed(sv.new_session_view(session_id), stage, str(message)))
        except Exception as store_error:
            logger.error("could not write failed view: %s", type(store_error).__name__)
        deps.emit({"SessionsFailed": 1})
        return None


def handle(payload: Any, deps: Deps, spawn: Callable[[Callable[[], Any]], Any] | None = None) -> dict[str, Any]:
    """Validate, start the session in the background, and acknowledge before the Verdict exists."""
    try:
        payload = validate_payload(payload)
    except PayloadError as error:
        return {"status": "rejected", "error": str(error)}

    def work() -> None:
        run_payload(payload, deps)

    if spawn is None:
        threading.Thread(target=work, name=f"session-{payload['session_id']}", daemon=True).start()
    else:
        spawn(work)
    return {"status": "accepted", "session_id": payload["session_id"]}


def main() -> None:  # pragma: no cover - needs the AgentCore SDK and AWS
    from bedrock_agentcore.runtime import BedrockAgentCoreApp

    app = BedrockAgentCoreApp()
    deps = default_deps()

    @app.entrypoint
    def invoke(payload: dict[str, Any]) -> dict[str, Any]:
        def spawn(work: Callable[[], Any]) -> None:
            # add_async_task / complete_async_task keep /ping at HealthyBusy while the thread runs.
            task_id = app.add_async_task("tribunal_session")

            def wrapped() -> None:
                try:
                    work()
                finally:
                    app.complete_async_task(task_id)

            threading.Thread(target=wrapped, daemon=True).start()

        return handle(payload, deps, spawn)

    app.run()


if __name__ == "__main__":  # pragma: no cover
    main()
