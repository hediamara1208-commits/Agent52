import json

import pytest

from guide.tribunal.session_view import (
    SessionView, SessionViewError, failed, new_session_view, session_view_from_json,
    session_view_to_json, stage_finished, with_data_notice,
)

SNAP = {"snapshot_id": "s1", "source": "starter", "retrieved_at": "2026-11-13T00:00:00Z",
        "coverage_end": "2026-11-12", "served_from": "primary", "fallback_cause": None}


def test_round_trip_and_helpers():
    v = new_session_view("abc", snapshot=SNAP)
    v = stage_finished(v, "profiler", next_agent="advocate", summary="Done.",
                       exhibits=[{"number": 1, "metric": "m", "value": 1.5, "currency": "CAD",
                                  "snapshot_id": "s1"}])
    v = with_data_notice(v, "served from cache")
    assert v.stages_done == ["profiler"] and v.active_agent == "advocate"
    again = session_view_from_json(session_view_to_json(v))
    assert again == v
    assert "mode" not in json.loads(session_view_to_json(v))


def test_failed_view_round_trips_and_names_stage():
    v = failed(new_session_view("abc"), "judge", "timeout")
    again = session_view_from_json(session_view_to_json(v))
    assert again.status == "failed" and again.error.stage == "judge"


def test_invalid_document_names_failing_fields():
    doc = json.loads(session_view_to_json(new_session_view("abc")))
    doc["status"] = "paused"
    del doc["trace"]
    doc["mode"] = "friendly"
    with pytest.raises(SessionViewError) as e:
        session_view_from_json(json.dumps(doc))
    assert {"status", "trace", "mode"} <= set(e.value.fields)


def test_failed_status_requires_error():
    with pytest.raises(SessionViewError):
        session_view_to_json(SessionView(session_id="x", status="failed"))
