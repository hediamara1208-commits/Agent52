"""Safe Amazon Bedrock Converse wrapper for Guide agents.

The wrapper applies the configured Bedrock Guardrail to every call, executes
Bedrock Converse tool-use turns, and records only sanitized response summaries.
It deliberately does not manage credentials: boto3 uses the standard AWS
credential chain supplied by the runtime role or developer environment.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import random
import time
from typing import Any, Callable, Mapping, Protocol, Sequence

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from guide.agents.instructions import SystemPrompt
from guide.config import Config
from guide.trace.recorder import TraceRecorder


GUIDANCE_ONLY_MESSAGE = (
    "The Guide_System only provides guidance. It cannot place, route, prefill, "
    "or trigger an order, transfer, or brokerage or bank action."
)
"""Safe user-facing message returned after a guidance-only guardrail block."""

_GUIDANCE_ONLY_RULE = "Guidance_Only_Rule"
_CHALLENGE_RULES = "Challenge_Rules"
_ACTION_TERMS = (
    "place an order",
    "place order",
    "submit an order",
    "submit order",
    "buy shares",
    "sell shares",
    "transfer funds",
    "wire transfer",
    "brokerage action",
    "bank action",
    "prefill",
    "pre-fill",
    "trigger an order",
    "order submitted",
    "trade confirmed",
)
_RETURN_PREDICTION_TERMS = ("return prediction", "guaranteed return", "will return")
_PERSONAL_ADVICE_TERMS = ("personalized financial advice", "personal financial advice")


class ToolRunner(Protocol):
    """Minimal tool runner interface consumed by :class:`BedrockAgent`."""

    def __call__(self, tool_use: Mapping[str, Any]) -> Any:
        """Execute one validated Bedrock ``toolUse`` request."""


class StageFailure(RuntimeError):
    """A model-stage failure safe for the orchestrator and UI to report."""

    def __init__(self, stage: str, reason: str = "Bedrock Converse call failed") -> None:
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}: {reason}")


@dataclass(frozen=True)
class AgentOutput:
    """Sanitized result of a completed agent run.

    ``message`` and ``content`` never include a Bedrock ``reasoningContent``
    block. Callers can pass ``text`` to a Ruling safely without exposing hidden
    model reasoning.
    """

    message: Mapping[str, Any]
    content: tuple[Mapping[str, Any], ...]
    stop_reason: str
    blocked: bool = False
    challenge_rule: str | None = None

    @property
    def text(self) -> str:
        """Join visible text blocks without interpreting tool-use payloads."""
        return "\n".join(
            str(block["text"])
            for block in self.content
            if isinstance(block, Mapping) and isinstance(block.get("text"), str)
        )


class BedrockAgent:
    """Call Amazon Bedrock Converse for one tribunal agent.

    ``tools`` passed to :meth:`run` can be a complete Bedrock ``toolConfig``
    mapping or an iterable of tool declarations. A tool runner is injected at
    construction time, or may be supplied by an object exposing ``run`` passed
    as ``tools``. The latter keeps the wrapper independent from the Toolkit.
    """

    def __init__(
        self,
        agent: str,
        config: Config,
        *,
        client: Any | None = None,
        tool_runner: ToolRunner | Callable[[Mapping[str, Any]], Any] | None = None,
        stage: str | None = None,
        max_tokens: int = 4096,  # Sonnet 5.5 spends output tokens on hidden reasoning first
        guard_text: str | None = None,
        max_tool_rounds: int = 8,
        max_throttling_retries: int = 3,
        base_backoff_seconds: float = 0.25,
        sleep: Callable[[float], None] = time.sleep,
        random_source: Callable[[], float] = random.random,
    ) -> None:
        if not agent.strip():
            raise ValueError("agent must not be empty")
        if not config.model_id.strip():
            raise ValueError("model_id is required for Bedrock Converse")
        if not config.guardrail_id.strip():
            raise ValueError("guardrail_id is required for every Bedrock Converse call")
        if not config.guardrail_version.strip():
            raise ValueError("guardrail_version is required for every Bedrock Converse call")
        if max_tokens <= 0 or max_tool_rounds <= 0 or max_throttling_retries < 0:
            raise ValueError("Bedrock retry and output limits must be valid")
        if base_backoff_seconds < 0:
            raise ValueError("base_backoff_seconds must be zero or greater")

        self.agent = agent
        self.stage = stage or agent
        self.config = config
        self.tool_runner = tool_runner
        self.max_tokens = max_tokens
        # Only this text (the user's own words) is checked by the Guardrail's input filters
        # (prompt attack). Code-built JSON, Exhibits and tool results are not user input.
        self.guard_text = (guard_text or "").strip() or "Simulated investment tribunal session."
        self.max_tool_rounds = max_tool_rounds
        self.max_throttling_retries = max_throttling_retries
        self.base_backoff_seconds = base_backoff_seconds
        self._sleep = sleep
        self._random = random_source
        # The wrapper owns throttling behavior, so botocore performs no hidden
        # retries. This makes the three-retry requirement observable in Trace.
        self.client = client or boto3.client(
            "bedrock-runtime",
            region_name=config.aws_region,
            config=BotoConfig(retries={"total_max_attempts": 1, "mode": "standard"}),
        )

    def run(
        self,
        system_prompt: "str | SystemPrompt",
        messages: Sequence[Mapping[str, Any]],
        tools: Mapping[str, Any] | Sequence[Mapping[str, Any]] | Any | None,
        trace: TraceRecorder,
        instruction_hash: str | None = None,
    ) -> AgentOutput:
        """Run the Converse tool-use loop and return sanitized output.

        ``system_prompt`` is the composed text or a ``SystemPrompt`` from the
        Instruction_Loader; the latter also supplies the Instruction_Hash that
        is recorded on every agent_call event (Req. 9.8, 21.8).

        Every individual Converse call, including follow-up turns after a tool
        result, includes the configured Bedrock Guardrail.
        """
        if isinstance(system_prompt, SystemPrompt):
            instruction_hash = instruction_hash or system_prompt.instruction_hash
            system_prompt = system_prompt.text
        if not isinstance(system_prompt, str):
            raise ValueError("system_prompt must be text")
        conversation = [deepcopy(dict(message)) for message in messages]
        tool_config = self._tool_config(tools)

        for tool_round in range(self.max_tool_rounds + 1):
            response = self._converse(system_prompt, conversation, tool_config)
            output_message = self._sanitized_message(response)
            stop_reason = str(response.get("stopReason", ""))

            if stop_reason == "guardrail_intervened":
                rule = self._guardrail_reason(response) or self._challenge_rule(conversation, output_message)
                trace.guardrail_block(self.stage, rule)
                trace.agent_call(self.agent, "Bedrock Converse invocation", "guardrail intervened",
                                 instruction_hash=instruction_hash)
                return AgentOutput(
                    message={"role": "assistant", "content": [{"text": GUIDANCE_ONLY_MESSAGE}]},
                    content=({"text": GUIDANCE_ONLY_MESSAGE},),
                    stop_reason=stop_reason,
                    blocked=True,
                    challenge_rule=rule,
                )

            tool_uses = [block["toolUse"] for block in output_message["content"] if "toolUse" in block]
            if not tool_uses:
                output = AgentOutput(
                    message=output_message,
                    content=tuple(output_message["content"]),
                    stop_reason=stop_reason,
                )
                trace.agent_call(self.agent, "Bedrock Converse invocation", output.text or stop_reason,
                                 instruction_hash=instruction_hash)
                return output

            if tool_round == self.max_tool_rounds:
                raise StageFailure(self.stage, "maximum tool-use rounds exceeded")

            conversation.append(output_message)
            conversation.append(
                {
                    "role": "user",
                    "content": [self._tool_result_block(tool_use, tools, trace) for tool_use in tool_uses],
                }
            )

        raise StageFailure(self.stage, "maximum tool-use rounds exceeded")  # pragma: no cover

    def _converse(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tool_config: Mapping[str, Any] | None,
    ) -> Mapping[str, Any]:
        request: dict[str, Any] = {
            "modelId": self.config.model_id,
            "system": [{"text": system_prompt}],
            "messages": self._with_guard_content(messages),
            "inferenceConfig": {"maxTokens": self.max_tokens},
            "guardrailConfig": {
                "guardrailIdentifier": self.config.guardrail_id,
                "guardrailVersion": self.config.guardrail_version,
                "trace": "enabled",  # so a block names its policy in the Trace
            },
        }
        if tool_config is not None:
            request["toolConfig"] = dict(tool_config)

        for retry in range(self.max_throttling_retries + 1):
            try:
                response = self.client.converse(**request)
                if not isinstance(response, Mapping):
                    raise StageFailure(self.stage, "Bedrock Converse returned an invalid response")
                return response
            except Exception as error:
                if not self._is_throttling(error):
                    if isinstance(error, StageFailure):
                        raise
                    raise StageFailure(self.stage) from error
                if retry >= self.max_throttling_retries:
                    raise StageFailure(self.stage, "Bedrock Converse throttled after 3 retries") from error
                delay = self.base_backoff_seconds * (2**retry) + (
                    self.base_backoff_seconds * max(0.0, self._random())
                )
                self._sleep(delay)

        raise StageFailure(self.stage)  # pragma: no cover

    @staticmethod
    def _is_throttling(error: Exception) -> bool:
        if isinstance(error, ClientError):
            return error.response.get("Error", {}).get("Code") == "ThrottlingException"
        response = getattr(error, "response", None)
        return isinstance(response, Mapping) and response.get("Error", {}).get("Code") == "ThrottlingException"

    @staticmethod
    def _sanitized_message(response: Mapping[str, Any]) -> dict[str, Any]:
        message = response.get("output", {}).get("message", {})
        if not isinstance(message, Mapping):
            return {"role": "assistant", "content": []}
        content = message.get("content", [])
        if not isinstance(content, list):
            content = []
        # Content block variants are mutually exclusive. Removing the whole
        # block prevents reasoning text and signatures entering Trace/Ruling.
        safe_content = [deepcopy(block) for block in content if isinstance(block, Mapping) and "reasoningContent" not in block]
        return {"role": str(message.get("role", "assistant")), "content": safe_content}

    @staticmethod
    def _tool_config(tools: Mapping[str, Any] | Sequence[Mapping[str, Any]] | Any | None) -> Mapping[str, Any] | None:
        if tools is None:
            return None
        if isinstance(tools, Mapping):
            if "tools" in tools:
                return tools
            return {"tools": [tools]}
        config = getattr(tools, "tool_config", None)
        if callable(config):
            config = config()
        if isinstance(config, Mapping) and "tools" in config:
            return config
        if isinstance(tools, Sequence) and not isinstance(tools, (str, bytes)):
            return {"tools": list(tools)}
        raise ValueError("tools must be Bedrock tool declarations or provide tool_config")

    def _tool_result_block(
        self,
        tool_use: Mapping[str, Any],
        tools: Any,
        trace: TraceRecorder,
    ) -> dict[str, Any]:
        runner = self.tool_runner or getattr(tools, "run", None)
        if not callable(runner):
            raise StageFailure(self.stage, "Bedrock requested a tool but no tool runner is configured")

        try:
            result = runner(tool_use)
        except Exception as error:
            raise StageFailure(self.stage, f"tool {tool_use.get('name', 'unknown')} failed") from error

        trace.tool_call(
            str(tool_use.get("name", "unknown")),
            tool_use.get("input", {}),
            self._exhibit_number(result),
        )
        return self._normalise_tool_result(tool_use, result)

    @staticmethod
    def _normalise_tool_result(tool_use: Mapping[str, Any], result: Any) -> dict[str, Any]:
        tool_use_id = str(tool_use.get("toolUseId", ""))
        if not tool_use_id:
            raise StageFailure("tool", "Bedrock toolUse is missing toolUseId")
        if isinstance(result, Mapping) and isinstance(result.get("toolResult"), Mapping):
            tool_result = deepcopy(dict(result["toolResult"]))
            tool_result["toolUseId"] = tool_use_id
            return {"toolResult": tool_result}

        if isinstance(result, Mapping) and "content" in result:
            content = deepcopy(result["content"])
            status = result.get("status")
        elif isinstance(result, str):
            content = [{"text": result}]
            status = None
        else:
            content = [{"json": json.loads(json.dumps(result, default=str))}]
            status = None

        if not isinstance(content, list):
            content = [{"json": content}]
        tool_result: dict[str, Any] = {"toolUseId": tool_use_id, "content": content}
        if status in {"success", "error"}:
            tool_result["status"] = status
        return {"toolResult": tool_result}

    @staticmethod
    def _exhibit_number(result: Any) -> int | None:
        if not isinstance(result, Mapping):
            return None
        for key in ("exhibit_number", "exhibitNumber"):
            value = result.get(key)
            if isinstance(value, int):
                return value
        exhibit = result.get("exhibit")
        if isinstance(exhibit, Mapping) and isinstance(exhibit.get("number"), int):
            return exhibit["number"]
        return None

    @staticmethod
    def _challenge_rule(
        messages: Sequence[Mapping[str, Any]], output_message: Mapping[str, Any]
    ) -> str:
        visible_text = " ".join(
            BedrockAgent._text_from_message(message) for message in (*messages, output_message)
        ).lower()
        if any(term in visible_text for term in _ACTION_TERMS):
            return _GUIDANCE_ONLY_RULE
        if any(term in visible_text for term in _RETURN_PREDICTION_TERMS):
            return "No_Return_Predictions"
        if any(term in visible_text for term in _PERSONAL_ADVICE_TERMS):
            return "No_Personalized_Financial_Advice"
        return _CHALLENGE_RULES

    def _with_guard_content(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Tag the user's own text as the only Guardrail-checked input (guardContent).

        With a guardContent block present, Converse applies the input filters to that block
        only; the model output is still checked in full (denied topics).
        """
        out = [dict(m) for m in messages]
        if any("guardContent" in b for m in out for b in m.get("content", []) if isinstance(b, Mapping)):
            return out
        for m in out:
            if m.get("role") == "user":
                m["content"] = list(m.get("content", [])) + [{"guardContent": {"text": {"text": self.guard_text}}}]
                break
        return out

    @staticmethod
    def _guardrail_reason(response: Mapping[str, Any]) -> str | None:
        """Name the Guardrail policy that blocked, e.g. 'output:topic:ReturnPredictions'."""
        trace = ((response.get("trace") or {}).get("guardrail") or {})
        found: list[str] = []

        def scan(where: str, assessment: Mapping[str, Any]) -> None:
            for t in (assessment.get("topicPolicy") or {}).get("topics", []) or []:
                if t.get("action") == "BLOCKED":
                    found.append(f"{where}:topic:{t.get('name')}")
            for f in (assessment.get("contentPolicy") or {}).get("filters", []) or []:
                if f.get("action") == "BLOCKED":
                    found.append(f"{where}:filter:{f.get('type')}")
            for w in (assessment.get("wordPolicy") or {}).get("customWords", []) or []:
                if w.get("action") == "BLOCKED":
                    found.append(f"{where}:word")

        for a in (trace.get("inputAssessment") or {}).values():
            if isinstance(a, Mapping):
                scan("input", a)
        outputs = trace.get("outputAssessments") or {}
        for items in (outputs.values() if isinstance(outputs, Mapping) else []):
            for a in items or []:
                if isinstance(a, Mapping):
                    scan("output", a)
        return ", ".join(dict.fromkeys(found)) or None

    @staticmethod
    def _text_from_message(message: Mapping[str, Any]) -> str:
        content = message.get("content", [])
        if not isinstance(content, Sequence):
            return ""
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, Mapping) and isinstance(block.get("text"), str)
        )
