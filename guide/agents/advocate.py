"""Advocate agent: the goal behind the request and at most 3 Options (Req. 4.1, 4.2, 4.8, 4.9).

The Advocate runs once per session. Code validates its JSON: option count, the
``advocate_scope`` rule, at least one smaller position size, and no buy or sell
wording. The Advocate never decides a Hard_Rule; code does that for every Option.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import re
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any

from guide.agents.base import AgentOutput, BedrockAgent, StageFailure
from guide.agents.instructions import SystemPrompt, load_system_prompt
from guide.config import ADVOCATE_SCOPES, Config
from guide.trace.recorder import TraceRecorder

AGENT = "advocate"
MAX_OPTIONS = 3
MAX_TOOL_CALLS = 6
EPS = 1e-9

_BUY_SELL = re.compile(r"\b(?:buy|buys|buying|bought|sell|sells|selling|sold)\b", re.IGNORECASE)
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


@dataclass(frozen=True)
class AdvocateOption:
    asset: str
    weight: float
    rationale: str
    exhibits: tuple[int, ...]


@dataclass(frozen=True)
class AdvocateOutput:
    goal: str
    options: tuple[AdvocateOption, ...]


def advocate_system_prompt(config: Config) -> SystemPrompt:
    return load_system_prompt(AGENT, Path(config.instruction_dir))


def _fail(reason: str) -> StageFailure:
    return StageFailure(AGENT, reason)


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{name} must be a non-empty string")
    if _BUY_SELL.search(value):
        raise _fail(f"{name} uses buy or sell wording")
    return value.strip()


def parse_advocate_output(
    text: str,
    *,
    request_ticker: str,
    request_weight: float,
    scope: str,
    universe: Collection[str] | None = None,
) -> AdvocateOutput:
    """Validate the Advocate JSON; raise StageFailure on any violation."""
    if scope not in ADVOCATE_SCOPES:
        raise ValueError(f"advocate_scope must be one of {', '.join(ADVOCATE_SCOPES)}")
    body = _FENCE.sub("", (text or "").strip())
    try:
        data = json.loads(body)
    except ValueError:
        # Tolerate a short preamble or trailing remark around the JSON object.
        start, end = body.find("{"), body.rfind("}")
        try:
            data = json.loads(body[start:end + 1]) if 0 <= start < end else None
        except ValueError:
            data = None
    if data is None:
        raise _fail("output is not valid JSON")
    if not isinstance(data, Mapping) or set(data) - {"goal", "options"}:
        raise _fail("output must be an object with goal and options only")

    goal = _text(data.get("goal"), "goal")
    raw = data.get("options")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_OPTIONS:
        raise _fail(f"options must be a list of 1 to {MAX_OPTIONS} items")

    allowed = {u.upper() for u in universe} if universe is not None else None
    options: list[AdvocateOption] = []
    seen: set[tuple[str, float]] = set()
    for item in raw:
        if not isinstance(item, Mapping) or set(item) != {"asset", "weight", "rationale", "exhibits"}:
            raise _fail("each option needs asset, weight, rationale, and exhibits")
        asset, weight, exhibits = item["asset"], item["weight"], item["exhibits"]
        if not isinstance(asset, str) or not asset.strip():
            raise _fail("option asset must be a ticker")
        asset = asset.strip()
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= weight <= 1:
            raise _fail("option weight must be a fraction between 0 and 1")
        if (
            not isinstance(exhibits, list)
            or not exhibits
            or any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in exhibits)
        ):
            raise _fail("option exhibits must be a non-empty list of Exhibit numbers")
        if scope == "size_only" and (asset.upper() != request_ticker.upper() or weight >= request_weight - EPS):
            raise _fail("size_only scope allows only a smaller size of the requested asset")
        if scope == "universe" and allowed is not None and asset.upper() not in allowed:
            raise _fail(f"asset {asset} is not in the assets universe")
        key = (asset.upper(), round(float(weight), 6))
        if key in seen:
            raise _fail("duplicate option")
        seen.add(key)
        options.append(AdvocateOption(asset, float(weight), _text(item["rationale"], "rationale"),
                                      tuple(dict.fromkeys(exhibits))))

    if not any(o.asset.upper() == request_ticker.upper() and o.weight < request_weight - EPS for o in options):
        raise _fail("no option reduces the requested position size")
    return AdvocateOutput(goal, tuple(options))


def build_messages(
    request_text: str,
    request_ticker: str,
    request_weight: float,
    contract: Mapping[str, Any],
    risk_panel: Mapping[str, Any],
    scope: str,
    hard_rule_results: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """The single user message: request, Investor_Contract, Risk_Panel (Exhibit numbers and
    values), the request's Hard_Rule results (evidence, not a verdict), and scope."""
    payload = {
        "request": {"text": request_text, "asset": request_ticker, "weight": request_weight},
        "advocate_scope": scope,
        "investor_contract": contract,
        "risk_panel": risk_panel,
    }
    if hard_rule_results is not None:
        payload["request_hard_rule_results"] = list(hard_rule_results)
    return [{"role": "user", "content": [{"text": json.dumps(payload, default=str, sort_keys=True)}]}]


def run_advocate(
    config: Config,
    *,
    request_text: str,
    request_ticker: str,
    request_weight: float,
    contract: Mapping[str, Any],
    risk_panel: Mapping[str, Any],
    tools: Any,
    trace: TraceRecorder,
    hard_rule_results: Sequence[Mapping[str, Any]] | None = None,
    universe: Collection[str] | None = None,
    system_prompt: SystemPrompt | None = None,
    client: Any | None = None,
    tool_runner: Any | None = None,
) -> AdvocateOutput:
    """Call the Advocate once and return validated Options; raise StageFailure otherwise."""
    prompt = system_prompt or advocate_system_prompt(config)
    model_id = config.model_ids.get(AGENT) or config.model_id
    agent = BedrockAgent(
        AGENT,
        replace(config, model_id=model_id),
        client=client,
        tool_runner=tool_runner,
        max_tokens=4096,
        max_tool_rounds=MAX_TOOL_CALLS,
        guard_text=request_text,
    )
    output: AgentOutput = agent.run(
        prompt,
        build_messages(request_text, request_ticker, request_weight, contract, risk_panel,
                       config.advocate_scope, hard_rule_results),
        tools,
        trace,
    )
    if output.blocked:
        raise _fail("guardrail intervened")
    return parse_advocate_output(
        output.text,
        request_ticker=request_ticker,
        request_weight=request_weight,
        scope=config.advocate_scope,
        universe=universe,
    )
