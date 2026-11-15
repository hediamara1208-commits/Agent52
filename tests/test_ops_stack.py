"""Synthesis tests for the CDK OpsStack, Tier 2 lean (task 18.6). Nothing is deployed."""
from __future__ import annotations

import pytest

pytest.importorskip("aws_cdk")
import aws_cdk as cdk  # noqa: E402
from aws_cdk.assertions import Match, Template  # noqa: E402

from infra.stacks.ops_stack import (  # noqa: E402
    AGENT_RUNTIME_LOG_GROUP,
    BEDROCK_INVOCATION_LOG_GROUP,
    SESSION_API_LOG_GROUP,
    OpsStack,
)


@pytest.fixture(scope="module")
def template() -> Template:
    stack = OpsStack(cdk.App(), "Ops", env=cdk.Environment(account="111111111111", region="us-east-1"))
    return Template.from_stack(stack)


def test_log_groups_have_30_day_retention(template):
    groups = template.find_resources("AWS::Logs::LogGroup")
    by_name = {g["Properties"]["LogGroupName"]: g["Properties"] for g in groups.values()}
    assert set(by_name) == {SESSION_API_LOG_GROUP, AGENT_RUNTIME_LOG_GROUP, BEDROCK_INVOCATION_LOG_GROUP}
    assert all(p["RetentionInDays"] == 30 for p in by_name.values())


def test_invocation_logging_custom_resource(template):
    import json

    resources = template.find_resources("Custom::AWS")
    assert len(resources) == 1
    props = next(iter(resources.values()))["Properties"]
    assert "putModelInvocationLoggingConfiguration" in json.dumps(props["Create"])
    assert "deleteModelInvocationLoggingConfiguration" in json.dumps(props["Delete"])


def test_invocation_role_is_scoped(template):
    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "RoleName": "guide-bedrock-invocation-logging-role",
            "AssumeRolePolicyDocument": Match.object_like(
                {"Statement": [Match.object_like({"Principal": {"Service": "bedrock.amazonaws.com"}})]}
            ),
        },
    )
    policies = template.find_resources("AWS::IAM::Policy")
    for p in policies.values():
        for s in p["Properties"]["PolicyDocument"]["Statement"]:
            actions = [s["Action"]] if isinstance(s["Action"], str) else s["Action"]
            if any(a.startswith("logs:") for a in actions):
                assert set(actions) == {"logs:CreateLogStream", "logs:PutLogEvents"}
                resources = s["Resource"] if isinstance(s["Resource"], list) else [s["Resource"]]
                assert all(r != "*" for r in resources)


def test_lean_scope_has_no_dashboard_alarm_topic_or_budget(template):
    for rtype in ("AWS::CloudWatch::Dashboard", "AWS::CloudWatch::Alarm", "AWS::SNS::Topic", "AWS::Budgets::Budget"):
        template.resource_count_is(rtype, 0)
