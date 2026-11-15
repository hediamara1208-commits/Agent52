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
    agent = BedrockAgent("investigator", _config(), client=client, tool_runner=run_tool)
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
            "trace": "enabled",
        }
    second_call_messages = client.calls[1]["messages"]
    assert all("reasoningContent" not in block for block in second_call_messages[1]["content"])
    assert second_call_messages[2]["content"][0]["toolResult"]["toolUseId"] == "call-1"
    assert [event.kind for event in trace.events] == ["tool_call", "agent_call"]
    assert trace.events[0].exhibit_number == 7


def test_guardrail_intervention_is_traced_and_returns_guidance_message():
    client = FakeBedrockClient([_response("guardrail_intervened", [{"text": "blocked"}])])
    trace = TraceRecorder(emit_spans=False)
    agent = BedrockAgent("judge", _config(), client=client)

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
    assert trace.events[0].name == "judge"
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
        "advocate",
        _config(),
        client=client,
        stage="advocate-options",
        sleep=lambda _: None,
        random_source=lambda: 0.0,
    )

    with pytest.raises(StageFailure, match="advocate-options: Bedrock Converse throttled after 3 retries"):
        agent.run("system instruction", [], None, TraceRecorder(emit_spans=False))

    assert len(client.calls) == 4


def test_model_calls_cannot_be_created_without_guardrail_configuration():
    unsafe_config = Config(s3_bucket="test-bucket", model_id="model-id", guardrail_id="")

    with pytest.raises(ValueError, match="guardrail_id is required"):
        BedrockAgent("judge", unsafe_config, client=FakeBedrockClient([]))


def test_guard_content_tags_only_the_user_text_and_block_reason_is_named():
    from guide.agents.base import BedrockAgent
    from guide.config import Config
    cfg = Config(s3_bucket="b", model_id="m", guardrail_id="g", guardrail_version="1")
    seen = {}

    class Client:
        def converse(self, **kw):
            seen.update(kw)
            return {"stopReason": "guardrail_intervened",
                    "output": {"message": {"role": "assistant", "content": [{"text": "x"}]}},
                    "trace": {"guardrail": {"outputAssessments": {"0": [{"topicPolicy": {"topics": [
                        {"name": "ReturnPredictions", "type": "DENY", "action": "BLOCKED"}]}}]}}}}

    from guide.trace.recorder import TraceRecorder
    trace = TraceRecorder(emit_spans=False)
    agent = BedrockAgent("judge", cfg, client=Client(), guard_text="30% in TSLA")
    out = agent.run("sys", [{"role": "user", "content": [{"text": "{\"a\": 1}"}]}], None, trace)
    assert out.blocked
    blocks = seen["messages"][0]["content"]
    blocks = [b for b in blocks if "cachePoint" not in b]
    assert blocks[-1] == {"guardContent": {"text": {"text": "30% in TSLA"}}}
    assert seen["guardrailConfig"]["trace"] == "enabled"
    ev = [e for e in trace.to_list() if e["kind"] == "guardrail_block"][0]
    assert ev["summary"]["rule"] == "output:topic:ReturnPredictions"


def test_usage_is_summed_over_tool_rounds_and_recorded_on_the_agent_call():
    from guide.agents import base

    class Client:
        def __init__(self):
            self.calls = []

        def converse(self, **kw):
            self.calls.append(kw)
            if len(self.calls) == 1:
                return {"stopReason": "tool_use",
                        "output": {"message": {"role": "assistant", "content": [
                            {"toolUse": {"toolUseId": "t1", "name": "x", "input": {}}}]}},
                        "usage": {"inputTokens": 1000, "outputTokens": 50, "cacheWriteInputTokens": 900, "totalTokens": 1950}}
            return {"stopReason": "end_turn",
                    "output": {"message": {"role": "assistant", "content": [{"text": "done"}]}},
                    "usage": {"inputTokens": 120, "outputTokens": 40, "cacheReadInputTokens": 900, "totalTokens": 1060}}

    base._CACHE_SUPPORTED.clear()
    client = Client()
    cfg = Config(s3_bucket="b", model_id="m-usage", guardrail_id="g", guardrail_version="1")
    trace = TraceRecorder(emit_spans=False)
    BedrockAgent("advocate", cfg, client=client, tool_runner=lambda use: {"ok": 1}).run(
        "system", [{"role": "user", "content": [{"text": "hi"}]}], {"tools": [{"toolSpec": {"name": "x"}}]}, trace)
    first = client.calls[0]
    assert first["system"][-1] == {"cachePoint": {"type": "default"}}
    assert first["toolConfig"]["tools"][-1] == {"cachePoint": {"type": "default"}}
    assert first["messages"][-1]["content"][-1] == {"cachePoint": {"type": "default"}}
    ev = [e for e in trace.to_list() if e["kind"] == "agent_call"][-1]
    assert ev["summary"]["usage"] == {"inputTokens": 1120, "outputTokens": 90, "cacheWriteInputTokens": 900,
                                      "cacheReadInputTokens": 900, "totalTokens": 3010, "calls": 2}


def test_a_cache_rejection_is_retried_without_cache_points():
    from botocore.exceptions import ClientError
    from guide.agents import base

    class Client:
        def __init__(self):
            self.calls = []

        def converse(self, **kw):
            self.calls.append(kw)
            if any("cachePoint" in b for b in kw["system"]):
                raise ClientError({"Error": {"Code": "ValidationException",
                                             "Message": "The model does not support prompt caching"}}, "Converse")
            return {"stopReason": "end_turn",
                    "output": {"message": {"role": "assistant", "content": [{"text": "ok"}]}}}

    base._CACHE_SUPPORTED.clear()
    client = Client()
    cfg = Config(s3_bucket="b", model_id="m-nocache", guardrail_id="g", guardrail_version="1")
    out = BedrockAgent("judge", cfg, client=client).run("s", [{"role": "user", "content": [{"text": "q"}]}], None,
                                                        TraceRecorder(emit_spans=False))
    assert out.text == "ok"
    assert len(client.calls) == 2 and client.calls[1]["system"] == [{"text": "s"}]
    assert base._CACHE_SUPPORTED["m-nocache"] is False
