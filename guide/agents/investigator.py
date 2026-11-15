"""Investigator agent: material risks per Option (Req. 4.4, 4.5, 36).

One Bedrock call, no calls to other agents. Code validates the JSON against a schema
and checks that every named Exhibit and every named Investor_Contract field or
Soft_Preference exists. A risk that fails a check is returned in ``rejected`` so the
orchestrator can ask for a revision (up to 2) and then drop it with a Trace record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from guide.agents.base import AgentOutput, BedrockAgent, StageFailure
from guide.agents.instructions import load_system_prompt
from guide.config import Config
from guide.toolkit.exhibits import ExhibitRegistry
from guide.trace.recorder import TraceRecorder

AGENT = "investigator"

# One material risk. `exhibits` may be empty when the risk rests on a Hard_Rule result
# (code-computed law, no Exhibit number); `contract_fields` must then name the rule's field.
RISK_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "required": ["risk", "exhibits", "why_for_this_person", "contract_fields"],
    "properties": {
        "risk": {"type": "string", "minLength": 1},
        "exhibits": {"type": "array", "items": {"type": "integer", "minimum": 1}},
        "why_for_this_person": {"type": "string", "minLength": 1},
        "contract_fields": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
    },
}

# Envelope only: a malformed single risk is rejected on its own (check_findings),
# it no longer throws away the Investigator's whole contribution.
OUTPUT_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "required": ["per_option"],
    "properties": {
        "per_option": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["option_id", "material_risks"],
                "properties": {
                    "option_id": {"type": "string", "minLength": 1},
                    "material_risks": {"type": "array"},
                },
            },
        }
    },
}
_VALIDATOR = Draft202012Validator(OUTPUT_SCHEMA)
_RISK_VALIDATOR = Draft202012Validator(RISK_SCHEMA)

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "contract" / "schema.json"
_CAP_MAPS = ("sector_caps", "per_asset_class_caps")


def contract_field_names(contract: Mapping[str, Any]) -> frozenset[str]:
    """Names the Investigator may cite: contract fields, cap-map keys, Soft_Preference ids."""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    names = {n for n in schema["properties"] if n not in ("provenance", "soft_preferences")}
    names.add("base_portfolio")
    for cap_map in _CAP_MAPS:
        for key in (contract.get(cap_map) or {}):
            names.add(f"{cap_map}.{key}")
    for pref in contract.get("soft_preferences") or []:
        if isinstance(pref, Mapping) and pref.get("id"):
            names.add(str(pref["id"]))
            names.add(f"soft_preferences.{pref['id']}")
    return frozenset(names)


@dataclass(frozen=True)
class Rejection:
    option_id: str
    risk: str
    reasons: tuple[str, ...]


@dataclass
class InvestigatorResult:
    per_option: list[dict[str, Any]] = field(default_factory=list)  # validated findings
    rejected: list[Rejection] = field(default_factory=list)
    blocked: bool = False


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
        raise StageFailure(AGENT, "output does not match the Investigator schema")
    return data


def check_findings(
    data: Mapping[str, Any],
    contract: Mapping[str, Any],
    registry: ExhibitRegistry,
    option_ids: Sequence[str],
) -> InvestigatorResult:
    """Keep risks whose Exhibits and contract fields exist and whose option is known."""
    allowed_fields = contract_field_names(contract)
    known_options = set(option_ids)
    result = InvestigatorResult()
    for entry in data["per_option"]:
        option_id = entry["option_id"]
        kept: list[dict[str, Any]] = []
        for risk in entry["material_risks"]:
            reasons: list[str] = []
            if next(iter(_RISK_VALIDATOR.iter_errors(risk)), None) is not None:
                label = risk.get("risk") if isinstance(risk, Mapping) else None
                result.rejected.append(Rejection(option_id, str(label or "?"), ("malformed risk",)))
                continue
            if option_id not in known_options:
                reasons.append(f"unknown option {option_id}")
            reasons += [f"Exhibit {n} does not exist" for n in risk["exhibits"] if registry.get(n) is None]
            reasons += [
                f"contract field or Soft_Preference {f!r} does not exist"
                for f in risk["contract_fields"]
                if f not in allowed_fields
            ]
            if reasons:
                result.rejected.append(Rejection(option_id, risk["risk"], tuple(reasons)))
            else:
                kept.append({k: risk[k] for k in RISK_SCHEMA["required"]})
        result.per_option.append({"option_id": option_id, "material_risks": kept})
    return result


def build_messages(
    options: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
    allowed_fields: Sequence[str] | None = None,
    recent_context: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """User message: Options with Risk_Panel Exhibit numbers and Hard_Rule results, the contract."""
    payload = {
        "options": list(options),
        "investor_contract": dict(contract),
        "allowed_contract_fields": sorted(allowed_fields or contract_field_names(contract)),
    }
    if recent_context:
        payload["recent_context"] = list(recent_context)
    return [{"role": "user", "content": [{"text": json.dumps(payload, default=str, sort_keys=True)}]}]


def run_investigator(
    config: Config,
    options: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
    registry: ExhibitRegistry,
    tools: Any,
    trace: TraceRecorder,
    *,
    client: Any | None = None,
    tool_runner: Any | None = None,
    recent_context: Sequence[Mapping[str, Any]] | None = None,
) -> InvestigatorResult:
    """Call the Investigator once; raise StageFailure on invalid output (Req. 36 fallback)."""
    prompt = load_system_prompt(AGENT, Path(config.instruction_dir))
    agent = BedrockAgent(
        AGENT,
        config,
        client=client,
        tool_runner=tool_runner,
        stage=AGENT,
        max_tokens=6000,
        max_tool_rounds=6,
    )
    output: AgentOutput = agent.run(prompt, build_messages(options, contract, recent_context=recent_context),
                                     tools, trace)
    if output.blocked:
        return InvestigatorResult(blocked=True)
    data = parse_output(output.text)
    return check_findings(data, contract, registry, [str(o["option_id"]) for o in options])
