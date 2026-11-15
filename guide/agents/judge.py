"""Judge agent: decides the Verdict, assesses Soft_Preferences, writes the narrative (Req. 29, 36).

Like a court: code supplies the evidence (Risk_Panels, Hard_Rule results, the largest size meeting
every rule) and the law (the Hard_Rules); the Advocate pleads Options and the Investigator names
their risks; the Judge alone decides which Option to adopt and the Verdict. Code then checks the
decision against the law (``check_decision``): adopting an Option that breaks a Hard_Rule is
not allowed. No verdict exists before the Judge rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from guide.agents.base import AgentOutput, BedrockAgent, StageFailure
from guide.agents.instructions import SystemPrompt, load_system_prompt
from guide.agents.investigator import contract_field_names
from guide.config import Config
from guide.toolkit.exhibits import ExhibitRegistry
from guide.trace.recorder import TraceRecorder
from guide.tribunal.rules import ACCEPT, ACCEPT_WITH_CONDITIONS, REJECT, Verdict

AGENT = "judge"
ASSESSMENTS = ("satisfied", "tension", "not_satisfied")

OUTPUT_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "required": ["assessments", "narrative", "decision"],
    "additionalProperties": False,
    "properties": {
        "assessments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["option_id", "preference_id", "assessment", "findings", "exhibits"],
                "additionalProperties": False,
                "properties": {
                    "option_id": {"type": "string", "minLength": 1},
                    "preference_id": {"type": "string", "minLength": 1},
                    "assessment": {"enum": list(ASSESSMENTS)},
                    "findings": {"type": "string", "minLength": 1},
                    "exhibits": {"type": "array", "minItems": 1, "items": {"type": "integer", "minimum": 1}},
                },
            },
        },
        "narrative": {"type": "string", "minLength": 1},
        "decision": {
            "type": "object",
            "required": ["verdict", "option_id", "conditions", "reason", "exhibits"],
            "additionalProperties": False,
            "properties": {
                "verdict": {"enum": [ACCEPT, ACCEPT_WITH_CONDITIONS, REJECT]},
                "option_id": {"type": ["string", "null"]},
                "conditions": {"type": "array", "items": {"type": "string", "minLength": 1}},
                "reason": {"type": "string", "minLength": 1},
                "exhibits": {"type": "array", "minItems": 1, "items": {"type": "integer", "minimum": 1}},
            },
        },
        # Req. 31.2: contract fields that explain a Verdict different from the Precedent's.
        "precedent_fields": {"type": "array", "items": {"type": "string", "minLength": 1}},
    },
}
_VALIDATOR = Draft202012Validator(OUTPUT_SCHEMA)

# Higher rank = more cautious. A Soft_Preference may only move a Verdict up this scale.
_CAUTION = {ACCEPT: 0, ACCEPT_WITH_CONDITIONS: 1, REJECT: 2}


@dataclass(frozen=True)
class Rejection:
    option_id: str
    preference_id: str
    reasons: tuple[str, ...]


@dataclass
class JudgeResult:
    assessments: list[dict[str, Any]] = field(default_factory=list)  # validated
    narrative: str = ""
    rejected: list[Rejection] = field(default_factory=list)
    blocked: bool = False
    precedent_fields: list[str] = field(default_factory=list)  # named fields that exist (Req. 31.2)
    unknown_precedent_fields: list[str] = field(default_factory=list)
    decision: dict[str, Any] | None = None  # the Judge's ruling, before the code check


def parse_output(text: str) -> dict[str, Any]:
    """Parse and schema-validate the agent JSON; raise StageFailure when invalid."""
    body = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", body, re.DOTALL)
    if fenced:
        body = fenced.group(1)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        # Tolerate a short preamble or trailing remark around the JSON object.
        start, end = body.find("{"), body.rfind("}")
        try:
            data = json.loads(body[start:end + 1]) if 0 <= start < end else None
        except json.JSONDecodeError:
            data = None
    if data is None:
        raise StageFailure(AGENT, "output is not valid JSON")
    if next(iter(_VALIDATOR.iter_errors(data)), None) is not None:
        raise StageFailure(AGENT, "output does not match the Judge schema")
    return data


def check_assessments(
    data: Mapping[str, Any],
    contract: Mapping[str, Any],
    registry: ExhibitRegistry,
    passing_option_ids: Sequence[str],
) -> JudgeResult:
    """Keep assessments for passing Options, existing Soft_Preferences and existing Exhibits.

    An assessment of an Option that fails a Hard_Rule is dropped: Soft_Preferences are weighed
    only for Options that pass (Req. 29.2).
    """
    preference_ids = {
        str(p["id"]) for p in contract.get("soft_preferences") or [] if isinstance(p, Mapping) and p.get("id")
    }
    passing = set(passing_option_ids)
    result = JudgeResult(narrative=data["narrative"])
    for item in data["assessments"]:
        reasons: list[str] = []
        if item["option_id"] not in passing:
            reasons.append(f"option {item['option_id']} does not pass the Hard_Rules or is unknown")
        if item["preference_id"] not in preference_ids:
            reasons.append(f"Soft_Preference {item['preference_id']!r} does not exist")
        reasons += [f"Exhibit {n} does not exist" for n in item["exhibits"] if registry.get(n) is None]
        if reasons:
            result.rejected.append(Rejection(item["option_id"], item["preference_id"], tuple(reasons)))
        else:
            result.assessments.append(dict(item))
    return result


def differing_fields(contract: Mapping[str, Any], precedent: Mapping[str, Any] | None) -> list[str]:
    """Top-level Investor_Contract fields whose value differs from the Precedent's contract."""
    other = (precedent or {}).get("contract")
    if not isinstance(other, Mapping):
        return []
    skip = {"provenance"}
    return sorted(k for k in set(contract) | set(other) if k not in skip and contract.get(k) != other.get(k))


def check_precedent_fields(
    named: Sequence[str], contract: Mapping[str, Any]
) -> tuple[list[str], list[str]]:
    """Split the fields the Judge named into (existing, unknown), by code (Req. 31.2)."""
    allowed = contract_field_names(contract)
    kept: list[str] = []
    unknown: list[str] = []
    for name in dict.fromkeys(named):
        (kept if name in allowed else unknown).append(name)
    return kept, unknown


def check_decision(
    decision: Mapping[str, Any] | None,
    options: Sequence[Mapping[str, Any]],
    registry: ExhibitRegistry,
    request_option_id: str,
) -> list[str]:
    """Check the Judge's ruling against the law (the Hard_Rules); return the objections.

    An empty list means the ruling stands. Code never picks the Verdict itself here.
    """
    if not decision:
        return ["the Judge returned no decision"]
    objections: list[str] = []
    by_id = {str(o["option_id"]): o for o in options}
    verdict = decision.get("verdict")
    option_id = decision.get("option_id")
    missing = [n for n in decision.get("exhibits") or [] if registry.get(n) is None]
    if missing:
        objections.append(f"cited Exhibits do not exist: {missing}")
    if verdict in (ACCEPT, ACCEPT_WITH_CONDITIONS):
        option = by_id.get(str(option_id)) if option_id is not None else None
        if option is None:
            objections.append(f"option {option_id!r} does not exist; adopt one of {sorted(by_id)} or reject")
        elif option.get("rejected"):
            objections.append(
                f"option {option_id} breaks the Hard_Rules {option.get('failing_rules')}; "
                "a Hard_Rule cannot be overruled, adopt an option that passes every rule or reject")
        elif verdict == ACCEPT and str(option_id) != request_option_id:
            objections.append("accept means the request as stated; adopting a different option is "
                              "accept_with_conditions with the new size as a condition")
    return objections


def verdict_from_decision(
    decision: Mapping[str, Any],
    options: Sequence[Mapping[str, Any]],
    rule_facts: Verdict,
) -> Verdict:
    """The Verdict the Judge ruled (call only after ``check_decision`` returned no objection)."""
    by_id = {str(o["option_id"]): o for o in options}
    verdict = decision["verdict"]
    option = by_id.get(str(decision.get("option_id"))) if verdict != REJECT else None
    conditions = [str(c) for c in decision.get("conditions") or []]
    if option is not None and verdict == ACCEPT_WITH_CONDITIONS and not conditions:
        conditions = [f"Keep the position in {option['ticker']} at or below {option['weight']:.1%} of the portfolio."]
    return Verdict(
        verdict=verdict,
        max_weight=float(option["weight"]) if option is not None else None,
        failing_rules=list(rule_facts.failing_rules),
        unverified_rules=list(rule_facts.unverified_rules),
        conditions=conditions,
        tension=rule_facts.tension,
        exhibits=sorted(set(rule_facts.exhibits) | {int(n) for n in decision.get("exhibits") or []}),
        reason=str(decision["reason"]),
    )


def apply_soft_preferences(
    verdict: Verdict,
    assessments: Sequence[Mapping[str, Any]],
    retained_option_id: str | None,
    contract: Mapping[str, Any],
) -> Verdict:
    """Return the Verdict after Soft_Preferences. Code forbids any upgrade (Req. 29.3, 29.4).

    The only change allowed: accept becomes accept_with_conditions when a Soft_Preference is
    ``not_satisfied`` for the retained Option, with a plain-language condition. A reject, a
    failing Hard_Rule, or an existing accept_with_conditions is never changed.
    """
    if verdict.verdict != ACCEPT or retained_option_id is None:
        return verdict
    texts = {
        str(p.get("id")): str(p.get("text", ""))
        for p in contract.get("soft_preferences") or []
        if isinstance(p, Mapping)
    }
    unmet = [
        a for a in assessments
        if a["option_id"] == retained_option_id and a["assessment"] == "not_satisfied"
    ]
    if not unmet:
        return verdict
    conditions = list(verdict.conditions)
    for a in unmet:
        text = texts.get(str(a["preference_id"]), str(a["preference_id"]))
        conditions.append(f"This option does not meet your stated preference: {text} Review it before relying on this result.")
    updated = replace(
        verdict,
        verdict=ACCEPT_WITH_CONDITIONS,
        conditions=conditions,
        exhibits=sorted(set(verdict.exhibits) | {n for a in unmet for n in a["exhibits"]}),
        reason=f"{verdict.reason} A Soft_Preference is not satisfied by the retained option.",
    )
    if _CAUTION[updated.verdict] < _CAUTION[verdict.verdict]:  # defensive; cannot happen
        return verdict
    return updated


def build_messages(
    *,
    hard_rule_results: Sequence[Mapping[str, Any]],
    options: Sequence[Mapping[str, Any]],
    investigator_findings: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
    rule_facts: Mapping[str, Any],
    precedent: Mapping[str, Any] | None = None,
    objection: Sequence[str] | None = None,
    recent_context: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """The single user message: the evidence and the pleadings. No verdict is given to the Judge."""
    payload = {
        "hard_rule_results": list(hard_rule_results),
        "options": list(options),
        "investigator_findings": list(investigator_findings),
        "soft_preferences": list(contract.get("soft_preferences") or []),
        "investor_contract": dict(contract),
        "rule_facts": dict(rule_facts),
        "closest_precedent": dict(precedent) if precedent else None,
        "precedent_differing_contract_fields": differing_fields(contract, precedent),
    }
    if objection:
        payload["objection_to_previous_ruling"] = list(objection)
    if recent_context:
        payload["recent_context"] = list(recent_context)
    return [{"role": "user", "content": [{"text": json.dumps(payload, default=str, sort_keys=True)}]}]


def run_judge(
    config: Config,
    *,
    hard_rule_results: Sequence[Mapping[str, Any]],
    options: Sequence[Mapping[str, Any]],
    investigator_findings: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
    rule_facts: Mapping[str, Any],
    passing_option_ids: Sequence[str],
    registry: ExhibitRegistry,
    trace: TraceRecorder,
    precedent: Mapping[str, Any] | None = None,
    objection: Sequence[str] | None = None,
    recent_context: Sequence[Mapping[str, Any]] | None = None,
    system_prompt: SystemPrompt | None = None,
    client: Any | None = None,
) -> JudgeResult:
    """Call the Judge once (no tools); raise StageFailure on invalid output (Req. 36 fallback)."""
    prompt = system_prompt or load_system_prompt(AGENT, Path(config.instruction_dir))
    model_id = config.model_ids.get(AGENT) or config.model_id
    agent = BedrockAgent(AGENT, replace(config, model_id=model_id), client=client, stage=AGENT, max_tokens=6000)
    messages = build_messages(
        hard_rule_results=hard_rule_results,
        options=options,
        investigator_findings=investigator_findings,
        contract=contract,
        rule_facts=rule_facts,
        precedent=precedent,
        objection=objection,
        recent_context=recent_context,
    )
    output: AgentOutput = agent.run(prompt, messages, None, trace)
    if output.blocked:
        return JudgeResult(blocked=True)
    data = parse_output(output.text)
    result = check_assessments(data, contract, registry, passing_option_ids)
    result.decision = dict(data["decision"])
    if precedent:
        result.precedent_fields, result.unknown_precedent_fields = check_precedent_fields(
            data.get("precedent_fields", []), contract)
    return result
