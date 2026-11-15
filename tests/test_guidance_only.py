from dataclasses import dataclass, field

from guide.trace.recorder import TraceRecorder
from guide.tribunal.guidance_only import (
    GUIDANCE_ONLY_MESSAGE, check_guidance_only, guidance_message, strip_violations)

BAD = ["Place the order for 30% TSLA now.", "Your trade confirmed at 10:01.",
       "Use the prefilled order ticket.", "Try the one-click buy.", "Transfer funds to the account."]
GOOD = ["A 30% TSLA position exceeds the 10% per-asset cap (Exhibit 3).",
        "The system never places the order.", "Consider a smaller size as guidance."]


def test_bad_statements_fail_and_good_pass():
    rec = TraceRecorder(emit_spans=False)
    assert all(not f.passed and f.matched_pattern for f in check_guidance_only("advocate", BAD))
    findings = check_guidance_only("judge", GOOD, rec)
    assert all(f.passed for f in findings)
    assert guidance_message(findings) is None
    assert len(rec.events) == 1 and "pass" in rec.events[0].summary["result"]


def test_one_trace_event_per_output_and_message():
    rec = TraceRecorder(emit_spans=False)
    findings = check_guidance_only("clerk", BAD + GOOD, rec)
    assert len(rec.events) == 1 and "fail" in rec.events[0].summary["result"]
    assert guidance_message(findings) == GUIDANCE_ONLY_MESSAGE


def test_strip_violations_removes_and_traces():
    @dataclass
    class R:
        narrative: list[str] = field(default_factory=list)
        title: str = "ok"

    r = R(narrative=BAD[:2] + GOOD)
    findings = check_guidance_only("judge", r.narrative)
    out, events = strip_violations(r, findings)
    assert out.narrative == GOOD and out.title == "ok"
    assert r.narrative == BAD[:2] + GOOD
    assert len(events) == 2 and all(e.kind == "claim_removed" for e in events)
