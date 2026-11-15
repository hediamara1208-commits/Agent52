"""Judge-side Guidance_Only_Rule check and statement removal.

Requirements 5.11, 5.12, 13.1, 13.6. Deterministic: a fixed pattern list, no model.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass, replace
from typing import Any

from guide.trace.recorder import TraceEvent, TraceRecorder

GUIDANCE_ONLY_MESSAGE = (
    "The Guide_System only provides guidance. It never places, routes, prefills, "
    "or triggers an order, transfer, or brokerage or bank action. "
    "Statements that did so were removed."
)

_ACTION = r"(?:orders?|trades?|transfers?|transactions?|purchases?|sales?|wires?|payments?|withdrawals?|deposits?)"
_VERB = (r"(?:place|submit|send|route|execute|initiate|trigger|confirm|make|complete|"
         r"authori[sz]e|buy|sell|wire|transfer|withdraw|deposit|move)")

# (name, pattern). Patterns are matched case-insensitively against each statement.
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(expr, re.IGNORECASE))
    for name, expr in (
        # Imperative order or transfer instructions.
        ("imperative_order",
         rf"\b(?:please\s+)?{_VERB}\s+(?:the|your|this|a|an|that|these|those)\s+(?:\w+\s+){{0,2}}{_ACTION}\b"),
        ("imperative_transfer",
         r"\b(?:transfer|wire|move|send|withdraw|deposit)\s+(?:the\s+|your\s+|these\s+)?(?:funds|money|cash|capital|\$\s?\d[\d,.]*)"),
        ("imperative_trade",
         r"\b(?:buy|sell|purchase|short)\s+(?:now|immediately|today|\d[\d,.]*\s*(?:shares|units|%)|\$\s?\d)"),
        # Simulated execution.
        ("simulated_execution",
         r"\b(?:order|trade|transfer|transaction|purchase|payment)s?\s+"
         r"(?:has\s+been\s+|have\s+been\s+|was\s+|were\s+|is\s+)?"
         r"(?:submitted|placed|confirmed|executed|filled|completed|sent|routed|processed)\b"),
        ("simulated_execution_done",
         rf"\b(?:i|we)(?:\s+have|'ve)?\s+(?:placed|submitted|executed|sent|routed|bought|sold|transferred)\b"),
        # Prefill or trigger language.
        ("prefill_or_trigger",
         r"\b(?:pre-?\s?fill(?:ed)?|pre-?\s?populated?|auto-?\s?fill(?:ed)?)\s+(?:\w+\s+){0,2}"
         r"(?:order|ticket|trade|transfer|form)\b"),
        ("one_click",
         r"\b(?:one[-\s]click|1-click)\s+(?:buy|sell|trade|order|transfer|purchase)\b"),
        ("trigger_action",
         rf"\b(?:click|press|tap)\s+(?:here\s+)?to\s+(?:buy|sell|trade|transfer|{_VERB}\s+(?:the\s+)?{_ACTION})\b"),
    )
)

# A negation shortly before a match ("never place the order") makes it a prohibition, not an instruction.
_NEGATION = re.compile(
    r"\b(?:not|never|no|cannot|can't|won't|don't|doesn't|do\s+not|does\s+not|without|nor)\b[^.;!?]{0,30}$",
    re.IGNORECASE,
)


@dataclass
class GuidanceFinding:
    agent: str
    statement: str
    passed: bool
    matched_pattern: str | None


def _match(statement: str) -> str | None:
    for name, pattern in PATTERNS:
        for m in pattern.finditer(statement):
            if _NEGATION.search(statement[: m.start()]):
                continue
            return name
    return None


def check_guidance_only(agent: str, statements: Sequence[str],
                        recorder: TraceRecorder | None = None) -> list[GuidanceFinding]:
    """Check each statement; return one finding per statement, in order.

    When `recorder` is given, one `judge_check` event records pass or fail for the whole output.
    """
    findings = []
    for s in statements:
        name = _match(s)
        findings.append(GuidanceFinding(agent, s, name is None, name))
    if recorder is not None:
        failed = [f for f in findings if not f.passed]
        recorder.judge_check(
            "guidance_only",
            {"agent": agent, "statements": len(findings)},
            {"result": "fail" if failed else "pass",
             "patterns": sorted({f.matched_pattern for f in failed})},
        )
    return findings


def guidance_message(findings: Sequence[GuidanceFinding]) -> str | None:
    """The UI message when any finding failed, else None."""
    return GUIDANCE_ONLY_MESSAGE if any(not f.passed for f in findings) else None


def _strip(value: Any, bad: set[str]) -> Any:
    if isinstance(value, str):
        return "" if value in bad else value
    if isinstance(value, Mapping):
        return {k: _strip(v, bad) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        kept = [_strip(v, bad) for v in value if not (isinstance(v, str) and v in bad)]
        return type(value)(kept) if isinstance(value, tuple) else kept
    if is_dataclass(value) and not isinstance(value, type):
        return replace(value, **{f.name: _strip(getattr(value, f.name), bad) for f in fields(value)})
    return value


def strip_violations(ruling: Any, findings: Sequence[GuidanceFinding],
                     recorder: TraceRecorder | None = None) -> tuple[Any, list[TraceEvent]]:
    """Remove every failing statement from `ruling` and record each removal.

    `ruling` may be a dataclass, mapping, list, or string; list entries equal to a failing
    statement are dropped and scalar string fields equal to one are emptied. The input is not mutated.
    """
    rec = recorder or TraceRecorder(emit_spans=False)
    bad = {f.statement for f in findings if not f.passed}
    events = [rec.claim_removed(f.agent, f.statement) for f in findings if not f.passed]
    return (_strip(ruling, bad) if bad else ruling), events
