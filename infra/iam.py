"""Least-privilege IAM statements for the Guide_System roles (design: AWS deployment, IAM table).

Pure Python: every function returns plain IAM policy statements (dicts). The CDK stacks wrap
them with ``iam.PolicyStatement.from_json``. Keeping this module free of ``aws_cdk`` lets the
policy rules be tested without CDK installed.

Rules enforced here and by ``tests/test_iam_policies.py``:
- no ``s3:DeleteObject`` / ``s3:DeleteObjectVersion``;
- no ``*`` action and no ``*`` service wildcard;
- no bare ``*`` resource, except the four actions listed in ``RESOURCE_STAR_EXCEPTIONS``,
  which AWS does not allow to be scoped to a resource;
- no brokerage or bank permissions (the system only gives guidance).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

Statement = dict[str, Any]

# AWS offers no resource-level scoping for these actions. CloudWatch is limited by a
# namespace condition; the X-Ray actions cannot be conditioned at all.

RESOURCE_STAR_EXCEPTIONS = frozenset(
    {"cloudwatch:PutMetricData", "xray:PutTraceSegments", "xray:PutTelemetryRecords"}
)

METRIC_NAMESPACE = "AlphaForgeGuide"
GLUE_TABLES = ("assets_universe", "prices_daily", "macro_rates", "fx_usdcad_daily", "corporate_actions")
# Regions a US cross-region inference profile can route to.
US_PROFILE_REGIONS = ("us-east-1", "us-east-2", "us-west-2")


@dataclass(frozen=True)
class IamTargets:
    """Names and identifiers the policies are scoped to. No credentials."""

    account: str
    region: str
    bucket: str
    prefix: str  # e.g. "dataset"
    model_id: str  # e.g. "us.anthropic.claude-sonnet-5-5"
    guardrail_id: str
    session_table: str
    glue_database: str
    athena_workgroup: str
    results_bucket: str
    results_prefix: str = "results/"
    memory_id: str = ""  # AgentCore Memory id; empty until the runtime stack creates it
    glue_tables: tuple[str, ...] = GLUE_TABLES

    def key(self, suffix: str) -> str:
        return f"arn:aws:s3:::{self.bucket}/{self.prefix}/{suffix}"

    @property
    def bucket_arn(self) -> str:
        return f"arn:aws:s3:::{self.bucket}"

    @property
    def results_bucket_arn(self) -> str:
        return f"arn:aws:s3:::{self.results_bucket}"


def _foundation_model_id(model_id: str) -> str:
    head, _, rest = model_id.partition(".")
    return rest if head in {"us", "eu", "apac", "global"} and rest else model_id


def _stmt(sid: str, actions: list[str], resources: list[str], condition: dict | None = None) -> Statement:
    s: Statement = {"Sid": sid, "Effect": "Allow", "Action": actions, "Resource": resources}
    if condition:
        s["Condition"] = condition
    return s


def _glue_arns(t: IamTargets, *, tables: bool = True) -> list[str]:
    base = f"arn:aws:glue:{t.region}:{t.account}"
    arns = [f"{base}:catalog", f"{base}:database/{t.glue_database}"]
    if tables:
        arns += [f"{base}:table/{t.glue_database}/{name}" for name in t.glue_tables]
    return arns


def _snapshot_keys(t: IamTargets) -> list[str]:
    return [t.key("snapshots/*"), t.key("curated/*"), t.key("pointers/current.json")]


def application_role_statements(t: IamTargets) -> list[Statement]:
    """Agent_Runtime role: read-only on snapshots; model, Guardrail, Session_Store, Memory, telemetry."""
    fm = _foundation_model_id(t.model_id)
    model_arns = [f"arn:aws:bedrock:{r}::foundation-model/{fm}" for r in US_PROFILE_REGIONS]
    model_arns.append(f"arn:aws:bedrock:{t.region}:{t.account}:inference-profile/{t.model_id}")
    statements = [
        _stmt("BedrockInvoke", ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"], model_arns),
        _stmt(
            "BedrockGuardrail",
            ["bedrock:ApplyGuardrail"],
            [f"arn:aws:bedrock:{t.region}:{t.account}:guardrail/{t.guardrail_id}"],
        ),
        _stmt(
            "AgentCoreWebSearch",  # Newsroom: recent news as Context Exhibits (AWS-owned tool ARN)
            ["bedrock-agentcore:InvokeWebSearch"],
            [f"arn:aws:bedrock-agentcore:{t.region}:aws:tool/web-search.v1"],
        ),
        _stmt("SnapshotRead", ["s3:GetObject", "s3:GetObjectVersion"], _snapshot_keys(t)),
        _stmt(
            "SessionStoreItems",
            # Query: the Judge reads Precedents from the shared partition (Req. 31).
            ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"],
            [f"arn:aws:dynamodb:{t.region}:{t.account}:table/{t.session_table}"],
        ),
    ]
    if t.memory_id:
        statements.append(
            _stmt(
                "AgentCoreMemory",
                [
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:GetEvent",
                    "bedrock-agentcore:RetrieveMemoryRecords",
                ],
                [f"arn:aws:bedrock-agentcore:{t.region}:{t.account}:memory/{t.memory_id}"],
            )
        )
    statements += [
        _stmt(
            "LogsWrite",
            ["logs:CreateLogStream", "logs:PutLogEvents"],
            [f"arn:aws:logs:{t.region}:{t.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"],
        ),
        # AgentCore writes to /aws/bedrock-agentcore/runtimes/<runtime-id>-<endpoint>, which the
        # runtime creates itself; without these actions container start-up errors are never logged.
        _stmt(
            "LogsGroup",
            ["logs:CreateLogGroup", "logs:DescribeLogStreams"],
            [f"arn:aws:logs:{t.region}:{t.account}:log-group:/aws/bedrock-agentcore/runtimes/*"],
        ),
        _stmt("XRayWrite", ["xray:PutTraceSegments", "xray:PutTelemetryRecords"], ["*"]),
        _stmt(
            "MetricsWrite",
            ["cloudwatch:PutMetricData"],
            ["*"],
            {"StringEquals": {"cloudwatch:namespace": METRIC_NAMESPACE}},
        ),
    ]
    return statements


def session_api_lambda_statements(t: IamTargets, runtime_arn: str) -> list[Statement]:
    """Session_API Lambda: Session_Store access, read snapshots (universe), start the Agent_Runtime, write logs."""
    return [
        _stmt(
            "SessionStore",
            ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"],
            [f"arn:aws:dynamodb:{t.region}:{t.account}:table/{t.session_table}"],
        ),
        _stmt("SnapshotRead", ["s3:GetObject"], _snapshot_keys(t)),
        _stmt(
            "InvokeRuntime",
            ["bedrock-agentcore:InvokeAgentRuntime"],
            [runtime_arn, f"{runtime_arn}/runtime-endpoint/*"],
        ),
        _stmt(
            "LogsWrite",
            ["logs:CreateLogStream", "logs:PutLogEvents"],
            [f"arn:aws:logs:{t.region}:{t.account}:log-group:/aws/lambda/*:log-stream:*"],
        ),
        _stmt("XRayWrite", ["xray:PutTraceSegments", "xray:PutTelemetryRecords"], ["*"]),
    ]


def athena_query_statements(t: IamTargets) -> list[Statement]:
    """Athena query role: workgroup, Glue read, curated read, results prefix."""
    return [
        _stmt(
            "AthenaWorkgroup",
            [
                "athena:StartQueryExecution",
                "athena:GetQueryExecution",
                "athena:GetQueryResults",
            ],
            [f"arn:aws:athena:{t.region}:{t.account}:workgroup/{t.athena_workgroup}"],
        ),
        _stmt(
            "GlueRead",
            ["glue:GetDatabase", "glue:GetTable", "glue:GetPartitions"],
            _glue_arns(t),
        ),
        _stmt("CuratedRead", ["s3:GetObject"], [t.key("curated/*")]),
        _stmt(
            "CuratedList",
            ["s3:ListBucket"],
            [t.bucket_arn],
            {"StringLike": {"s3:prefix": [f"{t.prefix}/curated/*"]}},
        ),
        _stmt(
            "ResultsWrite",
            ["s3:GetObject", "s3:PutObject"],
            [f"{t.results_bucket_arn}/{t.results_prefix}*"],
        ),
        _stmt("ResultsLocation", ["s3:GetBucketLocation"], [t.results_bucket_arn]),
        _stmt(
            "ResultsList",
            ["s3:ListBucket"],
            [t.results_bucket_arn],
            {"StringLike": {"s3:prefix": [f"{t.results_prefix}*"]}},
        ),
    ]


def seed_import_job_statements(t: IamTargets) -> list[Statement]:
    """Seed_Import_Job: write snapshots, curated tables, pointer; register partitions; plus Athena query."""
    return [
        _stmt(
            "SnapshotReadWrite",
            ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"],
            _snapshot_keys(t),
        ),
        _stmt(
            "GluePartitions",
            ["glue:GetTable", "glue:BatchCreatePartition"],
            _glue_arns(t),
        ),
        *athena_query_statements(t),
    ]


def all_actions(statements: list[Statement]) -> set[str]:
    out: set[str] = set()
    for s in statements:
        acts = s["Action"]
        out.update([acts] if isinstance(acts, str) else acts)
    return out


def policy_document(statements: list[Statement]) -> dict[str, Any]:
    return {"Version": "2012-10-17", "Statement": statements}


def violations(statements: list[Statement]) -> list[str]:
    """Return rule violations for a statement list; an empty list means the policy is acceptable."""
    problems: list[str] = []
    for s in statements:
        sid = s.get("Sid", "?")
        actions = [s["Action"]] if isinstance(s["Action"], str) else list(s["Action"])
        resources = [s["Resource"]] if isinstance(s["Resource"], str) else list(s["Resource"])
        if s.get("Effect") != "Allow":
            problems.append(f"{sid}: only Allow statements are built here")
        for a in actions:
            if "*" in a:
                problems.append(f"{sid}: wildcard action {a}")
            if a.startswith("s3:Delete"):
                problems.append(f"{sid}: delete action {a}")
            if a.split(":")[0] in {"brokerage", "bank", "banking", "payments"}:
                problems.append(f"{sid}: brokerage or bank action {a}")
        if "*" in resources and not all(a in RESOURCE_STAR_EXCEPTIONS for a in actions):
            problems.append(f"{sid}: bare * resource")
        if "cloudwatch:PutMetricData" in actions and "Condition" not in s:
            problems.append(f"{sid}: PutMetricData needs a namespace condition")
    return problems
