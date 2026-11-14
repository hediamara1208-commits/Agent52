"""Unit tests for the Bedrock Converse wrapper (Requirements 5.7, 5.8, 8.1, 8.2, 8.8, 9.6, 13.5, 13.6)."""
from __future__ import annotations

import pytest
from botocore.exceptions import ClientError

from guide.agents.base import GUIDANCE_ONLY_MESSAGE, BedrockAgent, StageFailure
from guide.config import Config
from guide.trace.recorder import TraceRecorder


class FakeBedrockClient:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _config() -> Config:
    return Config(
        s3_bucket="test-bucket",
        model_id="model-id-from-bedrock-console",
        guardrail_id="guardrail-id",
        guardrail_version="1",
    )


def _response(stop_reason="end_turn", content=None):
    return {
        "stopReason": stop_reason,
        "output": {"message": {"role": "assistant", "content": content or [{"text": "Complete."}]}},
    }


def test_tool_use_loop_guards_every_call_and_drops_reasoning_content():
    client = FakeBedrockClient(
        [
            _response(
                "tool_use",
                [
                    {"reasoningContent": {"reasoningText": {"text": "hidden"}}},
                    {"toolUse": {"toolUseId": "call-1", "name": "metric", "input": {"ticker": "TSLA"}}},
                ],
            ),
            _response(
                content=[
                    {"reasoningContent": {"reasoningText": {"text": "also hidden"}}},
                    {"text": "Exhibit 7 supports the narrative."},
                ]
            ),
        ]
    )
    seen_tool_uses = []

    def run_tool(tool_use):
        seen_tool_uses.append(tool_use)
        return {"content": [{"json": {"value": 0.12}}], "exhibit_number": 7}

    trace = TraceRecorder(emit_spans=False)
    agent = BedrockAgent("prosecutor", _config(), client=client, tool_runner=run_tool)
    output = agent.run(
        "system instruction",
        [{"role": "user", "content": [{"text": "Evaluate TSLA."}]}],
        [{"toolSpec": {"name": "metric", "inputSchema": {"json": {"type": "object"}}}}],
        trace,
    )

    assert output.text == "Exhibit 7 supports the narrative."
    assert all("reasoningContent" not in block for block in output.content)
    assert seen_tool_uses == [{"toolUseId": "call-1", "name": "metric", "input": {"ticker": "TSLA"}}]
    assert len(client.calls) == 2
    for call in client.calls:
        assert call["guardrailConfig"] == {
            "guardrailIdentifier": "guardrail-id",
            "guardrailVersion": "1",
            "trace": "disabled",
        }
    second_call_messages = client.calls[1]["messages"]
    assert all("reasoningContent" not in block for block in second_call_messages[1]["content"])
    assert second_call_messages[2]["content"][0]["toolResult"]["toolUseId"] == "call-1"
    assert [event.kind for event in trace.events] == ["tool_call", "agent_call"]
    assert trace.events[0].exhibit_number == 7


def test_guardrail_intervention_is_traced_and_returns_guidance_message():
    client = FakeBedrockClient([_response("guardrail_intervened", [{"text": "blocked"}])])
    trace = TraceRecorder(emit_spans=False)
    agent = BedrockAgent("clerk", _config(), client=client)

    output = agent.run(
        "system instruction",
        [{"role": "user", "content": [{"text": "Please place an order for TSLA."}]}],
        None,
        trace,
    )

    assert output.blocked is True
    assert output.challenge_rule == "Guidance_Only_Rule"
    assert output.text == GUIDANCE_ONLY_MESSAGE
    assert trace.events[0].kind == "guardrail_block"
    assert trace.events[0].name == "clerk"
    assert trace.events[0].summary["rule"] == "Guidance_Only_Rule"


def test_throttling_retries_three_times_with_exponential_backoff_and_jitter():
    throttled = ClientError({"Error": {"Code": "ThrottlingException"}}, "Converse")
    client = FakeBedrockClient([throttled, throttled, throttled, _response()])
    delays = []
    agent = BedrockAgent(
        "judge",
        _config(),
        client=client,
        sleep=delays.append,
        random_source=lambda: 0.0,
    )

    output = agent.run("system instruction", [], None, TraceRecorder(emit_spans=False))

    assert output.text == "Complete."
    assert len(client.calls) == 4
    assert delays == [0.25, 0.5, 1.0]


def test_exhausted_throttling_raises_stage_failure_after_three_retries():
    throttled = ClientError({"Error": {"Code": "ThrottlingException"}}, "Converse")
    client = FakeBedrockClient([throttled, throttled, throttled, throttled])
    agent = BedrockAgent(
        "defense",
        _config(),
        client=client,
        stage="defense-arguments",
        sleep=lambda _: None,
        random_source=lambda: 0.0,
    )

    with pytest.raises(StageFailure, match="defense-arguments: Bedrock Converse throttled after 3 retries"):
        agent.run("system instruction", [], None, TraceRecorder(emit_spans=False))

    assert len(client.calls) == 4


def test_model_calls_cannot_be_created_without_guardrail_configuration():
    unsafe_config = Config(s3_bucket="test-bucket", model_id="model-id", guardrail_id="")

    with pytest.raises(ValueError, match="guardrail_id is required"):
        BedrockAgent("judge", unsafe_config, client=FakeBedrockClient([]))
