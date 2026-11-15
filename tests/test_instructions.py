"""Instruction_Loader and Instruction_Hash tests (Req. 9.8, 21.4-21.8)."""
from __future__ import annotations

import hashlib

import pytest

from guide.agents.base import BedrockAgent
from guide.agents.instructions import InstructionError, load_all, load_system_prompt
from guide.config import Config
from guide.trace.recorder import TraceRecorder

GUIDANCE = "Never place, route, prefill, or trigger an order."


def _write(root, agent="judge", skills=("citing_exhibits", "guidance_only"), newline="\n"):
    (root / "instructions").mkdir(parents=True, exist_ok=True)
    (root / "skills").mkdir(parents=True, exist_ok=True)
    body = "# Role\nYou are the judge.\n# Included skills\n" + "".join(f"- {s}\n" for s in skills)
    (root / "instructions" / f"{agent}.md").write_bytes(body.replace("\n", newline).encode())
    (root / "skills" / "citing_exhibits.md").write_text("Cite every Exhibit.\n")
    (root / "skills" / "guidance_only.md").write_text(GUIDANCE + "\n")


def test_composes_in_listed_order_and_hashes_lf_text(tmp_path):
    _write(tmp_path)
    sp = load_system_prompt("judge", tmp_path)
    assert sp.skills == ("citing_exhibits", "guidance_only")
    assert sp.text.index("# Skill: citing_exhibits") < sp.text.index("# Skill: guidance_only")
    assert GUIDANCE in sp.text
    assert sp.instruction_hash == hashlib.sha256(sp.text.encode("utf-8")).hexdigest()


def test_crlf_files_give_same_hash(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _write(a)
    _write(b, newline="\r\n")
    assert load_system_prompt("judge", a).instruction_hash == load_system_prompt("judge", b).instruction_hash


def test_hash_changes_when_skill_changes(tmp_path):
    _write(tmp_path)
    before = load_system_prompt("judge", tmp_path).instruction_hash
    (tmp_path / "skills" / "citing_exhibits.md").write_text("Cite every Exhibit number.\n")
    assert load_system_prompt("judge", tmp_path).instruction_hash != before


def test_missing_instruction_file_names_agent_and_file(tmp_path):
    _write(tmp_path)
    with pytest.raises(InstructionError) as err:
        load_all(["judge", "advocate"], tmp_path)
    assert err.value.agent == "advocate" and "advocate.md" in err.value.missing_file


def test_missing_skill_file(tmp_path):
    _write(tmp_path, skills=("guidance_only", "data_limits"))
    with pytest.raises(InstructionError) as err:
        load_system_prompt("judge", tmp_path)
    assert err.value.agent == "judge" and "data_limits.md" in err.value.missing_file


def test_guidance_only_must_be_listed(tmp_path):
    _write(tmp_path, skills=("citing_exhibits",))
    with pytest.raises(InstructionError):
        load_system_prompt("judge", tmp_path)


def test_hash_reaches_converse_system_block_and_trace(tmp_path):
    _write(tmp_path)
    sp = load_system_prompt("judge", tmp_path)

    class Client:
        def converse(self, **kwargs):
            self.kwargs = kwargs
            return {"stopReason": "end_turn", "output": {"message": {"role": "assistant", "content": [{"text": "ok"}]}}}

    client = Client()
    cfg = Config(s3_bucket="b", model_id="m", guardrail_id="g", guardrail_version="1")
    trace = TraceRecorder(emit_spans=False)
    BedrockAgent("judge", cfg, client=client).run(sp, [], None, trace)
    assert client.kwargs["system"] == [{"text": sp.text}]
    (event,) = trace.events
    assert event.summary["instruction_hash"] == sp.instruction_hash
