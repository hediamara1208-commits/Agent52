"""Synthesis tests for the CDK FrontendStack and publish script (task 18.5). Nothing is deployed."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytest.importorskip("aws_cdk")
import aws_cdk as cdk  # noqa: E402
from aws_cdk.assertions import Match, Template  # noqa: E402

from infra.stacks.frontend_stack import FrontendStack  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish_frontend.sh"


@pytest.fixture(scope="module")
def template() -> Template:
    app = cdk.App()
    stack = FrontendStack(app, "Frontend", env=cdk.Environment(account="111111111111", region="us-east-1"))
    return Template.from_stack(stack)


def test_amplify_app_is_manual_deploy_without_repository_or_token(template):
    template.resource_count_is("AWS::Amplify::App", 1)
    app = next(iter(template.find_resources("AWS::Amplify::App").values()))["Properties"]
    assert app["Platform"] == "WEB"
    for key in ("Repository", "AccessToken", "OauthToken", "BasicAuthConfig"):
        assert key not in app
    assert app["CustomRules"][0]["Target"] == "/index.html"
    assert "no-store" in app["CustomHeaders"]


def test_branch_has_no_auto_build(template):
    template.has_resource_properties(
        "AWS::Amplify::Branch",
        {"BranchName": "main", "EnableAutoBuild": False, "AppId": Match.any_value()},
    )


def test_outputs_and_no_iam_or_secrets(template):
    outputs = template.to_json()["Outputs"]
    assert {"AmplifyAppId", "AmplifyBranchName", "UiUrl"} <= set(outputs)
    template.resource_count_is("AWS::IAM::Role", 0)


def test_ui_origin_is_https_amplify_origin():
    app = cdk.App()
    stack = FrontendStack(app, "F2")
    assert stack.ui_origin.startswith("https://main.")


def test_publish_script_syntax_and_contents():
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0
    text = SCRIPT.read_text()
    for needle in ("apiUrl", "userPoolId", "userPoolClientId", "create-deployment", "start-deployment", "npm run build"):
        assert needle in text
