"""S3-primary Dataset_Snapshot reads for the Tier 2 data architecture.

A ``SnapshotStore`` pins one pointer and manifest for a session.  The matching
``PinnedSnapshot`` reads only manifest-listed Parquet files, using a verified
local cache to avoid repeated downloads.  Tier 2 intentionally does not use
conditional requests, S3 VersionId reads, or cache fallback.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

import pandas as pd
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from guide.config import Config
from guide.data.cache import LocalCache
from guide.data.parquet_io import read_parquet
from guide.data.snapshot import FileEntry, SnapshotInfo, SnapshotManifest, pointer_from_json, manifest_from_json


class DataConfigError(RuntimeError):
    """The application cannot read a Primary_Store resource due to configuration."""

    def __init__(self, resource: str) -> None:
        self.resource = resource
        super().__init__(f"access denied for data resource: {resource}")


class DatasetUnavailable(RuntimeError):
    """The Primary_Store cannot provide a required Dataset_Snapshot resource."""

    def __init__(self, location: str) -> None:
        self.location = location
        super().__init__(f"dataset unavailable: {location}")


class DataIntegrityError(RuntimeError):
    """A file did not match the SHA-256 checksum declared in its manifest."""

    def __init__(self, file: str) -> None:
        self.file = file
        super().__init__(f"data integrity error for file: {file}")


class DataSource(Protocol):
    """The Toolkit's read-only view of one pinned Dataset_Snapshot."""

    snapshot: SnapshotInfo

    def read_table(self, table: str) -> pd.DataFrame: ...


class LocalSource:
    """Read starter CSV files for tests and the seed operation only."""

    def __init__(self, data_dir: str | Path = "/workshop/Agent52/data") -> None:
        self.data_dir = Path(data_dir)

    def read_csv(self, name: str) -> pd.DataFrame:
        return pd.read_csv(self.data_dir / name)


class SnapshotStore:
    """Resolve exactly one S3 snapshot pointer and manifest per session."""

    def __init__(self, config: Config, s3_client=None, cache: LocalCache | None = None) -> None:
        self._config = config
        self._bucket = config.s3_bucket
        self._prefix = config.s3_prefix.strip("/")
        self._cache = cache or LocalCache(Path(config.cache_dir))
        if s3_client is None:
            import boto3

            s3_client = boto3.client(
                "s3",
                region_name=config.aws_region,
                config=BotoConfig(
                    connect_timeout=config.s3_connect_timeout_seconds,
                    read_timeout=config.s3_read_timeout_seconds,
                    retries={"total_max_attempts": config.s3_max_attempts, "mode": "standard"},
                ),
            )
        self._s3 = s3_client

    def _key(self, suffix: str) -> str:
        return f"{self._prefix}/{suffix}" if self._prefix else suffix

    def _location(self, key: str) -> str:
        return f"s3://{self._bucket}/{key}"

    @staticmethod
    def _is_access_denied(error: Exception) -> bool:
        if not isinstance(error, ClientError):
            return False
        payload = error.response.get("Error", {})
        code = str(payload.get("Code", ""))
        status = payload.get("HTTPStatusCode")
        return code in {"AccessDenied", "InvalidAccessKeyId"} or status == 403

    def _get_bytes(self, key: str) -> tuple[bytes, str]:
        """Read one S3 object, mapping only S3 failures to public data errors."""
        location = self._location(key)
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=key)
            body = response["Body"]
            try:
                data = body.read()
            finally:
                body.close()
            return data, str(response.get("ETag", ""))
        except (ClientError, BotoCoreError, OSError) as error:
            if self._is_access_denied(error):
                raise DataConfigError(location) from error
            raise DatasetUnavailable(location) from error

    def pin(self) -> "PinnedSnapshot":
        """Read the current pointer and its manifest once, then pin their snapshot."""
        pointer_key = self._key("pointers/current.json")
        pointer_bytes, pointer_etag = self._get_bytes(pointer_key)
        pointer = pointer_from_json(pointer_bytes.decode("utf-8"))
        self._cache.put_pointer(pointer, pointer_etag)

        manifest_key = self._key(f"snapshots/{pointer.snapshot_id}/manifest.json")
        manifest_bytes, _ = self._get_bytes(manifest_key)
        manifest = manifest_from_json(manifest_bytes.decode("utf-8"))
        if manifest.snapshot_id != pointer.snapshot_id:
            raise DatasetUnavailable(self._location(manifest_key))
        self._cache.put_manifest(manifest)

        snapshot = SnapshotInfo(
            snapshot_id=manifest.snapshot_id,
            source=manifest.source,
            retrieved_at=manifest.retrieved_at,
            coverage_end=manifest.coverage_end,
            served_from="primary",
            fallback_cause=None,
        )
        return PinnedSnapshot(snapshot, manifest, self._s3, self._bucket, self._cache)


class PinnedSnapshot:
    """Read only the Parquet files listed by one immutable pinned manifest."""

    def __init__(
        self,
        snapshot: SnapshotInfo,
        manifest: SnapshotManifest,
        s3_client,
        bucket: str,
        cache: LocalCache,
    ) -> None:
        self.snapshot = snapshot
        self.manifest = manifest
        self._s3 = s3_client
        self._bucket = bucket
        self._cache = cache

    def _entry_for(self, table: str) -> FileEntry:
        matches = [entry for entry in self.manifest.files if entry.table == table and entry.kind == "parquet"]
        if len(matches) != 1:
            raise ValueError(f"manifest must list exactly one Parquet file for table: {table}")
        return matches[0]

    def _download(self, entry: FileEntry) -> bytes:
        location = f"s3://{self._bucket}/{entry.key}"
        try:
            response = self._s3.get_object(Bucket=self._bucket, Key=entry.key)
            body = response["Body"]
            try:
                return body.read()
            finally:
                body.close()
        except (ClientError, BotoCoreError, OSError) as error:
            if SnapshotStore._is_access_denied(error):
                raise DataConfigError(location) from error
            raise DatasetUnavailable(location) from error

    def _read_verified_bytes(self, entry: FileEntry) -> bytes:
        cached = self._cache.get_verified(entry)
        if cached is not None:
            return cached

        for _attempt in range(2):
            data = self._download(entry)
            if hashlib.sha256(data).hexdigest() == entry.sha256:
                self._cache.put_file(entry, data)
                return data
        raise DataIntegrityError(entry.key)

    def read_table(self, table: str) -> pd.DataFrame:
        """Read a manifest-listed Parquet table after checksum verification."""
        entry = self._entry_for(table)
        return read_parquet(table, self._read_verified_bytes(entry))
