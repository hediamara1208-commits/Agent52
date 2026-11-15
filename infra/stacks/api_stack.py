"""ApiStack: Session_Store, Session_API Lambda, REST API with Cognito authorizer (Req. 22.3, 22.9 to 22.12, 25.2, 25.8).

The Agent_Runtime ARN and the user pool ARN are plain strings (stack outputs or context values), so this
stack has no dependency cycle with RuntimeStack or AuthStack. The Session_Store name is a config value
shared with the runtime's IAM policy. Exactly the six routes of ``api.handler.ROUTES`` exist; the only
other methods are the unauthenticated CORS preflight ``OPTIONS`` answers (mock integration, no data).
Nothing is deployed by the tests; no credentials are stored.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack, aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from constructs import Construct

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.handler import ROUTES  # noqa: E402
from infra.iam import IamTargets, session_api_lambda_statements  # noqa: E402

# Only what the handler imports goes into the asset.
_ASSET_EXCLUDE = [
    "*",
    "!api",
    "!api/**",
    "!guide",
    "!guide/**",
    "!config.yaml",
    "**/__pycache__",
    "**/*.pyc",
    "**/tests",
]


# AWS SDK for pandas managed layer (pandas, numpy, pyarrow, boto3), Python 3.11 x86_64, us-east-1.
DEFAULT_PANDAS_LAYER_ARN = "arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python311:36"
class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        user_pool_arn: str,
        agent_runtime_arn: str,
        cors_origin: str,
        session_table: str = "alphaforge-guide-sessions",
        layer_arns: Sequence[str] = (DEFAULT_PANDAS_LAYER_ARN,),
        deps_dir: str | None = None,
        bucket_name: str = "alphaforge-guide-data",
        prefix: str = "dataset",
        throttle_rate: int = 10,
        throttle_burst: int = 20,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        if not cors_origin or cors_origin == "*":
            raise ValueError("cors_origin must be the Amplify app origin, not empty or '*'")

        # Session_Store: owner (HASH), sk (RANGE), on demand, ttl attribute (Req. 22.5).
        self.table = dynamodb.Table(
            self,
            "SessionStore",
            table_name=session_table,
            partition_key=dynamodb.Attribute(name="owner", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Session_API role: scoped statements from the IAM helper (Req. 25.2).
        targets = IamTargets(
            account=self.account,
            region=self.region,
            bucket=bucket_name,
            prefix=prefix,
            model_id="",
            guardrail_id="",
            session_table=session_table,
            glue_database="",
            athena_workgroup="",
            results_bucket="",
        )
        self.role = iam.Role(
            self,
            "SessionApiRole",
            role_name="guide-session-api-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Session_API Lambda (Session_Store, InvokeAgentRuntime, logs, X-Ray)",
        )
        self.role.attach_inline_policy(
            iam.Policy(
                self,
                "SessionApiPolicy",
                statements=[
                    iam.PolicyStatement.from_json(s)
                    for s in session_api_lambda_statements(targets, agent_runtime_arn)
                ],
            )
        )

        layers = [
            _lambda.LayerVersion.from_layer_version_arn(self, f"Layer{i}", arn)
            for i, arn in enumerate(layer_arns)
        ]
        # Pure-Python deps (jsonschema, pyyaml and friends) built by scripts/build_api_deps.sh.
        if deps_dir and Path(deps_dir).is_dir():
            layers.append(
                _lambda.LayerVersion(
                    self,
                    "DepsLayer",
                    code=_lambda.Code.from_asset(deps_dir),
                    compatible_runtimes=[_lambda.Runtime.PYTHON_3_11],
                )
            )
        self.function = _lambda.Function(
            self,
            "SessionApi",
            function_name="guide-session-api",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="api.handler.handler",
            code=_lambda.Code.from_asset(str(_ROOT), exclude=_ASSET_EXCLUDE),
            role=self.role,
            timeout=Duration.seconds(29),  # API Gateway REST integrations cap at 29 s
            memory_size=512,
            tracing=_lambda.Tracing.ACTIVE,
            layers=layers,
            environment={
                "GUIDE_SESSION_TABLE": session_table,
                "GUIDE_S3_BUCKET": bucket_name,
                "GUIDE_S3_PREFIX": prefix,
                "GUIDE_AGENT_RUNTIME_ARN": agent_runtime_arn,
                "GUIDE_CORS_ORIGIN": cors_origin,
                # Only /tmp is writable on Lambda; the config default is the cloud-IDE path.
                "GUIDE_CACHE_DIR": "/tmp/guide-cache",
            },
        )

        # REST API: Cognito authorizer on every route, CORS limited to the Amplify origin.
        user_pool = cognito.UserPool.from_user_pool_arn(self, "UserPool", user_pool_arn)
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "Authorizer", cognito_user_pools=[user_pool], identity_source="method.request.header.Authorization"
        )
        self.api = apigw.RestApi(
            self,
            "SessionApiGateway",
            rest_api_name="guide-session-api",
            description="Session_API (guidance only; no order, transfer, or brokerage route)",
            cloud_watch_role=False,
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                tracing_enabled=True,
                throttling_rate_limit=throttle_rate,
                throttling_burst_limit=throttle_burst,
            ),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=[cors_origin],
                allow_methods=sorted({m for m, _ in ROUTES}) + ["OPTIONS"],
                allow_headers=["Authorization", "Content-Type"],
                max_age=Duration.hours(1),
            ),
        )
        # Error responses produced by the gateway (401, 403, 429, 5xx) also carry the CORS origin.
        cors_headers = {"Access-Control-Allow-Origin": f"'{cors_origin}'"}
        self.api.add_gateway_response(
            "Default4xx", type=apigw.ResponseType.DEFAULT_4_XX, response_headers=cors_headers
        )
        self.api.add_gateway_response(
            "Default5xx", type=apigw.ResponseType.DEFAULT_5_XX, response_headers=cors_headers
        )

        integration = apigw.LambdaIntegration(self.function)
        resources: dict[str, apigw.IResource] = {"": self.api.root}
        for method, path in ROUTES:
            current = ""
            for segment in path.strip("/").split("/"):
                parent, current = current, f"{current}/{segment}"
                if current not in resources:
                    resources[current] = resources[parent].add_resource(segment)
            resources[current].add_method(
                method,
                integration,
                authorization_type=apigw.AuthorizationType.COGNITO,
                authorizer=authorizer,
                request_parameters={"method.request.header.Authorization": True},
            )

        CfnOutput(self, "SessionTableName", value=self.table.table_name)
        CfnOutput(self, "ApiUrl", value=self.api.url)
        CfnOutput(self, "SessionApiFunctionName", value=self.function.function_name)
