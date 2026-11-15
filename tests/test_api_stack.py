"""Synthesis tests for the CDK ApiStack (task 18.4). Nothing is deployed."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("aws_cdk")
import aws_cdk as cdk  # noqa: E402
from aws_cdk.assertions import Match, Template  # noqa: E402

from api.handler import ROUTES  # noqa: E402
from infra.stacks.api_stack import ApiStack  # noqa: E402

ORIGIN = "https://main.d111111abcdef8.amplifyapp.com"
RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:111111111111:runtime/guide_runtime-abc123"
POOL_ARN = "arn:aws:cognito-idp:us-east-1:111111111111:userpool/us-east-1_AbCdEf123"


@pytest.fixture(scope="module")
def template() -> Template:
    app = cdk.App()
    stack = ApiStack(
        app,
        "Api",
        user_pool_arn=POOL_ARN,
        agent_runtime_arn=RUNTIME_ARN,
        cors_origin=ORIGIN,
        env=cdk.Environment(account="111111111111", region="us-east-1"),
    )
    return Template.from_stack(stack)


def test_session_store_table(template):
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "alphaforge-guide-sessions",
            "BillingMode": "PAY_PER_REQUEST",
            "KeySchema": [
                {"AttributeName": "owner", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            "TimeToLiveSpecification": {"AttributeName": "ttl", "Enabled": True},
        },
    )


def test_lambda_traced_and_configured(template):
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "Handler": "api.handler.handler",
            "Runtime": "python3.11",
            "TracingConfig": {"Mode": "Active"},
            "Timeout": 29,
            "Environment": {
                "Variables": {
                    "GUIDE_SESSION_TABLE": "alphaforge-guide-sessions",
                    "GUIDE_AGENT_RUNTIME_ARN": RUNTIME_ARN,
                    "GUIDE_CORS_ORIGIN": ORIGIN,
                }
            },
        },
    )


def test_role_is_scoped(template):
    policies = template.find_resources("AWS::IAM::Policy")
    statements = [s for p in policies.values() for s in p["Properties"]["PolicyDocument"]["Statement"]]
    actions = {a for s in statements for a in ([s["Action"]] if isinstance(s["Action"], str) else s["Action"])}
    assert actions == {
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "s3:GetObject",
        "bedrock-agentcore:InvokeAgentRuntime",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords",
    }
    for s in statements:
        resources = [s["Resource"]] if not isinstance(s["Resource"], list) else s["Resource"]
        if "xray:PutTraceSegments" not in s["Action"]:
            assert "*" not in resources
    roles = template.find_resources("AWS::IAM::Role")
    for r in roles.values():
        assert not r["Properties"].get("ManagedPolicyArns")


def test_every_route_method_uses_cognito_and_routes_match(template):
    methods = template.find_resources("AWS::ApiGateway::Method")
    resources = template.find_resources("AWS::ApiGateway::Resource")
    parts = {k: v["Properties"] for k, v in resources.items()}

    def path_of(res_ref: dict | None) -> str:
        segs = []
        while res_ref and "Ref" in res_ref:
            props = parts[res_ref["Ref"]]
            segs.append(props["PathPart"])
            res_ref = props["ParentId"]
        return "/" + "/".join(reversed(segs))

    found = set()
    for m in methods.values():
        p = m["Properties"]
        if p["HttpMethod"] == "OPTIONS":
            assert p["AuthorizationType"] == "NONE"
            assert p["Integration"]["Type"] == "MOCK"
            continue
        assert p["AuthorizationType"] == "COGNITO_USER_POOLS"
        assert p["AuthorizerId"]
        found.add((p["HttpMethod"], path_of(p["ResourceId"])))
    assert found == set(ROUTES)


def test_authorizer_uses_user_pool(template):
    template.has_resource_properties(
        "AWS::ApiGateway::Authorizer",
        {"Type": "COGNITO_USER_POOLS", "ProviderARNs": [POOL_ARN], "IdentitySource": "method.request.header.Authorization"},
    )


def test_cors_is_limited_to_origin(template):
    dumped = json.dumps(template.to_json())
    assert f"'{ORIGIN}'" in dumped
    assert "'*'" not in dumped
    template.has_resource_properties(
        "AWS::ApiGateway::GatewayResponse",
        {"ResponseType": "DEFAULT_4XX", "ResponseParameters": Match.object_like({"gatewayresponse.header.Access-Control-Allow-Origin": f"'{ORIGIN}'"})},
    )


def test_stage_throttling_and_tracing(template):
    template.has_resource_properties(
        "AWS::ApiGateway::Stage",
        {
            "StageName": "prod",
            "TracingEnabled": True,
            "MethodSettings": Match.array_with(
                [Match.object_like({"ThrottlingRateLimit": 10, "ThrottlingBurstLimit": 20, "HttpMethod": "*", "ResourcePath": "/*"})]
            ),
        },
    )


def test_wildcard_origin_rejected():
    with pytest.raises(ValueError):
        ApiStack(cdk.App(), "Bad", user_pool_arn=POOL_ARN, agent_runtime_arn=RUNTIME_ARN, cors_origin="*")


def test_session_api_role_can_read_snapshot_keys_only(template):
    policies = template.find_resources("AWS::IAM::Policy")
    statements = [s for p in policies.values() for s in p["Properties"]["PolicyDocument"]["Statement"]]
    s3 = next(s for s in statements if s["Action"] == "s3:GetObject")
    assert s3["Resource"] == [
        "arn:aws:s3:::alphaforge-guide-data/dataset/snapshots/*",
        "arn:aws:s3:::alphaforge-guide-data/dataset/curated/*",
        "arn:aws:s3:::alphaforge-guide-data/dataset/pointers/current.json",
    ]
