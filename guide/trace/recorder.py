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

DATA_EVENT_KINDS = ("snapshot_pinned", "cache_fallback", "ingestion_aborted")
_EXHIBIT_RE = re.compile(r"Exhibit\s+(\d+)", re.IGNORECASE)


def _summ(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str, sort_keys=True)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..." if limit > 3 else text[:limit]


@dataclass(frozen=True)
class TraceEvent:
    seq: int
    timestamp: str
    kind: str  # agent_call | tool_call | judge_check | guardrail_block | claim_removed
    name: str
    summary: dict = field(default_factory=dict)
    exhibit_number: int | None = None


class TraceRecorder:
    def __init__(self, emit_spans: bool = True, tracer: Any = None, max_summary_chars: int | None = None):
        if max_summary_chars is None:
            from guide.config import load_config  # Req. 9.6: limit comes from config
            max_summary_chars = load_config().trace_summary_max_chars
        if isinstance(max_summary_chars, bool) or max_summary_chars <= 0:
            raise ValueError("max_summary_chars must be greater than zero")
        self._max_chars = int(max_summary_chars)
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

    def _s(self, value: Any) -> str:
        return _summ(value, self._max_chars)

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

    def agent_call(self, agent: str, input_summary: str, output_summary: str,
                   instruction_hash: str | None = None) -> TraceEvent:
        summary = {"input": self._s(input_summary), "output": self._s(output_summary)}
        if instruction_hash is not None:
            summary["instruction_hash"] = str(instruction_hash)  # full hash, never truncated (Req. 9.8)
        return self._record("agent_call", agent, summary)

    def tool_call(self, name: str, args: Mapping | Any, exhibit_number: int | None) -> TraceEvent:
        return self._record("tool_call", name, {"args": self._s(args)}, exhibit_number)

    def judge_check(self, rule: str, inputs: Any, result: Any) -> TraceEvent:
        return self._record("judge_check", rule,
                            {"inputs": self._s(inputs), "result": self._s(result)})

    def guardrail_block(self, stage: str, rule: str) -> TraceEvent:
        return self._record("guardrail_block", stage, {"rule": self._s(rule)})

    def claim_removed(self, agent: str, claim: str) -> TraceEvent:
        return self._record("claim_removed", agent, {"claim": self._s(claim)})

    def data_event(self, kind: str, snapshot_id: str, retrieved_at: str, cause: str | None = None) -> TraceEvent:
        """Record a data-layer event (Req. 9.7, 17.10)."""
        if kind not in DATA_EVENT_KINDS:
            raise ValueError(f"data event kind must be one of {', '.join(DATA_EVENT_KINDS)}")
        summary = {"snapshot_id": self._s(snapshot_id), "retrieved_at": self._s(retrieved_at)}
        if cause is not None:
            summary["cause"] = self._s(cause)
        return self._record(kind, kind, summary)

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
