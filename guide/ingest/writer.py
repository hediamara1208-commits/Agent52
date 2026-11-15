"""Snapshot_Writer, Tier 2 lean (Req. 18.1, 18.5, 18.6, 19.2, 20.6, 20.7).

Order of steps: Python validation, snapshot-prefix check, raw CSV and Parquet
objects (SHA-256 and VersionId collected), Glue partitions, Athena row-count and
duplicate queries (``skipped`` when Athena is unavailable), manifest, and the
current-snapshot pointer last. The pointer changes only at the last step, so a
failure anywhere earlier leaves the previous snapshot in use.

The full version (``IfNoneMatch`` writes, ``IfMatch`` on the pointer, and the
Athena/Python disagreement gate) is task 12.25. Here Athena results are
recorded in the manifest but do not gate the commit.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Literal

from botocore.exceptions import BotoCoreError, ClientError

from athena.queries import build_query, run_query
from guide.data.catalog import register_partitions
from guide.data.parquet_io import TABLE_SCHEMAS, csv_to_parquet, read_csv_typed
from guide.data.snapshot import (
    SNAPSHOT_ID_RE,
    FileEntry,
    ManifestError,
    SnapshotManifest,
    SnapshotPointer,
    manifest_to_json,
    pointer_to_json,
)
from guide.ingest.validate import validate_tables

JSON_CONTENT_TYPE = "application/json"


@dataclass(frozen=True)
class SnapshotDraft:
    snapshot_id: str
    source: Literal["starter", "addition"]
    retrieved_at: datetime
    tables: Mapping[str, bytes]  # table -> raw CSV bytes (carried-over tables included)
    carried_over: Mapping[str, str]
    library_versions: Mapping[str, str]


@dataclass(frozen=True)
class WriteResult:
    status: Literal["committed", "rejected", "failed"]
    snapshot_id: str
    failed_step: str | None  # python_validation | write | glue | athena_validation | manifest | pointer
    violations: tuple[str, ...]


def _key(config: Any, suffix: str) -> str:
    prefix = config.s3_prefix.strip("/")
    return f"{prefix}/{suffix}" if prefix else suffix


def _failed(draft: SnapshotDraft, step: str, message: str) -> WriteResult:
    return WriteResult("failed", draft.snapshot_id, step, (message,))


def _rejected(draft: SnapshotDraft, step: str, violations: tuple[str, ...]) -> WriteResult:
    return WriteResult("rejected", draft.snapshot_id, step, violations)


def _prefix_exists(s3: Any, config: Any, snapshot_id: str) -> bool:
    response = s3.list_objects_v2(
        Bucket=config.s3_bucket, Prefix=_key(config, f"snapshots/{snapshot_id}/"), MaxKeys=1
    )
    return bool(response.get("Contents")) or int(response.get("KeyCount", 0) or 0) > 0


def _put(s3: Any, config: Any, key: str, body: bytes, content_type: str | None = None) -> str:
    kwargs: dict[str, Any] = {"Bucket": config.s3_bucket, "Key": key, "Body": body}
    if content_type:
        kwargs["ContentType"] = content_type
    response = s3.put_object(**kwargs)
    return str(response.get("VersionId") or "null")


def _athena_validation(athena: Any, config: Any, snapshot_id: str, python_rows: Mapping[str, int]) -> dict[str, Any]:
    """Row counts and duplicates from Athena; ``skipped`` when Athena is unavailable (Req. 19.4)."""
    try:
        row_counts: dict[str, int] = {}
        duplicates = 0
        for table in TABLE_SCHEMAS:
            rows = run_query(athena, build_query(f"check_row_count_{table}", snapshot_id), config)
            row_counts[table] = int(rows[0]["row_count"]) if rows else 0
            rows = run_query(athena, build_query(f"check_duplicates_{table}", snapshot_id), config)
            duplicates += int(rows[0]["duplicate_keys"]) if rows else 0
    except Exception as error:  # unavailable, timed out, or malformed: recorded, never blocks (Req. 19.4)
        return {"status": "skipped", "reason": type(error).__name__}
    agrees = duplicates == 0 and row_counts == dict(python_rows)
    return {
        "status": "pass" if agrees else "mismatch",
        "row_counts": row_counts,
        "duplicates": duplicates,
    }


def write_snapshot(draft: SnapshotDraft, s3: Any, glue: Any, athena: Any, config: Any) -> WriteResult:
    """Write one immutable Dataset_Snapshot and move the pointer last."""
    sid = draft.snapshot_id
    if not isinstance(sid, str) or not SNAPSHOT_ID_RE.fullmatch(sid):
        return _rejected(draft, "python_validation", (f"invalid snapshot id: {sid!r}",))

    # 1. Python validation (Req. 20.6, 20.7)
    missing = [t for t in TABLE_SCHEMAS if t not in draft.tables]
    if missing:
        return _rejected(draft, "python_validation", (f"missing tables: {', '.join(missing)}",))
    try:
        frames = {t: read_csv_typed(t, bytes(draft.tables[t])) for t in TABLE_SCHEMAS}
        parquet = {t: csv_to_parquet(t, bytes(draft.tables[t])) for t in TABLE_SCHEMAS}
    except Exception as error:
        return _rejected(draft, "python_validation", (f"table cannot be read: {error}",))
    violations = validate_tables(frames["prices_daily"], frames["assets_universe"])
    if violations:
        return _rejected(draft, "python_validation", violations)
    prices = frames["prices_daily"]
    if prices.empty:
        return _rejected(draft, "python_validation", ("prices_daily has no rows",))

    # 2. Immutability: refuse an existing Snapshot_Id prefix (Req. 18.6)
    try:
        if _prefix_exists(s3, config, sid):
            return _rejected(draft, "write", (f"snapshot {sid} already exists",))
    except (ClientError, BotoCoreError) as error:
        return _failed(draft, "write", str(error))

    # 3. Raw CSV and Parquet objects
    files: list[FileEntry] = []
    try:
        for table in TABLE_SCHEMAS:
            rows = len(frames[table])
            for kind, key, body in (
                ("raw_csv", _key(config, f"snapshots/{sid}/raw/{table}.csv"), bytes(draft.tables[table])),
                ("parquet", _key(config, f"curated/{table}/snapshot_id={sid}/part-0000.parquet"), parquet[table]),
            ):
                version_id = _put(s3, config, key, body)
                files.append(FileEntry(table, kind, key, version_id, hashlib.sha256(body).hexdigest(), rows))  # type: ignore[arg-type]
    except (ClientError, BotoCoreError) as error:
        return _failed(draft, "write", str(error))

    # 4. Glue partitions (Req. 18.5)
    try:
        register_partitions(glue, config.glue_database, config.s3_bucket, config.s3_prefix, sid)
    except Exception as error:
        return _failed(draft, "glue", str(error))

    # 5. Athena validation, recorded; skipped when unavailable (Req. 19.2, 19.4)
    python_rows = {t: len(frames[t]) for t in TABLE_SCHEMAS}
    athena_result = _athena_validation(athena, config, sid, python_rows)

    # 6. Manifest
    manifest = SnapshotManifest(
        schema_version=1,
        snapshot_id=sid,
        source=draft.source,
        retrieved_at=draft.retrieved_at,
        library_versions=dict(draft.library_versions),
        coverage_start=_as_date(prices["date"].min()),
        coverage_end=_as_date(prices["date"].max()),
        tickers=tuple(sorted(set(map(str, frames["assets_universe"]["ticker"])))),
        files=tuple(files),
        carried_over=dict(draft.carried_over),
        validation={
            "python": {"status": "pass", "violations": []},
            "athena": athena_result,
        },
    )
    try:
        manifest_json = manifest_to_json(manifest)
        _put(s3, config, _key(config, f"snapshots/{sid}/manifest.json"), manifest_json.encode("utf-8"), JSON_CONTENT_TYPE)
    except (ClientError, BotoCoreError, ManifestError, ValueError) as error:
        return _failed(draft, "manifest", str(error))

    # 7. Pointer last
    try:
        pointer = SnapshotPointer(sid, datetime.now(timezone.utc))
        _put(s3, config, _key(config, "pointers/current.json"), pointer_to_json(pointer).encode("utf-8"), JSON_CONTENT_TYPE)
    except (ClientError, BotoCoreError, ValueError) as error:
        return _failed(draft, "pointer", str(error))

    return WriteResult("committed", sid, None, ())


def _as_date(value: Any) -> date:
    return value.date() if hasattr(value, "date") and callable(value.date) else value
