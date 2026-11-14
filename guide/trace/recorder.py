"""Trace recorder (Req. 8.3, 9.1-9.6).

Stores only short summaries, never raw model reasoning. Each event has a
timestamp and a sequence number. Events are optionally emitted as
OpenTelemetry spans (AgentCore Observability); if OpenTelemetry is not
installed, recording still works.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

try:  # optional dependency
    from opentelemetry import trace as _otel_trace
except Exception:  # pragma: no cover - depends on environment
    _otel_trace = None

MAX_SUMMARY_CHARS = 300
_EXHIBIT_RE = re.compile(r"Exhibit\s+(\d+)", re.IGNORECASE)


def _summ(value: Any, limit: int = MAX_SUMMARY_CHARS) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, sort_keys=True)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


@dataclass(frozen=True)
class TraceEvent:
    seq: int
    timestamp: str
    kind: str  # agent_call | tool_call | judge_check | guardrail_block | claim_removed
    name: str
    summary: dict = field(default_factory=dict)
    exhibit_number: int | None = None


class TraceRecorder:
    def __init__(self, emit_spans: bool = True, tracer: Any = None):
        self._events: list[TraceEvent] = []
        self._lock = threading.Lock()
        self._tracer = None
        if emit_spans:
            try:
                if tracer is not None:
                    self._tracer = tracer
                elif _otel_trace is not None:
                    self._tracer = _otel_trace.get_tracer("agentic-investment-guide")
            except Exception:
                self._tracer = None

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

    def _record(self, kind: str, name: str, summary: dict, exhibit_number: int | None = None) -> TraceEvent:
        with self._lock:
            ev = TraceEvent(
                seq=len(self._events) + 1,
                timestamp=datetime.now(timezone.utc).isoformat(),
                kind=kind,
                name=name,
                summary=summary,
                exhibit_number=exhibit_number,
            )
            self._events.append(ev)
        self._emit_span(ev)
        return ev

    def _emit_span(self, ev: TraceEvent) -> None:
        if self._tracer is None:
            return
        try:
            with self._tracer.start_as_current_span(f"{ev.kind}:{ev.name}") as span:
                span.set_attribute("guide.seq", ev.seq)
                span.set_attribute("guide.kind", ev.kind)
                if ev.exhibit_number is not None:
                    span.set_attribute("guide.exhibit_number", ev.exhibit_number)
                for k, v in ev.summary.items():
                    span.set_attribute(f"guide.{k}", str(v))
        except Exception:
            pass  # observability must never break the pipeline

    def agent_call(self, agent: str, input_summary: str, output_summary: str) -> TraceEvent:
        return self._record("agent_call", agent,
                            {"input": _summ(input_summary), "output": _summ(output_summary)})

    def tool_call(self, name: str, args: Mapping | Any, exhibit_number: int | None) -> TraceEvent:
        return self._record("tool_call", name, {"args": _summ(args)}, exhibit_number)

    def judge_check(self, rule: str, inputs: Any, result: Any) -> TraceEvent:
        return self._record("judge_check", rule,
                            {"inputs": _summ(inputs), "result": _summ(result)})

    def guardrail_block(self, stage: str, rule: str) -> TraceEvent:
        return self._record("guardrail_block", stage, {"rule": _summ(rule)})

    def claim_removed(self, agent: str, claim: str) -> TraceEvent:
        return self._record("claim_removed", agent, {"claim": _summ(claim)})

    def to_list(self) -> list[dict]:
        return [asdict(e) for e in self._events]

    def export_json(self) -> str:
        return json.dumps(self.to_list(), indent=2, ensure_ascii=False)

    def trace_chain(self, statement: Any, exhibits: Any = None) -> dict:
        return trace_chain(statement, exhibits)


def trace_chain(statement: Any, exhibits: Any = None) -> dict:
    """Link a statement to its Exhibit numbers and their source_files.

    `statement` is a string or an object with `.text` and optionally
    `.exhibit_numbers`. `exhibits` is anything with `get(number)` returning an
    object/dict with `source_files` (e.g. ExhibitRegistry).
    """
    text = statement if isinstance(statement, str) else getattr(statement, "text", str(statement))
    numbers = getattr(statement, "exhibit_numbers", None)
    if numbers is None:
        numbers = [int(n) for n in _EXHIBIT_RE.findall(text)]
    numbers = sorted(set(int(n) for n in numbers))

    source_files: list[str] = []
    missing: list[int] = []
    for n in numbers:
        ex = exhibits.get(n) if exhibits is not None else None
        if ex is None:
            missing.append(n)
            continue
        files = ex.get("source_files", ()) if isinstance(ex, Mapping) else getattr(ex, "source_files", ())
        for f in files:
            if f not in source_files:
                source_files.append(f)
    return {
        "statement": text,
        "exhibit_numbers": numbers,
        "source_files": source_files,
        "unresolved_exhibits": missing,
    }
