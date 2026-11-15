"""Advocate output validation and call wiring (Requirements 4.1, 4.2, 4.8, 4.9)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from guide.agents.advocate import advocate_system_prompt, parse_advocate_output, run_advocate
from guide.agents.base import StageFailure
from guide.config import Config
from guide.trace.recorder import TraceRecorder

ROOT = Path(__file__).resolve().parent.parent


def _opt(asset="TSLA", weight=0.1, rationale="A smaller size lowers the drawdown.", exhibits=(1,)):
    return {"asset": asset, "weight": weight, "rationale": rationale, "exhibits": list(exhibits)}


def _out(*options, goal="Keep growth exposure within the contract."):
    return json.dumps({"goal": goal, "options": list(options)})


def _parse(text, scope="size_only", **kw):
    return parse_advocate_output(text, request_ticker="TSLA", request_weight=0.3, scope=scope, **kw)


def test_valid_size_only_output():
    result = _parse(_out(_opt(weight=0.1), _opt(weight=0.2)))
    assert [o.weight for o in result.options] == [0.1, 0.2]


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        _out(),
        _out(_opt(weight=0.05), _opt(weight=0.1), _opt(weight=0.15), _opt(weight=0.2)),
        _out(_opt(weight=0.3)),  # not smaller
        _out(_opt(asset="XEQT.TO")),  # other asset under size_only
        _out(_opt(rationale="You should buy less TSLA.")),
        _out(_opt(exhibits=())),
        _out(_opt(), goal="Sell down the position."),
    ],
)
def test_invalid_output_fails_stage(text):
    with pytest.raises(StageFailure):
        _parse(text)


def test_universe_scope_allows_other_asset_but_needs_smaller_size():
    universe = {"TSLA", "XEQT.TO"}
    assert _parse(_out(_opt(), _opt(asset="XEQT.TO", weight=0.3)), "universe", universe=universe)
    with pytest.raises(StageFailure):
        _parse(_out(_opt(asset="XEQT.TO", weight=0.3)), "universe", universe=universe)
    with pytest.raises(StageFailure):
        _parse(_out(_opt(), _opt(asset="ZZZ")), "universe", universe=universe)


class _Client:
    def __init__(self, text):
        self.text, self.calls = text, []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {"stopReason": "end_turn",
                "output": {"message": {"role": "assistant", "content": [{"text": self.text}]}}}


def test_run_advocate_uses_agent_model_guardrail_and_scope():
    config = Config(s3_bucket="b", model_id="base", model_ids={"advocate": "adv-model"},
                    guardrail_id="g", guardrail_version="1", instruction_dir=str(ROOT / "guide/agents"))
    client = _Client(_out(_opt()))
    result = run_advocate(
        config, request_text="30% in TSLA", request_ticker="TSLA", request_weight=0.3,
        contract={}, risk_panel={}, tools=None, trace=TraceRecorder(emit_spans=False), client=client,
    )
    call = client.calls[0]
    assert len(result.options) == 1 and len(client.calls) == 1
    assert call["modelId"] == "adv-model" and call["guardrailConfig"]["guardrailIdentifier"] == "g"
    assert '"advocate_scope": "size_only"' in call["messages"][0]["content"][0]["text"]
    assert advocate_system_prompt(config).text in call["system"][0]["text"]


def test_advocate_message_carries_exhibit_values_and_rule_results():
    from guide.agents.advocate import build_messages
    import json as _json
    msg = build_messages("I want 30% in tesla.", "TSLA", 0.3, {"per_asset_cap": 0.1},
                         {"volatility": {"exhibit": 7, "value": 0.2}}, "size_only",
                         [{"rule": "per_asset_cap", "status": "fail", "observed": 0.3, "limit": 0.1, "exhibits": []}])
    payload = _json.loads(msg[0]["content"][0]["text"])
    assert payload["risk_panel"]["volatility"] == {"exhibit": 7, "value": 0.2}
    assert payload["request_hard_rule_results"][0]["status"] == "fail"


def test_compliant_request_may_be_proposed_as_is():
    """Robert asks for 2% SPY and it passes every Hard_Rule: the request itself is a fair Option."""
    spy = lambda w: _opt(asset="SPY", weight=w, rationale="2% SPY keeps volatility within the limit.")
    text = json.dumps({"goal": "Add US diversification within the contract.", "options": [spy(0.02)]})
    out = parse_advocate_output(text, request_ticker="SPY", request_weight=0.02, scope="size_only",
                                request_complies=True)
    assert [(o.asset, o.weight) for o in out.options] == [("SPY", 0.02)]
    with pytest.raises(StageFailure):  # not compliant: a smaller size is still required
        parse_advocate_output(text, request_ticker="SPY", request_weight=0.02, scope="size_only")
    with pytest.raises(StageFailure):  # never above the request, never another asset under size_only
        parse_advocate_output(json.dumps({"goal": "g", "options": [spy(0.03)]}), request_ticker="SPY",
                              request_weight=0.02, scope="size_only", request_complies=True)


def test_request_complies_reads_hard_rule_results():
    from guide.agents.advocate import request_complies
    assert request_complies([{"rule": "max_volatility", "status": "pass"}, {"rule": "per_asset_cap", "status": "pass"}])
    assert not request_complies([{"rule": "max_volatility", "status": "pass"}, {"rule": "x", "status": "unverified"}])
    assert not request_complies([{"rule": "per_asset_cap", "status": "fail"}])
    assert not request_complies([]) and not request_complies(None)
