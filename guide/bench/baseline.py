"""Baseline_Agent (Req. 34.5): one Converse call, no Toolkit, no Exhibits, no other agent.

Same model, same Guardrail (``guardrailConfig`` on the call), same Investor_Contract as the
Guide_System. Throttling is retried 3 times with exponential backoff. Every number in its
output is unverifiable because no Exhibit exists.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import boto3
from botocore.config import Config as BotoConfig

from guide.config import Config

BASELINE_SYSTEM_PROMPT = "You are an investment assistant"
VERDICTS = ("accept_with_conditions", "accept", "reject")
_VERDICT_RE = re.compile(r"\b(accept_with_conditions|accept with conditions|accept|reject)\b", re.I)
_FORMAT_LINE = (
    "Answer with a short assessment. End with one line 'VERDICT: accept', "
    "'VERDICT: accept_with_conditions' or 'VERDICT: reject'."
)


@dataclass(frozen=True)
class BaselineResult:
    text: str
    verdict: str  # accept | accept_with_conditions | reject | unclear
    latency_seconds: float
    tokens: int | None
    calls: int = 1


def build_user_message(contract: Mapping[str, Any], request_text: str) -> str:
    return (f"Investor_Contract (JSON):\n{json.dumps(contract, sort_keys=True, default=str)}\n\n"
            f"Request: {request_text}\n\n{_FORMAT_LINE}")


def parse_verdict(text: str) -> str:
    """Last verdict word in the text (the format line asks for it last); ``unclear`` if none."""
    found = _VERDICT_RE.findall(text)
    if not found:
        return "unclear"
    return found[-1].lower().replace(" ", "_")


def _is_throttling(error: Exception) -> bool:
    response = getattr(error, "response", None)
    return isinstance(response, Mapping) and response.get("Error", {}).get("Code") == "ThrottlingException"


class BaselineAgent:
    def __init__(self, config: Config, *, client: Any | None = None, max_tokens: int = 1024,
                 max_throttling_retries: int = 3, base_backoff_seconds: float = 0.25,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if not config.model_id.strip():
            raise ValueError("model_id is required")
        if not config.guardrail_id.strip() or not config.guardrail_version.strip():
            raise ValueError("the Guardrail is required on every Converse call")
        self.config = config
        self.max_tokens = max_tokens
        self.max_retries = max_throttling_retries
        self.backoff = base_backoff_seconds
        self._sleep = sleep
        self._clock = clock
        self.client = client or boto3.client(
            "bedrock-runtime", region_name=config.aws_region,
            config=BotoConfig(retries={"total_max_attempts": 1, "mode": "standard"}))

    def run(self, contract: Mapping[str, Any], request_text: str) -> BaselineResult:
        request = {
            "modelId": self.config.model_id,
            "system": [{"text": BASELINE_SYSTEM_PROMPT}],
            "messages": [{"role": "user", "content": [{"text": build_user_message(contract, request_text)}]}],
            "inferenceConfig": {"maxTokens": self.max_tokens},
            "guardrailConfig": {"guardrailIdentifier": self.config.guardrail_id,
                                "guardrailVersion": self.config.guardrail_version, "trace": "disabled"},
        }  # no toolConfig: the Baseline_Agent has no Toolkit
        start = self._clock()
        for retry in range(self.max_retries + 1):
            try:
                response = self.client.converse(**request)
                break
            except Exception as error:
                if not _is_throttling(error) or retry >= self.max_retries:
                    raise
                self._sleep(self.backoff * 2**retry)
        latency = self._clock() - start
        blocks = response.get("output", {}).get("message", {}).get("content", [])
        text = "\n".join(b["text"] for b in blocks if isinstance(b, Mapping) and isinstance(b.get("text"), str))
        if response.get("stopReason") == "guardrail_intervened":
            return BaselineResult(text, "unclear", latency, _tokens(response))  # blocked: no verdict given
        return BaselineResult(text, parse_verdict(text), latency, _tokens(response))


def _tokens(response: Mapping[str, Any]) -> int | None:
    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        return None
    total = usage.get("totalTokens")
    if isinstance(total, int):
        return total
    parts = [usage.get("inputTokens"), usage.get("outputTokens")]
    return sum(p for p in parts if isinstance(p, int)) if all(isinstance(p, int) for p in parts) else None
