"""Synthesis tests for the CDK AuthStack (task 18.2). Nothing is deployed."""
from __future__ import annotations

import pytest

pytest.importorskip("aws_cdk")
import aws_cdk as cdk  # noqa: E402
from aws_cdk.assertions import Match, Template  # noqa: E402

from infra.stacks.auth_stack import AuthStack  # noqa: E402


@pytest.fixture(scope="module")
def template() -> Template:
    app = cdk.App()
    stack = AuthStack(app, "Auth", env=cdk.Environment(account="111111111111", region="us-east-1"))
    return Template.from_stack(stack)


def test_user_pool_email_signin_and_password_policy(template):
    template.has_resource_properties(
        "AWS::Cognito::UserPool",
        {
            "UsernameAttributes": ["email"],
            "AdminCreateUserConfig": {"AllowAdminCreateUserOnly": True},
            "Policies": {
                "PasswordPolicy": Match.object_like(
                    {
                        "MinimumLength": 12,
                        "RequireLowercase": True,
                        "RequireUppercase": True,
                        "RequireNumbers": True,
                        "RequireSymbols": True,
                    }
                )
            },
        },
    )


def test_app_client_is_public_code_grant(template):
    template.has_resource_properties(
        "AWS::Cognito::UserPoolClient",
        {
            "GenerateSecret": False,
            "AllowedOAuthFlows": ["code"],
            "AllowedOAuthFlowsUserPoolClient": True,
        },
    )


def test_outputs_identifiers(template):
    outputs = template.to_json()["Outputs"]
    assert {"UserPoolId", "UserPoolArn", "UserPoolClientId"} <= set(outputs)
