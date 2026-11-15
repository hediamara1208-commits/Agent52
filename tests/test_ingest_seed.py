import io
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from guide.config import Config
from guide.data.cache import LocalCache
from guide.data.parquet_io import TABLE_SCHEMAS
from guide.ingest.seed import (
    load_universe_additions,
    main,
    retrieval_date_from_metadata,
    seed_snapshot,
)
from tests.test_ingest_writer import DownAthena, FakeGlue

DATA = Path(__file__).resolve().parents[1] / "data"
SID = "20261113T000000Z-starter"


class FakeS3:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.puts: list[str] = []

    def list_objects_v2(self, Bucket, Prefix, MaxKeys=1000):
        hits = [k for k in self.objects if k.startswith(Prefix)]
        return {"KeyCount": len(hits), "Contents": [{"Key": k} for k in hits[:MaxKeys]]}

    def put_object(self, Bucket, Key, Body, **kw):
        self.objects[Key] = Body
        self.puts.append(Key)
        return {"VersionId": f"v{len(self.puts)}"}

    def get_object(self, Bucket, Key, VersionId=None):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "x"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key]), "ETag": '"etag1"'}


@pytest.fixture
def config(tmp_path):
    return Config(s3_bucket="b", s3_prefix="dataset", cache_dir=str(tmp_path / "cache"))


def _run(config, s3, **kw):
    return seed_snapshot(config, s3, FakeGlue(), DownAthena(), input_dir=DATA, **kw)


def test_baseline_commit_dry_run_exists_and_prefill(config):
    s3 = FakeS3()
    assert retrieval_date_from_metadata(DATA) == datetime(2026, 11, 13, tzinfo=timezone.utc)

    dry = _run(config, s3, dry_run=True)
    assert dry.status == "dry_run" and dry.snapshot_id == SID and not s3.puts
    assert dry.planned_keys[-1] == "dataset/pointers/current.json" and len(dry.planned_keys) == 12

    done = _run(config, s3, prefill_cache=True)
    assert done.status == "committed" and done.in_use_snapshot_id == SID and done.failed_step is None
    cache = LocalCache(Path(config.cache_dir))
    manifest = cache.get_manifest(SID)
    assert cache.get_pointer()[0].snapshot_id == SID
    assert all(cache.get_verified(f) for f in manifest.files if f.kind == "parquet")

    before = list(s3.puts)
    again = _run(config, s3)
    assert again.status == "exists" and again.in_use_snapshot_id == SID and s3.puts == before


def test_unknown_ticker_is_rejected_and_named(config, tmp_path):
    src = tmp_path / "in"
    shutil.copytree(DATA, src)
    prices = src / "prices_daily.csv"
    prices.write_text(prices.read_text() + "2026-11-12,ZZZZ,1,1,1,1,1,1,USD\n")
    s3 = FakeS3()
    result = seed_snapshot(config, s3, FakeGlue(), DownAthena(), input_dir=src)
    assert result.status == "rejected" and any("ZZZZ" in v for v in result.violations)
    assert not s3.puts


def test_missing_table_carried_over_from_current_snapshot(config, tmp_path):
    s3 = FakeS3()
    assert _run(config, s3).status == "committed"
    src = tmp_path / "in"
    shutil.copytree(DATA, src)
    (src / "macro_rates.csv").unlink()
    result = seed_snapshot(config, s3, FakeGlue(), DownAthena(), input_dir=src, label="second")
    assert result.status == "committed", result
    manifest = json.loads(s3.objects[f"dataset/snapshots/{result.snapshot_id}/manifest.json"])
    assert manifest["carried_over"] == {"macro_rates": SID}


def test_missing_table_without_previous_snapshot_is_rejected(config, tmp_path):
    src = tmp_path / "in"
    shutil.copytree(DATA, src)
    (src / "macro_rates.csv").unlink()
    result = seed_snapshot(config, FakeS3(), FakeGlue(), DownAthena(), input_dir=src)
    assert result.status == "rejected" and "macro_rates.csv" in result.violations[0]


def test_additions_file_empty_by_default_and_cli_has_no_download_option():
    assert load_universe_additions() == ()
    from guide.ingest.seed import build_parser

    flags = {a for act in build_parser()._actions for a in act.option_strings}
    assert flags >= {"--input-dir", "--label", "--retrieved-at", "--dry-run", "--prefill-cache"}
    assert not any("download" in f for f in flags)
    source = (Path(__file__).resolve().parents[1] / "guide/ingest/seed.py").read_text()
    assert "import yfinance" not in source and "requests" not in source and "urllib" not in source
    assert callable(main) and set(TABLE_SCHEMAS)
