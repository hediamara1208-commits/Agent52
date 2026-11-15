"""Synthesis tests for the CDK RuntimeStack (task 18.3). Nothing is deployed."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("aws_cdk")
import aws_cdk as cdk  # noqa: E402
from aws_cdk.assertions import Match, Template  # noqa: E402

from infra.stacks.runtime_stack import RuntimeStack  # noqa: E402

ENV = cdk.Environment(account="111111111111", region="us-east-1")


def _template(**kwargs) -> Template:
    app = cdk.App()
    return Template.from_stack(RuntimeStack(app, "Runtime", env=ENV, **kwargs))


@pytest.fixture(scope="module")
def template() -> Template:
    return _template()


def test_runtime_uses_image_asset_and_role(template):
    template.resource_count_is("AWS::BedrockAgentCore::Runtime", 1)
    template.has_resource_properties(
        "AWS::BedrockAgentCore::Runtime",
        {
            "AgentRuntimeName": "guide_runtime",
            "AgentRuntimeArtifact": {"ContainerConfiguration": {"ContainerUri": Match.any_value()}},
            "RoleArn": Match.any_value(),
            "EnvironmentVariables": Match.object_like({"GUIDE_SESSION_TABLE": "alphaforge-guide-sessions"}),
        },
    )
    runtime = next(iter(template.find_resources("AWS::BedrockAgentCore::Runtime").values()))
    assert "AuthorizerConfiguration" not in runtime["Properties"]


def test_memory_exists(template):
    template.has_resource_properties("AWS::BedrockAgentCore::Memory", {"Name": "guide_memory", "EventExpiryDuration": 90})


def test_application_role_is_scoped_to_named_resources(template):
    policies = template.find_resources("AWS::IAM::Policy")
    statements = [s for p in policies.values() for s in p["Properties"]["PolicyDocument"]["Statement"]]
    text = json.dumps(statements)
    assert "arn:aws:dynamodb:us-east-1:111111111111:table/alphaforge-guide-sessions" in text
    assert "AgentCoreMemory" in text and "BedrockGuardrail" in text
    actions = {a for s in statements for a in ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])}
    assert not any(a.startswith("s3:Delete") or a == "*" for a in actions)
    assert not any(a.startswith(("dynamodb:Delete", "dynamodb:Scan")) for a in actions)
    template.has_resource_properties(
        "AWS::IAM::Role",
        {"AssumeRolePolicyDocument": Match.object_like({"Statement": Match.array_with([Match.object_like({"Principal": {"Service": "bedrock-agentcore.amazonaws.com"}})])})},
    )


def test_identity_adds_jwt_authorizer():
    t = _template(enable_identity=True, user_pool_id="us-east-1_abc123", user_pool_client_id="client123")
    t.has_resource_properties(
        "AWS::BedrockAgentCore::Runtime",
        {
            "AuthorizerConfiguration": {
                "CustomJWTAuthorizer": {
                    "DiscoveryUrl": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_abc123/.well-known/openid-configuration",
                    "AllowedClients": ["client123"],
                }
            }
        },
    )


def test_identity_requires_pool_ids():
    with pytest.raises(ValueError):
        _template(enable_identity=True)


def test_outputs(template):
    outputs = template.to_json()["Outputs"]
    assert {"AgentRuntimeArn", "AgentCoreMemoryId", "ApplicationRoleArn"} <= set(outputs)
