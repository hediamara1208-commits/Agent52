"""Focused coverage for task 3.8 snapshot-aware alignment helpers."""
from datetime import date, datetime, timezone

import pandas as pd

from guide.data.quality import coverage_end_note, fallback_note, snapshot_note
from guide.data.snapshot import SnapshotInfo
from guide.toolkit.align import convert_to_cad, filter_as_of


SNAPSHOT = SnapshotInfo(
    snapshot_id="20261113T000000Z-starter",
    source="starter",
    retrieved_at=datetime(2026, 11, 13, tzinfo=timezone.utc),
    coverage_end=date(2026, 11, 12),
    served_from="cache_fallback",
    fallback_cause="endpoint unavailable",
)


def test_filter_as_of_clamps_to_snapshot_coverage_and_records_note():
    frame = pd.DataFrame({"date": ["2026-11-11", "2026-11-12", "2026-11-13"], "value": [1, 2, 3]})

    filtered, notes = filter_as_of(frame, date(2026, 12, 1), SNAPSHOT)

    assert filtered["value"].tolist() == [1, 2]
    assert notes == [coverage_end_note(SNAPSHOT)]


def test_filter_as_of_before_coverage_has_no_coverage_notice():
    frame = pd.DataFrame({"date": ["2026-11-11", "2026-11-12"], "value": [1, 2]})

    filtered, notes = filter_as_of(frame, date(2026, 11, 11), SNAPSHOT)

    assert filtered["value"].tolist() == [1]
    assert notes == []


def test_convert_to_cad_drops_and_names_price_dates_without_an_earlier_fx_rate():
    wide = pd.DataFrame(
        {"USD_ASSET": [10.0, 10.0, 10.0], "CAD_ASSET": [5.0, 5.0, 5.0]},
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
    )
    fx = pd.DataFrame({"date": ["2026-01-02"], "usdcad": [1.4]})

    converted, notes = convert_to_cad(wide, {"USD_ASSET": "USD", "CAD_ASSET": "CAD"}, fx)

    assert converted.index.tolist() == [pd.Timestamp("2026-01-02"), pd.Timestamp("2026-01-03")]
    assert converted["USD_ASSET"].tolist() == [14.0, 14.0]
    assert converted["CAD_ASSET"].tolist() == [5.0, 5.0]
    assert any("2026-01-01" in note and "excluded date" in note for note in notes)
    assert any("carried forward" in note and "2026-01-03" in note for note in notes)


def test_snapshot_quality_notes_name_required_snapshot_details():
    assert SNAPSHOT.snapshot_id in fallback_note(SNAPSHOT)
    assert SNAPSHOT.snapshot_id in snapshot_note(SNAPSHOT)
    assert "2026-11-13T00:00:00Z" in snapshot_note(SNAPSHOT)
    assert coverage_end_note(SNAPSHOT) == "data available up to 2026-11-12 in snapshot 20261113T000000Z-starter"
