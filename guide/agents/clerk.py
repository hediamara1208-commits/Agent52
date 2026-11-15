"""Clerk: assembles the Ruling from a code template (no model call; Req. 6, 3.8, 3.9, 13.7, 16.16).

Every sentence is template text filled with values from code: rule results, the Verdict,
Sensitivity_Analysis results, the Investor_Contract, and the Exhibit registry. Disclaimers,
survivorship-bias text, and unsupported-topic notices are inserted here, so no agent can
omit them. Facts carry Exhibit numbers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from guide.contract.personas import Persona
from guide.data import quality
from guide.data.snapshot import SnapshotInfo
from guide.toolkit.exhibits import ExhibitRegistry
from guide.tribunal.rules import RuleRequest, RuleResult, Verdict
from guide.tribunal.sensitivity import SensitivityResult

CHANGE_SECTION_TITLE = "What would change the verdict"

DISCLAIMERS = (
    "This output is a simulation.",
    "This output is not personalized financial advice.",
    "This output does not predict future returns.",
)
ESG_SCORES_NOTICE = (
    "The Dataset has no ESG scores; the fossil fuel screen uses the exclusion list in the "
    "Dataset only."
)
ALIGNMENT_TEXT = (
    "Calendar alignment: dates where every held asset has a price (date intersection), "
    "portfolio rebalanced daily."
)
GUIDANCE_TEMPLATE = "You may wish to consider {item} and decide personally."

# Rule name -> Investor_Contract field it checks.
RULE_FIELD = {
    "per_asset_cap": "per_asset_cap",
    "per_asset_class_caps": "per_asset_class_caps",
    "sector_caps": "sector_caps",
    "crypto_cap": "crypto_cap",
    "max_volatility": "max_volatility",
    "max_drawdown": "max_drawdown",
    "speculative_limit": "speculative_limit",
    "esg_exclusion": "esg_exclusions",
}
ASSUMED_PROVENANCE = ("persona_assumption", "default")


@dataclass(frozen=True)
class Statement:
    text: str
    citations: tuple[int, ...] = ()


QUESTIONS = (
    ("which_data", "Which data?"),
    ("why_this_choice", "Why this choice?"),
    ("which_limits", "Which limits?"),
    ("what_would_change", "What would change the answer?"),
)
APPEAL_TEMPLATE = (
    "You may wish to consider an Appeal that changes the contract field {name}; "
    "the tribunal would run again with that value."
)


@dataclass
class Answer:
    """One headed answer of Req. 33.1; every statement carries Exhibit numbers when it has facts."""

    id: str
    heading: str
    statements: list[Statement] = field(default_factory=list)


@dataclass
class Ruling:
    verdict: str
    facts: list[Statement] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    fictional_scenarios: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    what_would_change: list[Statement] = field(default_factory=list)
    disclaimers: list[str] = field(default_factory=lambda: list(DISCLAIMERS))
    questions: list[Answer] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def stm(s: Statement) -> dict[str, Any]:
            return {"text": s.text, "citations": list(s.citations)}

        return {
            "verdict": self.verdict,
            "facts": [stm(s) for s in self.facts],
            "assumptions": list(self.assumptions),
            "fictional_scenarios": list(self.fictional_scenarios),
            "limits": list(self.limits),
            CHANGE_SECTION_TITLE: [stm(s) for s in self.what_would_change],
            "what_would_change": [stm(s) for s in self.what_would_change],
            "disclaimers": list(self.disclaimers),
            "questions": [
                {"id": a.id, "heading": a.heading, "statements": [stm(x) for x in a.statements]}
                for a in self.questions
            ],
        }

    def statements(self) -> list[str]:
        """Every sentence of the Ruling, for the guidance-only check."""
        out = [s.text for s in self.facts] + list(self.assumptions) + list(self.fictional_scenarios)
        out += list(self.limits) + [s.text for s in self.what_would_change] + list(self.disclaimers)
        out += [x.text for a in self.questions for x in a.statements]
        return out


def rationales_from_persona(persona: Persona | None) -> dict[str, str]:
    """Contract field -> Persona_File rationale."""
    if persona is None:
        return {}
    return {k: v.rationale for k, v in persona.contract_values.items() if v.rationale}


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f} %"


def _fact_text(r: RuleResult) -> str:
    if r.rule == "esg_exclusion":
        held = f" ({r.detail})" if r.detail else ""
        return f"Rule esg_exclusion: {r.status}; excluded holdings: {int(r.observed or 0)}{held}."
    where = f" [{r.detail}]" if r.detail else ""
    if r.status == "unverified":
        return f"Rule {r.rule}{where}: unverified; limit {_pct(r.limit)}."
    return f"Rule {r.rule}{where}: {r.status}; observed {_pct(r.observed)} against a limit of {_pct(r.limit)}."


def _facts(verdict: Verdict, results: Sequence[RuleResult]) -> list[Statement]:
    facts: list[Statement] = []
    cited = sorted({n for r in results for n in r.exhibits} | set(verdict.exhibits))
    if verdict.exhibits or cited:
        text = f"Verdict computed by code: {verdict.verdict}"
        if verdict.max_weight is not None:
            text += f"; largest position size meeting every rule: {_pct(verdict.max_weight)}"
        facts.append(Statement(text + ".", tuple(verdict.exhibits or cited)))
    for r in results:
        if r.exhibits:  # a Fact without an Exhibit does not exist (Req. 6.2)
            facts.append(Statement(_fact_text(r), tuple(r.exhibits)))
    return facts


def _assumptions(contract: Mapping[str, Any], results: Sequence[RuleResult], request: RuleRequest,
                 snapshot: SnapshotInfo | None, rationales: Mapping[str, str]) -> list[str]:
    out = [
        f"Period: {request.start.isoformat()} to {request.end.isoformat()}.",
        "Currency: CAD; USD amounts converted with the USD/CAD series.",
        ALIGNMENT_TEXT,
    ]
    if request.as_of is not None:
        out.append(f"No observation after {request.as_of.isoformat()} is used.")
    if snapshot is not None:
        out.append(
            f"Snapshot_Id {snapshot.snapshot_id}, retrieved {snapshot.retrieved_at.date().isoformat()}."
        )
    prov = contract.get("provenance") or {}
    seen: set[str] = set()
    for r in results:
        name = RULE_FIELD.get(r.rule)
        if name is None or name in seen:
            continue
        seen.add(name)
        origin = prov.get(name)
        if origin not in ASSUMED_PROVENANCE:
            continue
        why = rationales.get(name) or "no Persona_File rationale recorded"
        out.append(f"Contract field {name} = {contract.get(name)!r} ({origin}): {why}.")
    return out


def _scenarios(request: RuleRequest, verdict: Verdict) -> list[str]:
    out = [
        f"Simulation: {_pct(request.weight)} of the portfolio in {request.ticker} from "
        f"{request.start.isoformat()} to {request.end.isoformat()}."
    ]
    if verdict.max_weight is not None and abs(verdict.max_weight - request.weight) > 1e-9:
        out.append(
            f"Simulation: {_pct(verdict.max_weight)} of the portfolio in {request.ticker} "
            "is the largest size on the 0.5-point grid that meets every rule."
        )
    return out


def _limits(contract: Mapping[str, Any], results: Sequence[RuleResult], verdict: Verdict,
            registry: ExhibitRegistry, snapshot: SnapshotInfo | None, requested_text: str,
            sensitivity: Sequence[SensitivityResult]) -> list[str]:
    out = [
        quality.survivorship_bias_text(),
        f"Volatility is one risk indicator. Your {contract.get('horizon_years', 'stated')}-year "
        "horizon, diversification across holdings, and your stated preferences also matter.",
    ]
    topics = quality.detect_unsupported_topics(requested_text)
    if contract.get("esg_exclusions") and "ESG scores" not in topics:
        topics.append("ESG scores")
    notice = quality.unsupported_notice(topics)
    if notice:
        out.append(notice)
    if contract.get("esg_exclusions"):
        out.append(ESG_SCORES_NOTICE)
    if verdict.unverified_rules:
        out.append("Unverified rules: " + ", ".join(verdict.unverified_rules) + ".")
    if snapshot is not None and snapshot.served_from == "cache_fallback":
        out.append(quality.fallback_note(snapshot))
    numbers = {n for r in results for n in r.exhibits} | set(verdict.exhibits)
    numbers |= {s.exhibit for s in sensitivity}
    for n in sorted(numbers):
        ex = registry.get(n)
        for note in (ex.processing_notes if ex else ()):
            if note == quality.CNQ_NOTE and note not in out:
                out.append(note)
    return out


def _changes(sensitivity: Sequence[SensitivityResult], verdict: Verdict) -> list[Statement]:
    out = [Statement(s.text, (s.exhibit,)) for s in sensitivity]
    for cond in verdict.conditions:
        out.append(Statement(GUIDANCE_TEMPLATE.format(item=cond.rstrip(".")), ()))
    return out


def _which_data(request: RuleRequest, snapshot: SnapshotInfo | None, registry: ExhibitRegistry,
                numbers: Sequence[int]) -> list[Statement]:
    tables: set[str] = set()
    for n in numbers:
        ex = registry.get(n)
        tables |= set(ex.source_files if ex else ())
    out = []
    if tables:
        out.append(Statement("Tables used: " + ", ".join(sorted(tables)) + ".", tuple(numbers)))
    out.append(Statement(
        f"Period: {request.start.isoformat()} to {request.end.isoformat()}; amounts in CAD.", ()))
    if snapshot is not None:
        out.append(Statement(
            f"Snapshot_Id {snapshot.snapshot_id}, retrieved {snapshot.retrieved_at.date().isoformat()}.", ()))
    return out


def _why_this_choice(verdict: Verdict, results: Sequence[RuleResult],
                     contract: Mapping[str, Any]) -> list[Statement]:
    out = [Statement(f"Verdict computed by code: {verdict.verdict}.", tuple(verdict.exhibits))]
    deciding = [r for r in results if r.status != "pass" and r.rule in set(verdict.failing_rules) | set(verdict.unverified_rules)]
    for r in deciding:
        out.append(Statement(_fact_text(r), tuple(r.exhibits)))
    if not deciding:
        out.append(Statement("Every Hard_Rule passed at the requested size.", tuple(verdict.exhibits)))
    for pref in contract.get("soft_preferences") or []:
        if isinstance(pref, Mapping) and pref.get("text"):
            out.append(Statement(f"Soft_Preference {pref.get('id', '')}: {pref['text']}".rstrip(), ()))
    return out


def _appeal_hints(verdict: Verdict, results: Sequence[RuleResult]) -> list[Statement]:
    names: list[str] = []
    for r in results:
        name = RULE_FIELD.get(r.rule)
        if r.status == "fail" and name and name not in names:
            names.append(name)
    return [Statement(APPEAL_TEMPLATE.format(name=n), ()) for n in names]


def _questions(verdict: Verdict, results: Sequence[RuleResult], contract: Mapping[str, Any],
               request: RuleRequest, registry: ExhibitRegistry, snapshot: SnapshotInfo | None,
               limits: Sequence[str], changes: Sequence[Statement],
               facts: Sequence[Statement]) -> list[Answer]:
    numbers = sorted({n for f in facts for n in f.citations})
    body = {
        "which_data": _which_data(request, snapshot, registry, numbers),
        "why_this_choice": _why_this_choice(verdict, results, contract),
        "which_limits": [Statement(t, ()) for t in limits],
        "what_would_change": list(changes) + _appeal_hints(verdict, results),
    }
    return [Answer(i, h, body[i]) for i, h in QUESTIONS]


def build_ruling(
    *,
    verdict: Verdict,
    rule_results: Sequence[RuleResult],
    sensitivity: Sequence[SensitivityResult],
    contract: Mapping[str, Any],
    request: RuleRequest,
    registry: ExhibitRegistry,
    snapshot: SnapshotInfo | None = None,
    rationales: Mapping[str, str] | None = None,
    requested_text: str = "",
) -> Ruling:
    """Assemble the Ruling. No model is called; the Verdict is never altered."""
    facts = _facts(verdict, rule_results)
    limits = _limits(contract, rule_results, verdict, registry, snapshot, requested_text, sensitivity)
    changes = _changes(sensitivity, verdict)
    return Ruling(
        verdict=verdict.verdict,
        facts=facts,
        assumptions=_assumptions(contract, rule_results, request, snapshot, rationales or {}),
        fictional_scenarios=_scenarios(request, verdict),
        limits=limits,
        what_would_change=changes,
        questions=_questions(verdict, rule_results, contract, request, registry, snapshot,
                             limits, changes, facts),
    )
