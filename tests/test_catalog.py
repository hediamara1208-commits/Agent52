import boto3
import pytest
from botocore.stub import Stubber

from guide.data.catalog import PartitionRegistrationError, register_partitions
from guide.data.parquet_io import TABLE_SCHEMAS

SID = "20261113T000000Z-starter"


def _client():
    return boto3.client(
        "glue", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y"
    )


def test_registers_one_partition_per_table():
    glue = _client()
    with Stubber(glue) as stub:
        for table in TABLE_SCHEMAS:
            stub.add_response(
                "batch_create_partition",
                {"Errors": []},
                {
                    "DatabaseName": "db",
                    "TableName": table,
                    "PartitionInputList": [
                        {
                            "Values": [SID],
                            "StorageDescriptor": {
                                "Columns": [
                                    {"Name": f.name, "Type": t}
                                    for f, t in zip(
                                        TABLE_SCHEMAS[table],
                                        [
                                            {"date32[day]": "date", "string": "string",
                                             "double": "double", "int64": "bigint"}[str(f.type)]
                                            for f in TABLE_SCHEMAS[table]
                                        ],
                                    )
                                ],
                                "Location": f"s3://b/p/curated/{table}/snapshot_id={SID}/",
                                "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                                "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
                                "SerdeInfo": {
                                    "SerializationLibrary": "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
                                },
                                "Compressed": True,
                            },
                        }
                    ],
                },
            )
        assert register_partitions(glue, "db", "b", "p/", SID) == list(TABLE_SCHEMAS)
        stub.assert_no_pending_responses()


def test_already_exists_is_success_both_forms():
    glue = _client()
    with Stubber(glue) as stub:
        tables = list(TABLE_SCHEMAS)
        stub.add_client_error("batch_create_partition", "AlreadyExistsException")
        for _ in tables[1:]:
            stub.add_response(
                "batch_create_partition",
                {"Errors": [{"PartitionValues": [SID], "ErrorDetail": {"ErrorCode": "AlreadyExistsException"}}]},
            )
        assert register_partitions(glue, "db", "b", "p", SID) == tables


def test_other_errors_raise_and_bad_id_rejected():
    glue = _client()
    with Stubber(glue) as stub:
        stub.add_client_error("batch_create_partition", "AccessDeniedException")
        with pytest.raises(PartitionRegistrationError):
            register_partitions(glue, "db", "b", "p", SID)
    with pytest.raises(ValueError):
        register_partitions(glue, "db", "b", "p", "bad id")
