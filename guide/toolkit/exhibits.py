"""Immutable, sequentially numbered Exhibits and the registry that stores them.

Requirements 2.2 and 2.3: every Toolkit call yields an Exhibit with a sequential
number and all required fields; an Exhibit cannot be changed after creation.
"""
from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import date, datetime, timezone
from types import MappingProxyType
from typing import Any

from guide.data import quality
from guide.data.snapshot import SnapshotInfo


def _freeze(obj: Any) -> Any:
    """Recursively convert mappings to read-only proxies and sequences to tuples."""
    if isinstance(obj, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(_freeze(v) for v in obj)
    if isinstance(obj, (set, frozenset)):
        return frozenset(_freeze(v) for v in obj)
    return obj


def thaw(obj: Any) -> Any:
    """Convert a frozen structure back to plain dicts and lists (e.g. for JSON)."""
    if isinstance(obj, Mapping):
        return {k: thaw(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [thaw(v) for v in obj]
    return obj


@dataclass(frozen=True)
class Exhibit:
    number: int
    metric: str
    value: float | Mapping  # JSON-serializable, stored read-only
    period_start: date
    period_end: date
    assets: tuple[str, ...]
    currency: str
    source_files: tuple[str, ...]
    processing_notes: tuple[str, ...]
    inputs: Mapping  # arguments used, for determinism checks
    snapshot_id: str | None
    snapshot_retrieved_at: str | None

    def __post_init__(self) -> None:
        setter = object.__setattr__
        setter(self, "value", _freeze(self.value))
        setter(self, "inputs", _freeze(self.inputs))
        for name in ("assets", "source_files", "processing_notes"):
            setter(self, name, tuple(getattr(self, name)))

    def to_dict(self) -> dict[str, Any]:
        """Plain JSON-friendly representation."""
        return {
            "number": self.number,
            "metric": self.metric,
            "value": thaw(self.value),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "assets": list(self.assets),
            "currency": self.currency,
            "source_files": list(self.source_files),
            "processing_notes": list(self.processing_notes),
            "inputs": thaw(self.inputs),
            "snapshot_id": self.snapshot_id,
            "snapshot_retrieved_at": self.snapshot_retrieved_at,
        }


_FIELD_NAMES = tuple(f.name for f in fields(Exhibit) if f.name != "number")
_SNAPSHOT_FIELD_NAMES = ("snapshot_id", "snapshot_retrieved_at")
_CALLER_FIELD_NAMES = tuple(name for name in _FIELD_NAMES if name not in _SNAPSHOT_FIELD_NAMES)


def _snapshot_retrieved_at(snapshot: SnapshotInfo) -> str:
    """Return the pinned retrieval timestamp in canonical UTC ISO 8601 form."""
    retrieved_at = snapshot.retrieved_at
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        return retrieved_at.isoformat()
    return retrieved_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _fallback_note(snapshot: SnapshotInfo) -> str:
    """Use the shared fallback note when available during the task transition."""
    note_factory = getattr(quality, "fallback_note", None)
    if callable(note_factory):
        return note_factory(snapshot)
    return (
        "Dataset was served from the Local_Cache for Snapshot_Id "
        f"{snapshot.snapshot_id}."
    )


class ExhibitRegistry:
    """Stores one session's sequential Exhibits, bound to its pinned snapshot."""

    def __init__(self, snapshot: SnapshotInfo | None = None) -> None:
        self._snapshot = snapshot
        self._exhibits: list[Exhibit] = []
        self._lock = threading.Lock()

    def add(self, **fields_: Any) -> Exhibit:
        """Create, snapshot-bind, sequentially number, and store an Exhibit.

        Callers provide every computation field except ``number`` and the snapshot
        fields. The registry owns those values so every Exhibit in a session names
        the same pinned snapshot.
        """
        if "number" in fields_:
            raise TypeError("number is assigned by the registry")
        supplied_snapshot_fields = [name for name in _SNAPSHOT_FIELD_NAMES if name in fields_]
        if supplied_snapshot_fields:
            raise TypeError(
                "snapshot fields are assigned by the registry: "
                f"{', '.join(supplied_snapshot_fields)}"
            )
        missing = [name for name in _CALLER_FIELD_NAMES if name not in fields_]
        extra = [name for name in fields_ if name not in _CALLER_FIELD_NAMES]
        if missing:
            raise TypeError(f"missing Exhibit fields: {', '.join(missing)}")
        if extra:
            raise TypeError(f"unknown Exhibit fields: {', '.join(extra)}")

        snapshot_id: str | None = None
        snapshot_retrieved_at: str | None = None
        source_files = tuple(fields_["source_files"])
        processing_notes = tuple(fields_["processing_notes"])
        if self._snapshot is not None:
            snapshot_id = self._snapshot.snapshot_id
            snapshot_retrieved_at = _snapshot_retrieved_at(self._snapshot)
            source_files = tuple(
                f"{source_file.split('@', maxsplit=1)[0]}@{snapshot_id}"
                for source_file in source_files
            )
            if self._snapshot.served_from == "cache_fallback":
                processing_notes += (_fallback_note(self._snapshot),)

        exhibit_fields = {
            **fields_,
            "source_files": source_files,
            "processing_notes": processing_notes,
            "snapshot_id": snapshot_id,
            "snapshot_retrieved_at": snapshot_retrieved_at,
        }
        with self._lock:
            exhibit = Exhibit(number=len(self._exhibits) + 1, **exhibit_fields)
            self._exhibits.append(exhibit)
        return exhibit

    def get(self, number: int) -> Exhibit | None:
        if isinstance(number, bool) or not isinstance(number, int):
            return None
        if 1 <= number <= len(self._exhibits):
            return self._exhibits[number - 1]
        return None

    def all(self) -> list[Exhibit]:
        return list(self._exhibits)

    def __len__(self) -> int:
        return len(self._exhibits)
