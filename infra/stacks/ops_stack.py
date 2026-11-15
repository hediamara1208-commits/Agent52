"""OpsStack (Tier 2 lean): log groups and Bedrock model invocation logging (Req. 25.3, 25.6).

Creates 30-day log groups for the Session_API Lambda and the Agent_Runtime, and a log group for Bedrock
model invocation logging, switched on through an AWS-SDK custom resource. The dashboard, alarms, SNS
topic, and AWS Budgets are task 18.12. Metrics use the ``AlphaForgeGuide`` namespace (``runtime/app.py``).
Nothing is deployed by the tests; no credentials are stored.
"""
from __future__ import annotations

from aws_cdk import CfnOutput, RemovalPolicy, Stack, aws_iam as iam, aws_logs as logs
from aws_cdk import custom_resources as cr
from constructs import Construct

METRIC_NAMESPACE = "AlphaForgeGuide"
SESSION_API_LOG_GROUP = "/aws/lambda/guide-session-api"
AGENT_RUNTIME_LOG_GROUP = "/aws/bedrock-agentcore/runtimes/guide_runtime"
BEDROCK_INVOCATION_LOG_GROUP = "/aws/bedrock/guide-model-invocations"


class OpsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        def group(cid: str, name: str) -> logs.LogGroup:
            return logs.LogGroup(
                self,
                cid,
                log_group_name=name,
                retention=logs.RetentionDays.ONE_MONTH,
                removal_policy=RemovalPolicy.DESTROY,
            )

        self.session_api_logs = group("SessionApiLogs", SESSION_API_LOG_GROUP)
        self.agent_runtime_logs = group("AgentRuntimeLogs", AGENT_RUNTIME_LOG_GROUP)
        self.invocation_logs = group("BedrockInvocationLogs", BEDROCK_INVOCATION_LOG_GROUP)

        # Role that Bedrock assumes to write invocation logs (this account only).
        self.invocation_role = iam.Role(
            self,
            "BedrockInvocationLoggingRole",
            role_name="guide-bedrock-invocation-logging-role",
            assumed_by=iam.ServicePrincipal(
                "bedrock.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock:{self.region}:{self.account}:*"},
                },
            ),
            description="Bedrock model invocation logging to CloudWatch Logs",
        )
        self.invocation_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[self.invocation_logs.log_group_arn, f"{self.invocation_logs.log_group_arn}:log-stream:*"],
            )
        )

        logging_config = {
            "loggingConfig": {
                "cloudWatchConfig": {
                    "logGroupName": self.invocation_logs.log_group_name,
                    "roleArn": self.invocation_role.role_arn,
                },
                "textDataDeliveryEnabled": True,
                "imageDataDeliveryEnabled": False,
                "embeddingDataDeliveryEnabled": False,
            }
        }
        enable = cr.AwsSdkCall(
            service="Bedrock",
            action="putModelInvocationLoggingConfiguration",
            parameters=logging_config,
            physical_resource_id=cr.PhysicalResourceId.of("guide-bedrock-invocation-logging"),
        )
        self.invocation_logging = cr.AwsCustomResource(
            self,
            "BedrockInvocationLogging",
            on_create=enable,
            on_update=enable,
            on_delete=cr.AwsSdkCall(
                service="Bedrock",
                action="deleteModelInvocationLoggingConfiguration",
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    iam.PolicyStatement(
                        actions=[
                            "bedrock:PutModelInvocationLoggingConfiguration",
                            "bedrock:DeleteModelInvocationLoggingConfiguration",
                        ],
                        resources=["*"],  # these Bedrock actions do not support resource-level scoping
                    ),
                    iam.PolicyStatement(actions=["iam:PassRole"], resources=[self.invocation_role.role_arn]),
                ]
            ),
            install_latest_aws_sdk=False,
        )
        self.invocation_logging.node.add_dependency(self.invocation_logs, self.invocation_role)

        CfnOutput(self, "SessionApiLogGroupName", value=self.session_api_logs.log_group_name)
        CfnOutput(self, "AgentRuntimeLogGroupName", value=self.agent_runtime_logs.log_group_name)
        CfnOutput(self, "BedrockInvocationLogGroupName", value=self.invocation_logs.log_group_name)
