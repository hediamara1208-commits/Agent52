"""DataStack: Primary_Store bucket, Athena results bucket, Glue catalog, Athena workgroup.

Req. 8.13, 8.14, 18.4, 18.7, 19.1, 24.7, 26.1. Nothing here is deployed by the tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack, aws_athena as athena, aws_glue as glue
from aws_cdk import aws_iam as iam, aws_s3 as s3
from constructs import Construct

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:  # `cdk` runs app.py from infra/
    sys.path.insert(0, str(_ROOT))

from guide.data.catalog import (  # noqa: E402
    PARQUET_INPUT_FORMAT,
    PARQUET_OUTPUT_FORMAT,
    PARQUET_SERDE,
    table_columns,
)
from guide.data.parquet_io import TABLE_SCHEMAS  # noqa: E402
from infra.iam import IamTargets, athena_query_statements, seed_import_job_statements  # noqa: E402

RESULTS_PREFIX = "results"


class DataStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        bucket_suffix: str = "",
        bucket_name: str = "alphaforge-guide-data",
        results_bucket_name: str = "alphaforge-guide-athena-results",
        prefix: str = "dataset",
        database_name: str = "alphaforge_guide",
        workgroup_name: str = "alphaforge-guide",
        bytes_scanned_cutoff: int = 104857600,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        suffix = f"-{bucket_suffix}" if bucket_suffix else ""
        bucket_name += suffix
        results_bucket_name += suffix
        tables = list(TABLE_SCHEMAS)

        # Primary_Store: system of record, retained when the stack is destroyed.
        self.primary_bucket = s3.Bucket(
            self,
            "PrimaryStore",
            bucket_name=bucket_name,
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
        )
        self.primary_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="DenyDeleteOfSnapshotsAndCurated",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["s3:DeleteObject", "s3:DeleteObjectVersion"],
                resources=[
                    self.primary_bucket.arn_for_objects(f"{prefix}/snapshots/*"),
                    self.primary_bucket.arn_for_objects(f"{prefix}/curated/*"),
                ],
            )
        )

        self.results_bucket = s3.Bucket(
            self,
            "AthenaResults",
            bucket_name=results_bucket_name,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            lifecycle_rules=[s3.LifecycleRule(id="expire-results", expiration=Duration.days(7))],
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Glue catalog: explicit columns from TABLE_SCHEMAS, no crawler.
        self.database = glue.CfnDatabase(
            self,
            "Database",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=database_name, description="AlphaForge Guide dataset snapshots"
            ),
        )
        for table in tables:
            glue_table = glue.CfnTable(
                self,
                f"Table-{table}",
                catalog_id=self.account,
                database_name=database_name,
                table_input=glue.CfnTable.TableInputProperty(
                    name=table,
                    table_type="EXTERNAL_TABLE",
                    parameters={"classification": "parquet", "EXTERNAL": "TRUE"},
                    partition_keys=[glue.CfnTable.ColumnProperty(name="snapshot_id", type="string")],
                    storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                        columns=[
                            glue.CfnTable.ColumnProperty(name=c["Name"], type=c["Type"])
                            for c in table_columns(table)
                        ],
                        location=f"s3://{bucket_name}/{prefix}/curated/{table}/",
                        input_format=PARQUET_INPUT_FORMAT,
                        output_format=PARQUET_OUTPUT_FORMAT,
                        compressed=True,
                        serde_info=glue.CfnTable.SerdeInfoProperty(serialization_library=PARQUET_SERDE),
                    ),
                ),
            )
            glue_table.add_dependency(self.database)

        self.workgroup = athena.CfnWorkGroup(
            self,
            "Workgroup",
            name=workgroup_name,
            description="AlphaForge Guide validation and exploration queries",
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                enforce_work_group_configuration=True,
                publish_cloud_watch_metrics_enabled=True,
                bytes_scanned_cutoff_per_query=bytes_scanned_cutoff,
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{results_bucket_name}/{RESULTS_PREFIX}/",
                    encryption_configuration=athena.CfnWorkGroup.EncryptionConfigurationProperty(
                        encryption_option="SSE_S3"
                    ),
                ),
            ),
        )

        targets = IamTargets(
            account=self.account,
            region=self.region,
            bucket=bucket_name,
            prefix=prefix,
            model_id="",  # not used by the data roles
            guardrail_id="",
            session_table="",
            glue_database=database_name,
            athena_workgroup=workgroup_name,
            results_bucket=results_bucket_name,
            results_prefix=f"{RESULTS_PREFIX}/",
            glue_tables=tuple(tables),
        )
        self.seed_role = self._role("SeedImportRole", "Seed_Import_Job", seed_import_job_statements(targets))
        self.athena_role = self._role("AthenaQueryRole", "Athena query", athena_query_statements(targets))

        CfnOutput(self, "PrimaryStoreBucket", value=self.primary_bucket.bucket_name)
        CfnOutput(self, "AthenaResultsBucket", value=self.results_bucket.bucket_name)
        CfnOutput(self, "AthenaWorkgroup", value=workgroup_name)
        CfnOutput(self, "GlueDatabase", value=database_name)
        CfnOutput(self, "SeedImportRoleArn", value=self.seed_role.role_arn)
        CfnOutput(self, "AthenaQueryRoleArn", value=self.athena_role.role_arn)

    def _role(self, id: str, label: str, statements: list[dict]) -> iam.Role:
        role = iam.Role(
            self,
            id,
            assumed_by=iam.AccountRootPrincipal(),  # principals in this account that hold sts:AssumeRole
            description=f"{label} role (least privilege, no delete)",
        )
        for statement in statements:
            role.add_to_policy(iam.PolicyStatement.from_json(statement))
        return role
