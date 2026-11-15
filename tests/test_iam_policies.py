"""Least-privilege rules for infra/iam.py (Req. 8.9 to 8.12, 25.1). Offline; deploys nothing."""
import json

import pytest

from infra import iam

T = iam.IamTargets(
    account="123456789012",
    region="us-east-1",
    bucket="alphaforge-guide-data",
    prefix="dataset",
    model_id="us.anthropic.claude-sonnet-5-5",
    guardrail_id="3981l0ehd4uu",
    session_table="alphaforge-guide-sessions",
    glue_database="alphaforge_guide",
    athena_workgroup="alphaforge-guide",
    results_bucket="alphaforge-guide-athena-results",
    memory_id="mem-1",
)
RUNTIME = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/rt-1"

ROLES = {
    "application": iam.application_role_statements(T),
    "session_api": iam.session_api_lambda_statements(T, RUNTIME),
    "seed": iam.seed_import_job_statements(T),
    "athena": iam.athena_query_statements(T),
}


@pytest.mark.parametrize("role", ROLES)
def test_role_has_no_rule_violations(role):
    assert iam.violations(ROLES[role]) == []


@pytest.mark.parametrize("role", ROLES)
def test_no_delete_or_brokerage_actions(role):
    for a in iam.all_actions(ROLES[role]):
        assert not a.startswith("s3:Delete")
        assert a.split(":")[0] not in {"brokerage", "bank", "banking"}


def test_application_role_is_read_only_on_snapshots():
    s3 = {a for a in iam.all_actions(ROLES["application"]) if a.startswith("s3:")}
    assert s3 == {"s3:GetObject", "s3:GetObjectVersion"}
    keys = next(s for s in ROLES["application"] if s["Sid"] == "SnapshotRead")["Resource"]
    assert keys == [
        "arn:aws:s3:::alphaforge-guide-data/dataset/snapshots/*",
        "arn:aws:s3:::alphaforge-guide-data/dataset/curated/*",
        "arn:aws:s3:::alphaforge-guide-data/dataset/pointers/current.json",
    ]


def test_application_role_scopes_bedrock_and_memory():
    by_sid = {s["Sid"]: s for s in ROLES["application"]}
    assert by_sid["BedrockGuardrail"]["Resource"] == [
        "arn:aws:bedrock:us-east-1:123456789012:guardrail/3981l0ehd4uu"
    ]
    assert "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-5-5" in by_sid["BedrockInvoke"]["Resource"]
    assert by_sid["AgentCoreMemory"]["Resource"] == ["arn:aws:bedrock-agentcore:us-east-1:123456789012:memory/mem-1"]
    assert by_sid["MetricsWrite"]["Condition"] == {"StringEquals": {"cloudwatch:namespace": "AlphaForgeGuide"}}


def test_memory_statement_omitted_until_memory_exists():
    from dataclasses import replace

    sids = {s["Sid"] for s in iam.application_role_statements(replace(T, memory_id=""))}
    assert "AgentCoreMemory" not in sids


def test_seed_role_can_write_snapshot_keys_and_register_partitions():
    by_sid = {s["Sid"]: s for s in ROLES["seed"]}
    assert "s3:PutObject" in by_sid["SnapshotReadWrite"]["Action"]
    assert set(by_sid["GluePartitions"]["Action"]) == {"glue:GetTable", "glue:BatchCreatePartition"}
    assert len([r for r in by_sid["GluePartitions"]["Resource"] if "/alphaforge_guide/" in r]) == 5
    assert "AthenaWorkgroup" in by_sid


def test_policy_document_is_json_serializable():
    json.dumps(iam.policy_document(ROLES["seed"]))


def test_violations_detects_bad_policies():
    bad = [
        {"Sid": "A", "Effect": "Allow", "Action": ["s3:DeleteObject"], "Resource": ["arn:aws:s3:::b/k"]},
        {"Sid": "B", "Effect": "Allow", "Action": ["s3:*"], "Resource": ["*"]},
    ]
    assert len(iam.violations(bad)) >= 3


def test_guardrail_stack_synthesizes_with_expected_topics():
    cdk = pytest.importorskip("aws_cdk")
    from aws_cdk.assertions import Template

    from infra.stacks.guardrail_stack import GuardrailStack

    tpl = Template.from_stack(GuardrailStack(cdk.App(), "G"))
    res = tpl.find_resources("AWS::Bedrock::Guardrail")
    props = next(iter(res.values()))["Properties"]
    topics = {t["Name"]: t for t in props["TopicPolicyConfig"]["TopicsConfig"]}
    assert set(topics) == {"RealTransactions", "ReturnPredictions"}
    assert all(t["OutputEnabled"] and not t["InputEnabled"] for t in topics.values())
    assert props["ContentPolicyConfig"]["FiltersConfig"][0]["InputStrength"] == "HIGH"
