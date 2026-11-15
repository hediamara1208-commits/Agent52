"""Citation_Validator: every claim cites existing Exhibits and states their numbers.

Requirements 4.1 to 4.6, 4.8. Code decides validity; agents only revise.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from guide.toolkit.exhibits import ExhibitRegistry
from guide.trace.recorder import TraceEvent, TraceRecorder

ROUNDING_EPS = 1e-9


@dataclass(frozen=True)
class NumberRef:
    """A number stated in a claim and the Exhibit value it must match.

    `field` is a dotted path into a mapping Exhibit value; empty for a scalar value.
    `decimals` is the number of decimals stated in the claim; when None the
    comparison uses the tolerance passed to `validate_claim`.
    """
    value: float
    exhibit_number: int
    field: str = ""
    decimals: int | None = None


@dataclass
class Claim:
    text: str
    citations: list[int] = field(default_factory=list)
    numbers: list[NumberRef] = field(default_factory=list)
    # Investigator claims name an Investor_Contract field or Soft_Preference (Req. 4.5).
    contract_ref: str | None = None


@dataclass(frozen=True)
class CitationIssue:
    code: str  # no_citation | unknown_exhibit | unknown_field | not_numeric | number_mismatch | no_contract_ref
    message: str
    exhibit_number: int | None = None


def _lookup(value: Any, path: str) -> Any:
    if not path:
        return value
    cur = value
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        elif isinstance(cur, (tuple, list)) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            raise KeyError(path)
    return cur


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def numbers_match(stated: float, exhibit_value: float, decimals: int | None, tol: float) -> bool:
    """Equal after rounding the Exhibit value to the decimals stated in the claim (Req. 4.7)."""
    if decimals is None:
        return abs(stated - exhibit_value) <= tol
    return abs(round(exhibit_value, decimals) - round(stated, decimals)) <= ROUNDING_EPS


def validate_claim(claim: Claim, registry: ExhibitRegistry, tol: float = 1e-4,
                   require_contract_ref: bool = False,
                   known_contract_refs: Sequence[str] | None = None) -> list[CitationIssue]:
    """Return the issues that make `claim` invalid; an empty list means valid."""
    issues: list[CitationIssue] = []
    if not claim.citations:
        issues.append(CitationIssue("no_citation", "claim cites no Exhibit"))
    for n in claim.citations:
        if registry.get(n) is None:
            issues.append(CitationIssue("unknown_exhibit", f"Exhibit {n} is not in the registry", n))
    for ref in claim.numbers:
        ex = registry.get(ref.exhibit_number)
        if ex is None:
            issues.append(CitationIssue("unknown_exhibit",
                                        f"Exhibit {ref.exhibit_number} is not in the registry",
                                        ref.exhibit_number))
            continue
        try:
            actual = _lookup(ex.value, ref.field)
        except KeyError:
            issues.append(CitationIssue("unknown_field",
                                        f"Exhibit {ex.number} has no field '{ref.field}'", ex.number))
            continue
        if not _is_number(actual) or not _is_number(ref.value):
            issues.append(CitationIssue("not_numeric",
                                        f"Exhibit {ex.number} field '{ref.field}' is not comparable", ex.number))
        elif not numbers_match(float(ref.value), float(actual), ref.decimals, tol):
            issues.append(CitationIssue(
                "number_mismatch",
                f"claim states {ref.value} but Exhibit {ex.number} gives {actual}", ex.number))
    if require_contract_ref:
        ref_name = (claim.contract_ref or "").strip()
        if not ref_name or (known_contract_refs is not None and ref_name not in known_contract_refs):
            issues.append(CitationIssue("no_contract_ref",
                                        "claim names no existing contract field or Soft_Preference"))
    return issues


Reviser = Callable[[Claim, list[CitationIssue]], "Claim | None"]


def enforce(agent: str, claims: Sequence[Claim], registry: ExhibitRegistry,
            max_revisions: int = 2, revise: Reviser | None = None,
            recorder: TraceRecorder | None = None, tol: float = 1e-4,
            require_contract_ref: bool = False,
            known_contract_refs: Sequence[str] | None = None,
            ) -> tuple[list[Claim], list[TraceEvent]]:
    """Keep valid claims; return failing ones to `revise` up to `max_revisions` times.

    A claim still invalid after the revisions (or when `revise` is None or returns None)
    is removed and recorded with `claim_removed`. Returns the surviving claims and the
    Trace events created here.
    """
    rec = recorder or TraceRecorder(emit_spans=False)
    kept: list[Claim] = []
    events: list[TraceEvent] = []
    for original in claims:
        current: Claim | None = original
        attempts = 0
        while True:
            issues = validate_claim(current, registry, tol, require_contract_ref, known_contract_refs)
            if not issues:
                kept.append(current)
                break
            if revise is None or attempts >= max_revisions:
                events.append(rec.claim_removed(agent, original.text))
                break
            attempts += 1
            revised = revise(current, issues)
            if revised is None:
                events.append(rec.claim_removed(agent, original.text))
                break
            current = revised
    return kept, events
