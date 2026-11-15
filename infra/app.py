#!/usr/bin/env python3
"""CDK app entry point (region us-east-1).

All settings come from CDK context (``infra/cdk.json`` or ``-c key=value``).
No credentials are read or stored here; the AWS credential chain is used by the CDK CLI.
Stacks (deploy order): GuideDataStack, GuideFrontendStack, GuideAuthStack, GuideRuntimeStack,
GuideApiStack, GuideOpsStack. Values pass between stacks as CloudFormation references, with no cycles:
Frontend.ui_origin -> Auth callbacks and Api CORS; Auth ids -> Runtime (identity flag); Runtime ARN -> Api.
The Bedrock guardrail already exists (id and version come from ``config.yaml``), so GuardrailStack is not wired.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

import aws_cdk as cdk

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from infra.stacks.api_stack import ApiStack  # noqa: E402
from infra.stacks.auth_stack import DEFAULT_CALLBACK_URLS, AuthStack  # noqa: E402
from infra.stacks.data_stack import DataStack  # noqa: E402
from infra.stacks.frontend_stack import FrontendStack  # noqa: E402
from infra.stacks.ops_stack import OpsStack  # noqa: E402
from infra.stacks.runtime_stack import RuntimeStack  # noqa: E402

REGION = "us-east-1"
FLAGS = (
    "enable_waf",
    "enable_kms",
    "enable_cloudtrail",
    "enable_object_lock",
    "enable_gateway",
    "enable_identity",
    "enable_pipeline",
)


@dataclass(frozen=True)
class Settings:
    region: str
    bucket_suffix: str
    model_id: str
    budget_amount: float
    budget_email: str
    enable_waf: bool
    enable_kms: bool
    enable_cloudtrail: bool
    enable_object_lock: bool
    enable_gateway: bool
    enable_identity: bool
    enable_pipeline: bool


def _flag(value: object) -> bool:
    """`-c flag=true` arrives as a string; cdk.json values arrive as bool."""
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def load_settings(app: cdk.App) -> Settings:
    ctx = app.node.try_get_context
    return Settings(
        region=str(ctx("region") or REGION),
        bucket_suffix=str(ctx("bucket_suffix") or ""),
        model_id=str(ctx("model_id") or ""),
        budget_amount=float(ctx("budget_amount") or 0),
        budget_email=str(ctx("budget_email") or ""),
        **{name: _flag(ctx(name)) for name in FLAGS},
    )


def _read_config() -> dict:
    with open(_ROOT / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def build_app() -> cdk.App:
    app = cdk.App()
    settings = load_settings(app)
    if settings.region != REGION:
        raise ValueError(f"region must be {REGION}, got {settings.region!r}")
    # Account comes from the CLI's resolved credentials at deploy time, never from code.
    env = cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=settings.region
    )
    config = _read_config()
    suffix = settings.bucket_suffix
    model_id = settings.model_id or str(config.get("model_id") or "")
    session_table = str(config.get("session_table") or "alphaforge-guide-sessions")
    bucket_name = str(config.get("s3_bucket") or "alphaforge-guide-data")
    prefix = str(config.get("s3_prefix") or "dataset")
    deps_dir = str(_ROOT / "build" / "api_deps")  # built by scripts/build_api_deps.sh; optional

    data = DataStack(
        app, "GuideDataStack", env=env, bucket_suffix=suffix, bucket_name=bucket_name, prefix=prefix
    )
    frontend = FrontendStack(app, "GuideFrontendStack", env=env)
    auth = AuthStack(
        app,
        "GuideAuthStack",
        env=env,
        callback_urls=[*DEFAULT_CALLBACK_URLS, frontend.ui_origin + "/"],
    )
    runtime = RuntimeStack(
        app,
        "GuideRuntimeStack",
        env=env,
        model_id=model_id,
        guardrail_id=str(config.get("guardrail_id") or ""),
        guardrail_version=str(config.get("guardrail_version") or "DRAFT"),
        bucket_name=bucket_name,
        bucket_suffix=suffix,
        prefix=prefix,
        session_table=session_table,
        enable_identity=settings.enable_identity,
        user_pool_id=auth.user_pool.user_pool_id if settings.enable_identity else "",
        user_pool_client_id=auth.user_pool_client.user_pool_client_id if settings.enable_identity else "",
    )
    api = ApiStack(
        app,
        "GuideApiStack",
        env=env,
        user_pool_arn=auth.user_pool.user_pool_arn,
        agent_runtime_arn=runtime.runtime.attr_agent_runtime_arn,
        cors_origin=frontend.ui_origin,
        session_table=session_table,
        bucket_name=bucket_name + (f"-{suffix}" if suffix else ""),
        prefix=prefix,
        deps_dir=deps_dir,
    )
    ops = OpsStack(app, "GuideOpsStack", env=env)
    api.add_dependency(data)
    runtime.add_dependency(data)
    ops.add_dependency(api)
    return app


if __name__ == "__main__":
    build_app().synth()
