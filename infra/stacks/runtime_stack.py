"""RuntimeStack: ECR image asset, AgentCore Memory, Application_Role, AgentCore Runtime (Req. 8.9, 8.10, 23.1, 23.3, 23.9, 25.1).

The Session_Store table is referenced by name (a config value), so IAM ARNs are built from names and
this stack has no dependency cycle with the API stack. When ``enable_identity`` is set the runtime
accepts a JWT from the Cognito user pool. Nothing here is deployed by the tests; no credentials are
stored.
"""
from __future__ import annotations

import sys
from pathlib import Path

from aws_cdk import CfnOutput, Duration, Stack, aws_bedrockagentcore as agentcore, aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from constructs import Construct

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from infra.iam import IamTargets, application_role_statements  # noqa: E402

# Only what runtime/Dockerfile copies goes into the asset.
_ASSET_EXCLUDE = [
    "*",
    "!guide",
    "!guide/**",
    "!runtime",
    "!runtime/**",
    "!config.yaml",
    "**/__pycache__",
    "**/*.pyc",
    "**/tests",
]


class RuntimeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        model_id: str = "us.anthropic.claude-sonnet-5-5",
        guardrail_id: str = "3981l0ehd4uu",
        guardrail_version: str = "DRAFT",
        bucket_name: str = "alphaforge-guide-data",
        prefix: str = "dataset",
        session_table: str = "alphaforge-guide-sessions",
        glue_database: str = "alphaforge_guide",
        athena_workgroup: str = "alphaforge-guide",
        results_bucket_name: str = "alphaforge-guide-athena-results",
        bucket_suffix: str = "",
        enable_identity: bool = False,
        user_pool_id: str = "",
        user_pool_client_id: str = "",
        memory_expiry_days: int = 90,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        if enable_identity and not (user_pool_id and user_pool_client_id):
            raise ValueError("enable_identity requires user_pool_id and user_pool_client_id")
        suffix = f"-{bucket_suffix}" if bucket_suffix else ""

        # Container image (arm64), built from the repository root with runtime/Dockerfile.
        self.image = ecr_assets.DockerImageAsset(
            self,
            "RuntimeImage",
            directory=str(_ROOT),
            file="runtime/Dockerfile",
            platform=ecr_assets.Platform.LINUX_ARM64,
            exclude=_ASSET_EXCLUDE,
        )

        # AgentCore Memory: contracts and summaries keyed by user and profile (Req. 8.4, 23.4).
        self.memory = agentcore.CfnMemory(
            self,
            "Memory",
            name="guide_memory",
            description="Investor contracts and summaries, keyed by user and profile",
            event_expiry_duration=memory_expiry_days,
        )

        targets = IamTargets(
            account=self.account,
            region=self.region,
            bucket=bucket_name + suffix,
            prefix=prefix,
            model_id=model_id,
            guardrail_id=guardrail_id,
            session_table=session_table,
            glue_database=glue_database,
            athena_workgroup=athena_workgroup,
            results_bucket=results_bucket_name + suffix,
            memory_id=self.memory.attr_memory_id,
        )

        # Application_Role: least privilege from the IAM helper (Req. 25.1).
        self.application_role = iam.Role(
            self,
            "ApplicationRole",
            role_name="guide-application-role",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={"StringEquals": {"aws:SourceAccount": self.account}},
            ),
            description="Agent_Runtime execution role (read-only snapshots, Bedrock, Memory, telemetry)",
            max_session_duration=Duration.hours(1),
        )
        self.application_role.attach_inline_policy(
            iam.Policy(
                self,
                "ApplicationPolicy",
                statements=[iam.PolicyStatement.from_json(s) for s in application_role_statements(targets)],
            )
        )
        # Pull the runtime image; the repository grant scopes BatchGetImage to this repo.
        self.image.repository.grant_pull(self.application_role)

        authorizer = None
        if enable_identity:
            discovery = (
                f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"
            )
            authorizer = agentcore.CfnRuntime.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnRuntime.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=discovery,
                    allowed_clients=[user_pool_client_id],
                )
            )

        self.runtime = agentcore.CfnRuntime(
            self,
            "Runtime",
            agent_runtime_name="guide_runtime",
            description="Guide_System orchestrator: run_session behind one entry point",
            role_arn=self.application_role.role_arn,
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=self.image.image_uri
                )
            ),
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(network_mode="PUBLIC"),
            authorizer_configuration=authorizer,
            environment_variables={
                "GUIDE_AGENTCORE_MEMORY_ID": self.memory.attr_memory_id,
                "GUIDE_SESSION_TABLE": session_table,
                "GUIDE_S3_BUCKET": bucket_name + suffix,
                "GUIDE_S3_PREFIX": prefix,
                "GUIDE_MODEL_ID": model_id,
                "GUIDE_GUARDRAIL_ID": guardrail_id,
                "GUIDE_GUARDRAIL_VERSION": guardrail_version,
            },
        )
        self.runtime.node.add_dependency(self.application_role)

        CfnOutput(self, "AgentRuntimeArn", value=self.runtime.attr_agent_runtime_arn)
        CfnOutput(self, "AgentCoreMemoryId", value=self.memory.attr_memory_id)
        CfnOutput(self, "ApplicationRoleArn", value=self.application_role.role_arn)
