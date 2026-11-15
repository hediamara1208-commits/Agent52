"""Synthesis test for infra/app.py (task 18.7). Offline; deploys nothing."""
from __future__ import annotations

import pytest

pytest.importorskip("aws_cdk")

from infra.app import build_app  # noqa: E402

STACKS = ["GuideDataStack", "GuideAuthStack", "GuideRuntimeStack", "GuideApiStack", "GuideFrontendStack", "GuideOpsStack"]


def test_all_six_stacks_exist_and_synthesize():
    assembly = build_app().synth()
    names = {s.stack_name for s in assembly.stacks}
    assert set(STACKS) <= names
    api = assembly.get_stack_by_name("GuideApiStack").template
    env = next(
        r["Properties"]["Environment"]["Variables"]
        for r in api["Resources"].values()
        if r["Type"] == "AWS::Lambda::Function" and "GUIDE_S3_BUCKET" in str(r["Properties"].get("Environment"))
    )
    assert env["GUIDE_S3_PREFIX"] == "dataset"
