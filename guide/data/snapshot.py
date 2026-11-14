"""Immutable Dataset_Snapshot models and schema-validated JSON conversion.

Requirements 17.14 through 17.16 require manifests and current-snapshot pointers
in the Primary_Store to be validated JSON documents.  This module provides the
canonical, deterministic representation used by the writer and loader.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator, FormatChecker

SNAPSHOT_ID_RE = re.compile(r"^\d{8}T\d{6}Z-[a-z0-9]{1,32}$")

_MANIFEST_SCHEMA_PATH = Path(__file__).with_name("manifest.schema.json")
_POINTER_SCHEMA_PATH = Path(__file__).with_name("pointer.schema.json")


class ManifestError(ValueError):
    """A manifest or pointer cannot be used because named fields are invalid."""

    def __init__(self, fields: list[str] | tuple[str, ...]) -> None:
        self.fields = tuple(fields)
        super().__init__(f"invalid snapshot document fields: {', '.join(self.fields)}")


@dataclass(frozen=True)
class FileEntry:
    table: str
    kind: Literal["raw_csv", "parquet"]
    key: str
    version_id: str
    sha256: str
    rows: int


@dataclass(frozen=True)
class SnapshotManifest:
    schema_version: int
    snapshot_id: str
    source: Literal["starter", "addition"]
    retrieved_at: datetime
    library_versions: Mapping[str, str]
    coverage_start: date
    coverage_end: date
    tickers: tuple[str, ...]
    files: tuple[FileEntry, ...]
    carried_over: Mapping[str, str]
    validation: Mapping[str, Any]


@dataclass(frozen=True)
class SnapshotPointer:
    snapshot_id: str
    updated_at: datetime


@dataclass(frozen=True)
class SnapshotInfo:
    """The snapshot pinned for one session and named by every Exhibit."""

    snapshot_id: str
    source: str
    retrieved_at: datetime
    coverage_end: date
    served_from: Literal["primary", "cache", "cache_fallback"]
    fallback_cause: str | None


def _to_iso_datetime(value: datetime) -> str:
    """Return the canonical UTC ISO 8601 representation used in JSON."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must include a UTC offset")
    utc_value = value.astimezone(timezone.utc)
    return utc_value.isoformat().replace("+00:00", "Z")


def _from_iso_datetime(value: str) -> datetime:
    """Parse a JSON datetime and normalize it to an aware UTC value."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("not an ISO 8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _field_name(error: Any, root: str) -> str:
    path = [str(part) for part in error.absolute_path]
    if error.validator == "required":
        missing = re.search(r"'([^']+)' is a required property", error.message)
        if missing:
            path.append(missing.group(1))
    elif error.validator == "additionalProperties":
        unexpected = re.search(r"'([^']+)' was unexpected", error.message)
        if unexpected:
            path.append(unexpected.group(1))
    return ".".join(path) if path else root


@lru_cache(maxsize=None)
def _validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _parse_and_validate(value: str, schema_path: Path, root: str) -> dict[str, Any]:
    try:
        document = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        raise ManifestError((root,)) from None
    if not isinstance(document, dict):
        raise ManifestError((root,))

    errors = sorted(
        _validator(schema_path).iter_errors(document),
        key=lambda error: (list(map(str, error.absolute_path)), error.message),
    )
    if errors:
        fields = tuple(dict.fromkeys(_field_name(error, root) for error in errors))
        raise ManifestError(fields)
    return document


def _manifest_to_document(manifest: SnapshotManifest) -> dict[str, Any]:
    return {
        "schema_version": manifest.schema_version,
        "snapshot_id": manifest.snapshot_id,
        "source": manifest.source,
        "retrieved_at": _to_iso_datetime(manifest.retrieved_at),
        "library_versions": dict(manifest.library_versions),
        "coverage_start": manifest.coverage_start.isoformat(),
        "coverage_end": manifest.coverage_end.isoformat(),
        "tickers": list(manifest.tickers),
        "files": [
            {
                "table": entry.table,
                "kind": entry.kind,
                "key": entry.key,
                "version_id": entry.version_id,
                "sha256": entry.sha256,
                "rows": entry.rows,
            }
            for entry in manifest.files
        ],
        "carried_over": dict(manifest.carried_over),
        "validation": dict(manifest.validation),
    }


def manifest_to_json(manifest: SnapshotManifest) -> str:
    """Serialize a schema-valid manifest deterministically with sorted keys and ISO dates."""
    serialized = json.dumps(_manifest_to_document(manifest), sort_keys=True, separators=(",", ":"))
    _parse_and_validate(serialized, _MANIFEST_SCHEMA_PATH, "<manifest>")
    return serialized


def manifest_from_json(value: str) -> SnapshotManifest:
    """Validate and parse a manifest, reporting all schema-invalid field paths."""
    document = _parse_and_validate(value, _MANIFEST_SCHEMA_PATH, "<manifest>")
    try:
        return SnapshotManifest(
            schema_version=document["schema_version"],
            snapshot_id=document["snapshot_id"],
            source=document["source"],
            retrieved_at=_from_iso_datetime(document["retrieved_at"]),
            library_versions=dict(document["library_versions"]),
            coverage_start=date.fromisoformat(document["coverage_start"]),
            coverage_end=date.fromisoformat(document["coverage_end"]),
            tickers=tuple(document["tickers"]),
            files=tuple(FileEntry(**entry) for entry in document["files"]),
            carried_over=dict(document["carried_over"]),
            validation=dict(document["validation"]),
        )
    except (TypeError, ValueError) as exc:
        raise ManifestError(("<manifest>",)) from exc


def pointer_to_json(pointer: SnapshotPointer) -> str:
    """Serialize a schema-valid current-snapshot pointer deterministically."""
    document = {
        "snapshot_id": pointer.snapshot_id,
        "updated_at": _to_iso_datetime(pointer.updated_at),
    }
    serialized = json.dumps(document, sort_keys=True, separators=(",", ":"))
    _parse_and_validate(serialized, _POINTER_SCHEMA_PATH, "<pointer>")
    return serialized


def pointer_from_json(value: str) -> SnapshotPointer:
    """Validate and parse a pointer, reporting all schema-invalid field paths."""
    document = _parse_and_validate(value, _POINTER_SCHEMA_PATH, "<pointer>")
    try:
        return SnapshotPointer(
            snapshot_id=document["snapshot_id"],
            updated_at=_from_iso_datetime(document["updated_at"]),
        )
    except (TypeError, ValueError) as exc:
        raise ManifestError(("<pointer>",)) from exc
