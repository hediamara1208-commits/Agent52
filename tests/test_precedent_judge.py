"""Req. 31.2, 31.4: differing-field check and the seed script (no AWS, no model call)."""
from __future__ import annotations

import importlib.util
from dataclasses import replace
from pathlib import Path

from guide.agents.judge import JudgeResult, build_messages, check_precedent_fields, differing_fields
from guide.tribunal.precedents import InMemoryPrecedentStore
from tests.test_orchestrator import Fakes, _request, _run, source  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = {"per_asset_cap": 0.05, "speculative_limit": 0.05, "soft_preferences": []}


def test_differing_fields_and_message_payload():
    other = {"contract": {"per_asset_cap": 0.15, "speculative_limit": 0.05, "soft_preferences": []}}
    assert differing_fields(CONTRACT, other) == ["per_asset_cap"]
    assert differing_fields(CONTRACT, None) == []
    msg = build_messages(hard_rule_results=[], options=[], investigator_findings=[], contract=CONTRACT,
                         verdict={}, precedent=other)[0]["content"][0]["text"]
    assert '"precedent_differing_contract_fields": ["per_asset_cap"]' in msg


def test_named_field_must_exist():
    kept, unknown = check_precedent_fields(["per_asset_cap", "made_up_field", "per_asset_cap"], CONTRACT)
    assert kept == ["per_asset_cap"] and unknown == ["made_up_field"]


def test_orchestrator_records_existing_fields_and_traces_unknown(source):  # noqa: F811
    store = InMemoryPrecedentStore()
    _run(Fakes(), replace(_request(), profile_id="robert", session_id="s1"), source=source, precedents=store)

    def judge(**kw):
        return JudgeResult(narrative="Options weighed against stated preferences.",
                           precedent_fields=["per_asset_cap"], unknown_precedent_fields=["bogus"])

    view, _ = _run(Fakes(judge=judge), replace(_request("amira"), profile_id="amira", session_id="s2"),
                   source=source, precedents=store)
    assert view.ruling["precedent"]["session_id"] == "s1"
    assert view.ruling["precedent"]["differing_fields"] == ["per_asset_cap"]
    assert any(e["name"] == "precedent_field" for e in view.trace if e["kind"] == "judge_check")


def test_seed_script_runs_every_case_without_aws():
    spec = importlib.util.spec_from_file_location("seed_precedents", ROOT / "scripts" / "seed_precedents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    seen = []

    class V:
        status = "completed"

    def fake_run(request, **kw):
        seen.append((request.profile_id, request.ticker, kw["precedents"]))
        return V()

    store = InMemoryPrecedentStore()
    done = mod.seed(store, run=fake_run)
    assert len(done) == 5 and len(seen) == 5
    assert {s[0] for s in seen} == {"robert", "amira", "mateo", "canadian_heavy"}
    assert all(s[2] is store for s in seen)
