import json

import pytest

from guide.trace.recorder import TraceRecorder


class _Span:
    def __init__(self, store):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def set_attribute(self, k, v):
        self.store[k] = v


class _Tracer:
    def __init__(self):
        self.spans = []

    def start_as_current_span(self, name):
        attrs = {}
        self.spans.append((name, attrs))
        return _Span(attrs)


def test_summary_cap_comes_from_argument_and_config_default():
    rec = TraceRecorder(emit_spans=False, max_summary_chars=20)
    ev = rec.claim_removed("judge", "x" * 100)
    assert len(ev.summary["claim"]) == 20
    default = TraceRecorder(emit_spans=False)
    assert len(default.claim_removed("judge", "y" * 1000).summary["claim"]) == 400


def test_invalid_cap_rejected():
    with pytest.raises(ValueError):
        TraceRecorder(emit_spans=False, max_summary_chars=0)


def test_data_event_in_export_and_spans():
    tracer = _Tracer()
    rec = TraceRecorder(tracer=tracer, max_summary_chars=50)
    rec.data_event("cache_fallback", "20261113T000000Z-starter", "2026-11-14T10:00:00Z", "s3 timeout")
    exported = json.loads(rec.export_json())
    assert exported[0]["kind"] == "cache_fallback"
    assert exported[0]["summary"] == {
        "snapshot_id": "20261113T000000Z-starter",
        "retrieved_at": "2026-11-14T10:00:00Z",
        "cause": "s3 timeout",
    }
    assert tracer.spans[0][1]["guide.cause"] == "s3 timeout"
    with pytest.raises(ValueError):
        rec.data_event("other", "s", "t", "c")
