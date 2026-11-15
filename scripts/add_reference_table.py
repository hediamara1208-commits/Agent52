"""Add a hand-authored reference table (e.g. esg_exclusions) to a new immutable Dataset_Snapshot.

The new snapshot reuses every file of the current snapshot (listed in ``carried_over``),
adds the reference table as raw CSV + Parquet with SHA-256 checksums, and then moves
``pointers/current.json``. No market data is downloaded or changed.

Usage (CloudShell or any machine with boto3 + pyarrow):
    python scripts/add_reference_table.py --bucket alphaforge-guide-data --csv data/esg_exclusions.csv
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq


def to_parquet(data: bytes, columns: list[str]) -> tuple[bytes, int]:
    table = pacsv.read_csv(io.BytesIO(data), convert_options=pacsv.ConvertOptions(
        column_types={c: pa.string() for c in columns}, strings_can_be_null=False))
    out = pa.BufferOutputStream()
    pq.write_table(table, out, compression="snappy", write_statistics=False)
    return out.getvalue().to_pybytes(), table.num_rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--prefix", default="dataset")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--table", default=None)
    ap.add_argument("--label", default="esg")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s3 = boto3.client("s3")
    path = Path(args.csv)
    table = args.table or path.stem
    raw = path.read_bytes()
    columns = raw.split(b"\n", 1)[0].decode().strip().split(",")
    parquet, rows = to_parquet(raw, columns)

    def get(key: str) -> dict:
        return json.loads(s3.get_object(Bucket=args.bucket, Key=f"{args.prefix}/{key}")["Body"].read())

    pointer = get("pointers/current.json")
    old = pointer["snapshot_id"]
    manifest = get(f"snapshots/{old}/manifest.json")
    if any(f["table"] == table for f in manifest["files"]):
        raise SystemExit(f"{table} is already in snapshot {old}")
    now = datetime.now(timezone.utc)
    new = f"{now:%Y%m%dT%H%M%SZ}-{args.label}"
    sample = next(f for f in manifest["files"] if f["kind"] == "parquet")
    raw_sample = next(f for f in manifest["files"] if f["kind"] == "raw_csv")

    def key_like(entry: dict) -> str:
        return entry["key"].replace(old, new).replace(entry["table"], table)

    entries = []
    for kind, body, like in (("raw_csv", raw, raw_sample), ("parquet", parquet, sample)):
        key = key_like(like)
        version = "dry-run"
        if not args.dry_run:
            version = s3.put_object(Bucket=args.bucket, Key=key, Body=body).get("VersionId") or "null"
        entries.append({"table": table, "kind": kind, "key": key, "version_id": version,
                        "sha256": hashlib.sha256(body).hexdigest(), "rows": rows})
    carried = dict(manifest.get("carried_over") or {})
    for f in manifest["files"]:
        carried.setdefault(f["table"], old)
    manifest.update(snapshot_id=new, source="addition", files=manifest["files"] + entries,
                    carried_over=carried)
    new_pointer = {**pointer, "snapshot_id": new, "updated_at": now.isoformat().replace("+00:00", "Z")}
    print(json.dumps({"old": old, "new": new, "added": entries}, indent=1))
    if args.dry_run:
        return
    s3.put_object(Bucket=args.bucket, Key=f"{args.prefix}/snapshots/{new}/manifest.json",
                  Body=json.dumps(manifest, indent=1).encode())
    s3.put_object(Bucket=args.bucket, Key=f"{args.prefix}/pointers/current.json",
                  Body=json.dumps(new_pointer).encode())
    print("pointer ->", new)


if __name__ == "__main__":
    main()
