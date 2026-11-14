"""Filesystem cache for immutable Dataset_Snapshot objects.

The cache is an efficiency layer only.  It never selects a snapshot or masks an
S3 error; :class:`guide.data.loader.SnapshotStore` always pins its pointer and
manifest from the Primary_Store in the Tier 2 implementation.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from guide.data.snapshot import (
    FileEntry,
    SnapshotManifest,
    SnapshotPointer,
    manifest_from_json,
    manifest_to_json,
    pointer_from_json,
    pointer_to_json,
)


class LocalCache:
    """Store snapshot metadata and checksum-addressed object bytes locally."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    @property
    def _pointer_path(self) -> Path:
        return self.root / "pointers" / "current.json"

    @property
    def _pointer_etag_path(self) -> Path:
        return self.root / "pointers" / "current.etag"

    def _manifest_path(self, snapshot_id: str) -> Path:
        return self.root / "manifests" / f"{snapshot_id}.json"

    def _object_path(self, sha256: str) -> Path:
        return self.root / "objects" / sha256

    @staticmethod
    def _write_bytes(path: Path, data: bytes) -> None:
        """Atomically replace a cache entry without exposing partial bytes."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        temporary_path.replace(path)

    def get_pointer(self) -> tuple[SnapshotPointer, str] | None:
        """Return cached pointer metadata, or ``None`` when it is incomplete."""
        try:
            return (
                pointer_from_json(self._pointer_path.read_text(encoding="utf-8")),
                self._pointer_etag_path.read_text(encoding="utf-8"),
            )
        except FileNotFoundError:
            return None

    def put_pointer(self, pointer: SnapshotPointer, etag: str) -> None:
        """Cache a pointer and the ETag returned by the Primary_Store."""
        self._write_bytes(self._pointer_path, pointer_to_json(pointer).encode("utf-8"))
        self._write_bytes(self._pointer_etag_path, etag.encode("utf-8"))

    def get_manifest(self, snapshot_id: str) -> SnapshotManifest | None:
        """Return the cached manifest for a snapshot, if present."""
        try:
            return manifest_from_json(self._manifest_path(snapshot_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def put_manifest(self, manifest: SnapshotManifest) -> None:
        """Cache a schema-valid immutable snapshot manifest."""
        path = self._manifest_path(manifest.snapshot_id)
        self._write_bytes(path, manifest_to_json(manifest).encode("utf-8"))

    def get_verified(self, entry: FileEntry) -> bytes | None:
        """Return file bytes only when their checksum matches ``entry``."""
        path = self._object_path(entry.sha256)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            return None
        if hashlib.sha256(data).hexdigest() == entry.sha256:
            return data
        path.unlink(missing_ok=True)
        return None

    def put_file(self, entry: FileEntry, data: bytes) -> None:
        """Cache verified immutable bytes using their manifest checksum as key."""
        if hashlib.sha256(data).hexdigest() != entry.sha256:
            raise ValueError(f"checksum does not match manifest for {entry.key}")
        self._write_bytes(self._object_path(entry.sha256), data)
