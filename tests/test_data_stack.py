"""Synthesis tests for the CDK DataStack (task 12.7). Nothing is deployed."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("aws_cdk")
import aws_cdk as cdk  # noqa: E402
from aws_cdk.assertions import Match, Template  # noqa: E402

from guide.data.parquet_io import TABLE_SCHEMAS  # noqa: E402
from infra.stacks.data_stack import DataStack  # noqa: E402


@pytest.fixture(scope="module")
def template() -> Template:
    app = cdk.App()
    stack = DataStack(app, "Data", env=cdk.Environment(account="111111111111", region="us-east-1"))
    return Template.from_stack(stack)


def test_primary_bucket_is_protected_and_retained(template):
    template.has_resource(
        "AWS::S3::Bucket",
        {
            "Properties": {
                "BucketName": "alphaforge-guide-data",
                "VersioningConfiguration": {"Status": "Enabled"},
                "PublicAccessBlockConfiguration": Match.object_like({"BlockPublicAcls": True, "RestrictPublicBuckets": True}),
                "BucketEncryption": Match.any_value(),
            },
            "DeletionPolicy": "Retain",
        },
    )
    policies = template.find_resources("AWS::S3::BucketPolicy")
    statements = [s for p in policies.values() for s in p["Properties"]["PolicyDocument"]["Statement"]]
    assert any(s.get("Condition", {}).get("Bool", {}).get("aws:SecureTransport") == "false" for s in statements)
    deny = next(s for s in statements if s.get("Sid") == "DenyDeleteOfSnapshotsAndCurated")
    assert deny["Effect"] == "Deny" and deny["Principal"] == {"AWS": "*"}
    assert set(deny["Action"]) == {"s3:DeleteObject", "s3:DeleteObjectVersion"}
    assert len(deny["Resource"]) == 2


def test_results_bucket_expires_after_seven_days(template):
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketName": "alphaforge-guide-athena-results",
            "LifecycleConfiguration": {"Rules": [Match.object_like({"ExpirationInDays": 7, "Status": "Enabled"})]},
        },
    )


def test_glue_tables_match_table_schemas_and_no_crawler(template):
    tables = template.find_resources("AWS::Glue::Table")
    assert len(tables) == len(TABLE_SCHEMAS) == 5
    for res in tables.values():
        ti = res["Properties"]["TableInput"]
        assert ti["Name"] in TABLE_SCHEMAS
        assert [c["Name"] for c in ti["StorageDescriptor"]["Columns"]] == TABLE_SCHEMAS[ti["Name"]].names
        assert ti["PartitionKeys"] == [{"Name": "snapshot_id", "Type": "string"}]
        assert ti["StorageDescriptor"]["Location"].endswith(f"/dataset/curated/{ti['Name']}/")
        assert "ParquetHiveSerDe" in ti["StorageDescriptor"]["SerdeInfo"]["SerializationLibrary"]
    template.resource_count_is("AWS::Glue::Crawler", 0)
    template.has_resource_properties("AWS::Glue::Database", {"DatabaseInput": {"Name": "alphaforge_guide", "Description": Match.any_value()}})


def test_workgroup_is_enforced(template):
    template.has_resource_properties(
        "AWS::Athena::WorkGroup",
        {
            "Name": "alphaforge-guide",
            "WorkGroupConfiguration": Match.object_like(
                {
                    "EnforceWorkGroupConfiguration": True,
                    "BytesScannedCutoffPerQuery": 104857600,
                    "ResultConfiguration": {
                        "OutputLocation": "s3://alphaforge-guide-athena-results/results/",
                        "EncryptionConfiguration": {"EncryptionOption": "SSE_S3"},
                    },
                }
            ),
        },
    )


def test_roles_have_no_delete_or_wildcards(template):
    assert len(template.find_resources("AWS::IAM::Role", {"Properties": {"AssumeRolePolicyDocument": Match.any_value()}})) >= 2
    for res in template.find_resources("AWS::IAM::Policy").values():
        for s in res["Properties"]["PolicyDocument"]["Statement"]:
            actions = s["Action"] if isinstance(s["Action"], list) else [s["Action"]]
            assert not any(a == "*" or a.endswith(":*") or "Delete" in a for a in actions), actions
            resources = s["Resource"] if isinstance(s["Resource"], list) else [s["Resource"]]
            assert "*" not in [r for r in resources if isinstance(r, str)], json.dumps(s)
