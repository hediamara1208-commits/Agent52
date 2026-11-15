"""AWS Glue partition registration for Dataset_Snapshots (Req. 18.4, 18.5).

The Glue tables are defined explicitly in the CDK DataStack. This module only
adds one ``snapshot_id`` partition per Dataset table. Partition columns come
from ``TABLE_SCHEMAS`` so the catalog and the written Parquet cannot drift.
Registration is idempotent: ``AlreadyExistsException`` counts as success.
"""
from __future__ import annotations

from typing import Any

import pyarrow as pa
from botocore.exceptions import ClientError

from guide.data.parquet_io import TABLE_SCHEMAS
from guide.data.snapshot import SNAPSHOT_ID_RE

PARQUET_INPUT_FORMAT = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
PARQUET_OUTPUT_FORMAT = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
PARQUET_SERDE = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"

_ALREADY_EXISTS = "AlreadyExistsException"


class PartitionRegistrationError(RuntimeError):
    """Raised when a Glue partition cannot be registered."""


def glue_type(arrow_type: pa.DataType) -> str:
    """Map an Arrow type of the Dataset schemas to a Glue column type."""
    if pa.types.is_date32(arrow_type):
        return "date"
    if pa.types.is_string(arrow_type):
        return "string"
    if pa.types.is_float64(arrow_type):
        return "double"
    if pa.types.is_int64(arrow_type):
        return "bigint"
    raise ValueError(f"No Glue type for Arrow type {arrow_type}")


def table_columns(table: str) -> list[dict[str, str]]:
    """Glue column definitions for a Dataset table, from ``TABLE_SCHEMAS``."""
    return [{"Name": f.name, "Type": glue_type(f.type)} for f in TABLE_SCHEMAS[table]]


def partition_location(bucket: str, prefix: str, table: str, snapshot_id: str) -> str:
    base = "/".join(part for part in (prefix.strip("/"),) if part)
    root = f"s3://{bucket}/{base}/" if base else f"s3://{bucket}/"
    return f"{root}curated/{table}/snapshot_id={snapshot_id}/"


def _partition_input(bucket: str, prefix: str, table: str, snapshot_id: str) -> dict[str, Any]:
    return {
        "Values": [snapshot_id],
        "StorageDescriptor": {
            "Columns": table_columns(table),
            "Location": partition_location(bucket, prefix, table, snapshot_id),
            "InputFormat": PARQUET_INPUT_FORMAT,
            "OutputFormat": PARQUET_OUTPUT_FORMAT,
            "SerdeInfo": {"SerializationLibrary": PARQUET_SERDE},
            "Compressed": True,
        },
    }


def register_partitions(glue: Any, database: str, bucket: str, prefix: str, snapshot_id: str) -> list[str]:
    """Register the ``snapshot_id`` partition for each of the five Dataset tables.

    Returns the table names handled. Existing partitions are treated as
    success, so a retry is safe. Any other failure raises
    ``PartitionRegistrationError`` naming the table.
    """
    if not isinstance(snapshot_id, str) or not SNAPSHOT_ID_RE.match(snapshot_id):
        raise ValueError(f"Invalid snapshot_id: {snapshot_id!r}")

    registered: list[str] = []
    for table in TABLE_SCHEMAS:
        try:
            response = glue.batch_create_partition(
                DatabaseName=database,
                TableName=table,
                PartitionInputList=[_partition_input(bucket, prefix, table, snapshot_id)],
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == _ALREADY_EXISTS:
                registered.append(table)
                continue
            raise PartitionRegistrationError(f"{table}: {error}") from error

        failures = [
            err
            for err in (response or {}).get("Errors", [])
            if err.get("ErrorDetail", {}).get("ErrorCode") != _ALREADY_EXISTS
        ]
        if failures:
            detail = failures[0].get("ErrorDetail", {})
            raise PartitionRegistrationError(
                f"{table}: {detail.get('ErrorCode', 'unknown error')}: {detail.get('ErrorMessage', '')}"
            )
        registered.append(table)
    return registered
