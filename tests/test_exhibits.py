"""Unit tests for snapshot-bound Toolkit Exhibits."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from guide.data.snapshot import SnapshotInfo
from guide.toolkit.exhibits import ExhibitRegistry


SNAPSHOT_ID = "20261113T000000Z-starter"
RETRIEVED_AT = datetime(2026, 11, 13, tzinfo=timezone.utc)


def _snapshot(*, served_from: str = "primary") -> SnapshotInfo:
    return SnapshotInfo(
        snapshot_id=SNAPSHOT_ID,
        source="starter",
        retrieved_at=RETRIEVED_AT,
        coverage_end=date(2026, 11, 12),
        served_from=served_from,  # type: ignore[arg-type]
        fallback_cause="primary store unreachable" if served_from == "cache_fallback" else None,
    )


def _exhibit_fields() -> dict[str, object]:
    return {
        "metric": "annualized_volatility",
        "value": 0.201,
        "period_start": date(2021, 11, 12),
        "period_end": date(2026, 11, 12),
        "assets": ("TSLA",),
        "currency": "CAD",
        "source_files": ("assets_universe", "prices_daily@outdated-snapshot"),
        "processing_notes": ("Prices converted to CAD.",),
        "inputs": {"ticker": "TSLA"},
    }


def test_registry_binds_snapshot_metadata_and_source_files():
    registry = ExhibitRegistry(_snapshot())

    exhibit = registry.add(**_exhibit_fields())

    assert exhibit.number == 1
    assert exhibit.snapshot_id == SNAPSHOT_ID
    assert exhibit.snapshot_retrieved_at == "2026-11-13T00:00:00Z"
    assert exhibit.source_files == (
        f"assets_universe@{SNAPSHOT_ID}",
        f"prices_daily@{SNAPSHOT_ID}",
    )
    assert exhibit.to_dict()["snapshot_id"] == SNAPSHOT_ID
    assert exhibit.to_dict()["snapshot_retrieved_at"] == "2026-11-13T00:00:00Z"


def test_cache_fallback_adds_a_snapshot_specific_processing_note():
    registry = ExhibitRegistry(_snapshot(served_from="cache_fallback"))

    exhibit = registry.add(**_exhibit_fields())

    assert any("Local_Cache" in note and SNAPSHOT_ID in note for note in exhibit.processing_notes)


def test_registry_without_a_snapshot_preserves_unbound_test_exhibits():
    registry = ExhibitRegistry()

    exhibit = registry.add(**_exhibit_fields())

    assert exhibit.snapshot_id is None
    assert exhibit.snapshot_retrieved_at is None
    assert exhibit.source_files == ("assets_universe", "prices_daily@outdated-snapshot")


def test_registry_rejects_caller_supplied_snapshot_metadata():
    registry = ExhibitRegistry(_snapshot())

    with pytest.raises(TypeError, match="snapshot fields are assigned by the registry"):
        registry.add(**_exhibit_fields(), snapshot_id="incorrect")
