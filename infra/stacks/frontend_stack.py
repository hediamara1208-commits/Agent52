"""FrontendStack: AWS Amplify Hosting app and branch for manual deployment (Req. 22.1, 26.2).

No repository is connected and no access token is stored. ``scripts/publish_frontend.sh`` builds
``frontend/``, writes the runtime ``config.json``, and uploads the zip with
``aws amplify create-deployment`` and ``start-deployment``. The stack has no dependency on the API
or auth stacks; the API stack takes ``ui_origin`` as its CORS origin, which avoids a cycle.
Nothing is deployed by the tests.
"""
from __future__ import annotations

from aws_cdk import CfnOutput, Stack, aws_amplify as amplify
from constructs import Construct

BRANCH_NAME = "main"


class FrontendStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        app_name: str = "alphaforge-guide-ui",
        branch_name: str = BRANCH_NAME,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.branch_name = branch_name
        self.app = amplify.CfnApp(
            self,
            "App",
            name=app_name,
            platform="WEB",
            # Single-page app: rewrite every non-asset path to index.html.
            custom_rules=[
                amplify.CfnApp.CustomRuleProperty(
                    source=r"</^[^.]+$|\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>",
                    target="/index.html",
                    status="200",
                )
            ],
            custom_headers=(
                "customHeaders:\n"
                "  - pattern: '**'\n"
                "    headers:\n"
                "      - key: X-Content-Type-Options\n"
                "        value: nosniff\n"
                "      - key: Referrer-Policy\n"
                "        value: no-referrer\n"
                "  - pattern: '/config.json'\n"
                "    headers:\n"
                "      - key: Cache-Control\n"
                "        value: no-store\n"
            ),
        )
        self.branch = amplify.CfnBranch(
            self,
            "Branch",
            app_id=self.app.attr_app_id,
            branch_name=branch_name,
            stage="PRODUCTION",
            enable_auto_build=False,
        )
        self.ui_origin = f"https://{branch_name}.{self.app.attr_default_domain}"

        CfnOutput(self, "AmplifyAppId", value=self.app.attr_app_id)
        CfnOutput(self, "AmplifyBranchName", value=branch_name)
        CfnOutput(self, "UiUrl", value=self.ui_origin)
