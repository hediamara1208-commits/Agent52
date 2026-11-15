"""Seed_Import_Job library and CLI (Req. 17.4, 18.8, 20.1 to 20.3, 20.6 to 20.9).

Builds a ``SnapshotDraft`` from the five CSV files of an input directory and hands it
to the Snapshot_Writer. It never downloads anything: no network call other than the
AWS clients passed in, and no ``yfinance`` import.

CLI: ``python -m guide.ingest.seed [--input-dir DIR] [--label TEXT] [--retrieved-at ISO]
[--dry-run] [--prefill-cache]``.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

import yaml
from botocore.exceptions import BotoCoreError, ClientError

from guide.config import load_config
from guide.data.cache import LocalCache
from guide.data.parquet_io import TABLE_SCHEMAS, read_csv_typed
from guide.data.snapshot import (
    SNAPSHOT_ID_RE,
    ManifestError,
    SnapshotManifest,
    manifest_from_json,
    pointer_from_json,
)
from guide.ingest.validate import UniverseAddition, restrict_universe, validate_tables
from guide.ingest.writer import SnapshotDraft, _key, _prefix_exists, write_snapshot

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ADDITIONS_FILE = Path(__file__).with_name("universe_additions.yaml")
DEFAULT_SOURCES_DOC = REPO_ROOT / "docs" / "data_sources.md"
DEFAULT_LABEL = "starter"
UNIVERSE_COLUMNS = ("asset_id", "ticker", "name", "asset_class", "market", "currency", "sector")
_LABEL_RE = re.compile(r"^[a-z0-9]{1,32}$")

UniverseAdditions = Sequence[UniverseAddition]


@dataclass(frozen=True)
class SeedResult:
    status: Literal["committed", "rejected", "failed", "exists", "dry_run"]
    snapshot_id: str
    in_use_snapshot_id: str  # pointer after the run; empty when no snapshot exists
    failed_step: str | None
    violations: tuple[str, ...]
    planned_keys: tuple[str, ...] = ()


# --- inputs ---------------------------------------------------------------


def load_universe_additions(path: Path | str = DEFAULT_ADDITIONS_FILE) -> tuple[UniverseAddition, ...]:
    """Read the Universe_Additions_File; an absent file or empty list means no additions."""
    p = Path(path)
    if not p.exists():
        return ()
    document = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    items = document.get("additions") or []
    names = UniverseAddition.__dataclass_fields__
    return tuple(UniverseAddition(**{n: str(item.get(n, "") or "") for n in names}) for item in items)


def retrieval_date_from_metadata(input_dir: Path) -> datetime | None:
    """Latest ``retrieved_on`` in ``sources_metadata.csv`` as midnight UTC, or None when absent."""
    path = Path(input_dir) / "sources_metadata.csv"
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as handle:
        dates = [date.fromisoformat(r["retrieved_on"].strip()) for r in csv.DictReader(handle) if (r.get("retrieved_on") or "").strip()]
    if not dates:
        return None
    d = max(dates)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def snapshot_id_for(retrieved_at: datetime, label: str) -> str:
    return f"{retrieved_at.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}-{label}"


# --- Primary_Store reads ----------------------------------------------------


def _is_missing(error: ClientError) -> bool:
    code = str(error.response.get("Error", {}).get("Code", ""))
    return code in {"NoSuchKey", "404", "NotFound"}


def _read_pointer(s3: Any, config: Any) -> tuple[Any, str] | None:
    """Current pointer and ETag, or None when no pointer exists yet."""
    try:
        response = s3.get_object(Bucket=config.s3_bucket, Key=_key(config, "pointers/current.json"))
    except ClientError as error:
        if _is_missing(error):
            return None
        raise
    return pointer_from_json(response["Body"].read().decode("utf-8")), str(response.get("ETag", "")).strip('"')


def _read_manifest(s3: Any, config: Any, snapshot_id: str) -> SnapshotManifest:
    response = s3.get_object(Bucket=config.s3_bucket, Key=_key(config, f"snapshots/{snapshot_id}/manifest.json"))
    return manifest_from_json(response["Body"].read().decode("utf-8"))


def _in_use(s3: Any, config: Any) -> str:
    try:
        found = _read_pointer(s3, config)
    except (ClientError, BotoCoreError, ManifestError, ValueError):
        return ""
    return found[0].snapshot_id if found else ""


def _carry_over(s3: Any, config: Any, missing: list[str]) -> tuple[dict[str, bytes], dict[str, str]]:
    """Raw CSV bytes of tables absent from the input directory, from the current snapshot (Req. 20.9)."""
    found = _read_pointer(s3, config)
    if found is None:
        raise LookupError("no previous snapshot to carry tables over from")
    previous = found[0].snapshot_id
    manifest = _read_manifest(s3, config, previous)
    tables: dict[str, bytes] = {}
    for table in missing:
        entry = next((f for f in manifest.files if f.table == table and f.kind == "raw_csv"), None)
        if entry is None:
            raise LookupError(f"snapshot {previous} has no raw CSV for {table}")
        kwargs: dict[str, Any] = {"Bucket": config.s3_bucket, "Key": entry.key}
        if entry.version_id and entry.version_id != "null":
            kwargs["VersionId"] = entry.version_id
        data = s3.get_object(**kwargs)["Body"].read()
        if hashlib.sha256(data).hexdigest() != entry.sha256:
            raise LookupError(f"checksum mismatch for {table} in snapshot {previous}")
        tables[table] = data
    return tables, {table: previous for table in missing}


# --- universe rule ----------------------------------------------------------


def _with_added_universe_rows(universe_csv: bytes, rows: Sequence[UniverseAddition]) -> bytes:
    """Append accepted additions that the universe CSV does not list yet."""
    if not rows:
        return universe_csv
    text = universe_csv.decode("utf-8")
    out = io.StringIO()
    out.write(text if text.endswith("\n") else text + "\n")
    writer = csv.writer(out, lineterminator="\n")
    for a in rows:
        writer.writerow([f"ADD-{a.ticker}", a.ticker, a.name, a.asset_class, a.market, a.currency, a.sector])
    return out.getvalue().encode("utf-8")


# --- job --------------------------------------------------------------------


def _library_versions() -> dict[str, str]:
    versions = {"python": ".".join(map(str, sys.version_info[:3]))}
    for name in ("pandas", "pyarrow"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:  # pragma: no cover
            versions[name] = "unknown"
    return versions


def _planned_keys(config: Any, sid: str) -> tuple[str, ...]:
    keys: list[str] = []
    for table in TABLE_SCHEMAS:
        keys.append(_key(config, f"snapshots/{sid}/raw/{table}.csv"))
        keys.append(_key(config, f"curated/{table}/snapshot_id={sid}/part-0000.parquet"))
    keys.append(_key(config, f"snapshots/{sid}/manifest.json"))
    keys.append(_key(config, "pointers/current.json"))
    return tuple(keys)


def _prefill_cache(s3: Any, config: Any, sid: str) -> None:
    """Copy pointer, manifest, and Parquet objects of ``sid`` into the Local_Cache (Req. 27.10)."""
    cache = LocalCache(Path(config.cache_dir))
    manifest = _read_manifest(s3, config, sid)
    for entry in manifest.files:
        if entry.kind != "parquet":
            continue
        kwargs: dict[str, Any] = {"Bucket": config.s3_bucket, "Key": entry.key}
        if entry.version_id and entry.version_id != "null":
            kwargs["VersionId"] = entry.version_id
        cache.put_file(entry, s3.get_object(**kwargs)["Body"].read())
    cache.put_manifest(manifest)
    found = _read_pointer(s3, config)
    if found is None or found[0].snapshot_id != sid:
        raise LookupError(f"pointer does not name {sid}")
    cache.put_pointer(found[0], found[1])


def seed_snapshot(
    config: Any,
    s3: Any,
    glue: Any,
    athena: Any,
    input_dir: Path | str | None = None,
    label: str = DEFAULT_LABEL,
    retrieved_at: datetime | None = None,
    additions: UniverseAdditions | None = None,
    dry_run: bool = False,
    prefill_cache: bool = False,
    data_sources_doc: str | None = None,
) -> SeedResult:
    """Build a Dataset_Snapshot from CSV files and commit it through the Snapshot_Writer."""
    directory = Path(input_dir if input_dir is not None else config.seed_dir)
    if not _LABEL_RE.fullmatch(label or ""):
        return SeedResult("rejected", "", _in_use(s3, config), "input", (f"invalid label: {label!r}",))
    stamp = retrieved_at or retrieval_date_from_metadata(directory)
    if stamp is None:
        return SeedResult("rejected", "", _in_use(s3, config), "input", ("no retrieval date: sources_metadata.csv is absent and --retrieved-at was not given",))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    sid = snapshot_id_for(stamp, label)
    if not SNAPSHOT_ID_RE.fullmatch(sid):
        return SeedResult("rejected", sid, _in_use(s3, config), "input", (f"invalid snapshot id: {sid!r}",))

    def finish(status: str, step: str | None, violations: tuple[str, ...], planned: tuple[str, ...] = ()) -> SeedResult:
        return SeedResult(status, sid, _in_use(s3, config), step, violations, planned)  # type: ignore[arg-type]

    # 1. Read the CSV files; tables without a file are carried over (step 3)
    tables: dict[str, bytes] = {}
    missing: list[str] = []
    for table in TABLE_SCHEMAS:
        path = directory / f"{table}.csv"
        if path.is_file():
            tables[table] = path.read_bytes()
        else:
            missing.append(table)
    carried: dict[str, str] = {}
    if missing:
        try:
            extra, carried = _carry_over(s3, config, missing)
        except LookupError as error:
            return finish("rejected", "input", (f"missing input files {', '.join(m + '.csv' for m in missing)}: {error}",))
        except (ClientError, BotoCoreError, ManifestError, ValueError) as error:
            return finish("failed", "carry_over", (str(error),))
        tables.update(extra)

    # 2. Universe rule (Req. 20.8)
    try:
        frames = {t: read_csv_typed(t, tables[t]) for t in TABLE_SCHEMAS}
    except Exception as error:
        return finish("rejected", "python_validation", (f"table cannot be read: {error}",))
    universe_tickers = [str(t) for t in frames["assets_universe"]["ticker"]]
    requested = [str(t) for t in frames["prices_daily"]["ticker"].unique()]
    if data_sources_doc is None:
        data_sources_doc = DEFAULT_SOURCES_DOC.read_text(encoding="utf-8") if DEFAULT_SOURCES_DOC.exists() else ""
    restriction = restrict_universe(requested, universe_tickers, additions, data_sources_doc)
    if restriction.rejected:
        return finish("rejected", "universe_restriction", restriction.violations)
    used = [a for a in (additions or ()) if a.ticker in restriction.accepted and a.ticker not in universe_tickers]
    if used:
        tables["assets_universe"] = _with_added_universe_rows(tables["assets_universe"], used)
        frames["assets_universe"] = read_csv_typed("assets_universe", tables["assets_universe"])

    # 4. Python validation (Req. 20.6, 20.7): nothing is written on a violation
    violations = validate_tables(frames["prices_daily"], frames["assets_universe"])
    if violations:
        return finish("rejected", "python_validation", violations)

    # 5. Immutability: stop when the Snapshot_Id exists (Req. 18.10)
    try:
        if _prefix_exists(s3, config, sid):
            return finish("exists", None, ())
    except (ClientError, BotoCoreError) as error:
        return finish("failed", "write", (str(error),))

    if dry_run:
        return finish("dry_run", None, (), _planned_keys(config, sid))

    # 6. Write
    draft = SnapshotDraft(
        snapshot_id=sid,
        source="addition" if used else "starter",
        retrieved_at=stamp,
        tables=tables,
        carried_over=carried,
        library_versions=_library_versions(),
    )
    written = write_snapshot(draft, s3, glue, athena, config)
    if written.status != "committed":
        return finish(written.status, written.failed_step, written.violations)
    if prefill_cache:
        try:
            _prefill_cache(s3, config, sid)
        except Exception as error:  # the snapshot is committed; report the cache problem
            return SeedResult("committed", sid, sid, "prefill_cache", (str(error),))
    return SeedResult("committed", sid, sid, None, ())


# --- CLI --------------------------------------------------------------------


def _parse_retrieved_at(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m guide.ingest.seed",
        description="Seed_Import_Job: build a Dataset_Snapshot from local CSV files. Downloads nothing.",
    )
    parser.add_argument("--input-dir", default=None, help="directory with the CSV files (default: seed_dir)")
    parser.add_argument("--label", default=DEFAULT_LABEL, help="source label of the Snapshot_Id")
    parser.add_argument("--retrieved-at", default=None, help="ISO retrieval timestamp (default: sources_metadata.csv)")
    parser.add_argument("--dry-run", action="store_true", help="validate and print planned keys; write nothing")
    parser.add_argument("--prefill-cache", action="store_true", help="copy the committed snapshot into the Local_Cache")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    import boto3  # imported here so the library stays importable without AWS setup

    config = load_config()
    region = config.aws_region
    result = seed_snapshot(
        config,
        boto3.client("s3", region_name=region),
        boto3.client("glue", region_name=region),
        boto3.client("athena", region_name=region),
        input_dir=args.input_dir,
        label=args.label,
        retrieved_at=_parse_retrieved_at(args.retrieved_at) if args.retrieved_at else None,
        additions=load_universe_additions(),
        dry_run=args.dry_run,
        prefill_cache=args.prefill_cache,
    )
    print(json.dumps(asdict(result), indent=2))
    ok = result.status in {"committed", "exists", "dry_run"} and result.failed_step is None
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
