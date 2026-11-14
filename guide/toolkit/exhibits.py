"""Immutable, sequentially numbered Exhibits and the registry that stores them.

Requirements 2.2 and 2.3: every Toolkit call yields an Exhibit with a sequential
number and all required fields; an Exhibit cannot be changed after creation.
"""
from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import date
from types import MappingProxyType
from typing import Any


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
        }


_FIELD_NAMES = tuple(f.name for f in fields(Exhibit) if f.name != "number")


class ExhibitRegistry:
    """Stores the Exhibits of one Tribunal_Session, numbered 1, 2, 3, ..."""

    def __init__(self) -> None:
        self._exhibits: list[Exhibit] = []
        self._lock = threading.Lock()

    def add(self, **fields_: Any) -> Exhibit:
        """Create an Exhibit with the next sequential number and store it.

        All fields except ``number`` are required; ``number`` is assigned here.
        """
        if "number" in fields_:
            raise TypeError("number is assigned by the registry")
        missing = [n for n in _FIELD_NAMES if n not in fields_]
        extra = [n for n in fields_ if n not in _FIELD_NAMES]
        if missing:
            raise TypeError(f"missing Exhibit fields: {', '.join(missing)}")
        if extra:
            raise TypeError(f"unknown Exhibit fields: {', '.join(extra)}")
        with self._lock:
            exhibit = Exhibit(number=len(self._exhibits) + 1, **fields_)
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
