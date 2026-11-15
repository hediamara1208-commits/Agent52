from datetime import datetime, timezone
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from guide.config import Config
from guide.data.parquet_io import TABLE_SCHEMAS
from guide.data.snapshot import manifest_from_json, pointer_from_json
from guide.ingest.writer import SnapshotDraft, write_snapshot

DATA = Path(__file__).resolve().parents[1] / "data"
SID = "20261113T000000Z-starter"


class FakeS3:
    """In-memory stand-in for the S3 calls the writer makes."""

    def __init__(self, fail_key: str | None = None):
        self.objects: dict[str, bytes] = {}
        self.puts: list[str] = []
        self.fail_key = fail_key

    def list_objects_v2(self, Bucket, Prefix, MaxKeys=1000):
        hits = [k for k in self.objects if k.startswith(Prefix)]
        return {"KeyCount": len(hits), "Contents": [{"Key": k} for k in hits[:MaxKeys]]}

    def put_object(self, Bucket, Key, Body, **kw):
        if self.fail_key and self.fail_key in Key:
            raise ClientError({"Error": {"Code": "InternalError", "Message": "boom"}}, "PutObject")
        self.objects[Key] = Body
        self.puts.append(Key)
        return {"VersionId": f"v{len(self.puts)}"}


class FakeGlue:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = 0

    def batch_create_partition(self, **kw):
        self.calls += 1
        if self.fail:
            raise ClientError({"Error": {"Code": "InternalServiceException", "Message": "x"}}, "BatchCreatePartition")
        return {"Errors": []}


class DownAthena:
    def start_query_execution(self, **kw):
        raise ClientError({"Error": {"Code": "ServiceUnavailable", "Message": "x"}}, "StartQueryExecution")


@pytest.fixture
def config():
    return Config(s3_bucket="b", s3_prefix="dataset")


def _draft(tables=None):
    t = tables or {name: (DATA / f"{name}.csv").read_bytes() for name in TABLE_SCHEMAS}
    return SnapshotDraft(
        snapshot_id=SID,
        source="starter",
        retrieved_at=datetime(2026, 11, 13, tzinfo=timezone.utc),
        tables=t,
        carried_over={},
        library_versions={"pyarrow": "x"},
    )


def test_commit_writes_objects_manifest_and_pointer_last(config):
    s3 = FakeS3()
    result = write_snapshot(_draft(), s3, FakeGlue(), DownAthena(), config)
    assert result.status == "committed" and result.failed_step is None
    assert s3.puts[-1] == "dataset/pointers/current.json"
    assert s3.puts[-2] == f"dataset/snapshots/{SID}/manifest.json"
    assert pointer_from_json(s3.objects["dataset/pointers/current.json"].decode()).snapshot_id == SID
    manifest = manifest_from_json(s3.objects[f"dataset/snapshots/{SID}/manifest.json"].decode())
    assert len(manifest.files) == 10
    assert manifest.validation["athena"]["status"] == "skipped"
    assert all(len(f.sha256) == 64 for f in manifest.files)


def test_existing_prefix_is_refused_and_untouched(config):
    s3 = FakeS3()
    s3.objects[f"dataset/snapshots/{SID}/manifest.json"] = b"old"
    result = write_snapshot(_draft(), s3, FakeGlue(), DownAthena(), config)
    assert result.status == "rejected"
    assert s3.puts == [] and s3.objects[f"dataset/snapshots/{SID}/manifest.json"] == b"old"


def test_invalid_data_is_rejected_before_any_write(config):
    tables = {name: (DATA / f"{name}.csv").read_bytes() for name in TABLE_SCHEMAS}
    lines = tables["prices_daily"].decode().splitlines()
    tables["prices_daily"] = "\n".join(lines + [lines[1]]).encode()  # duplicate row
    s3 = FakeS3()
    result = write_snapshot(_draft(tables), s3, FakeGlue(), DownAthena(), config)
    assert result.status == "rejected" and result.failed_step == "python_validation"
    assert any("duplicate" in v for v in result.violations)
    assert s3.puts == []


@pytest.mark.parametrize(
    "s3_fail, glue_fail, step",
    [("manifest.json", False, "manifest"), ("pointers/", False, "pointer"), ("raw/prices_daily", False, "write"), (None, True, "glue")],
)
def test_failures_never_move_the_pointer(config, s3_fail, glue_fail, step):
    s3 = FakeS3(fail_key=s3_fail)
    result = write_snapshot(_draft(), s3, FakeGlue(fail=glue_fail), DownAthena(), config)
    assert result.status == "failed" and result.failed_step == step
    if step != "pointer":
        assert "dataset/pointers/current.json" not in s3.objects
