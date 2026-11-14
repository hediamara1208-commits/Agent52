"""Data-quality notes and limits (Req. 3.7, 3.8, 3.9, 17.11, 20.10)."""
from __future__ import annotations

import re
from datetime import date
from typing import Iterable

from guide.data.snapshot import SnapshotInfo

CNQ_TICKER = "CNQ.TO"
CNQ_ANOMALY_DATE = date(2022, 8, 22)

CNQ_NOTE = (
    "CNQ.TO 2022-08-22: the 1.021 split factor likely reflects a special "
    "distribution and is unverified."
)

SURVIVORSHIP_BIAS_TEXT = (
    "Survivorship-bias limitation: the Dataset holds 31 assets that exist today, "
    "covering about five years. Assets that were delisted or failed in the window "
    "are absent, so historical results are likely better than an investor would "
    "have experienced, and a five-year window limits any conclusion."
)

UNSUPPORTED_NOTICE = (
    "The Dataset does not contain {topics}. Any related argument is unsupported by Exhibits."
)

_UNSUPPORTED_PATTERNS: dict[str, re.Pattern] = {
    "ESG scores": re.compile(
        r"\besg\b|\bsustainab\w*|\bcarbon (?:score|rating|footprint)|\bgovernance score", re.I
    ),
    "news": re.compile(r"\bnews\b|\bheadlines?\b|\bannouncements?\b|\bsentiment\b|\bpress releases?\b", re.I),
    "company fundamentals": re.compile(
        r"\bfundamentals?\b|\bearnings\b|\beps\b|\bp/?e\b|\bprice[- ]to[- ]earnings\b|\brevenues?\b"
        r"|\bbalance sheet\b|\bcash flow\b|\bprofit margins?\b|\bvaluation\b|\bbook value\b",
        re.I,
    ),
}


def fallback_note(snapshot: SnapshotInfo) -> str:
    """Return the mandatory Exhibit notice for a verified cache fallback."""
    return (
        "Dataset was served from the Local_Cache because the Primary_Store was unreachable "
        f"(snapshot {snapshot.snapshot_id})."
    )


def snapshot_note(snapshot: SnapshotInfo) -> str:
    """Identify the pinned snapshot and its retrieval timestamp in user-facing notes."""
    retrieved_at = snapshot.retrieved_at.isoformat().replace("+00:00", "Z")
    return f"Dataset snapshot {snapshot.snapshot_id} retrieved at {retrieved_at}."


def coverage_end_note(snapshot: SnapshotInfo) -> str:
    """Disclose that an as-of request exceeded the snapshot's data coverage."""
    return f"data available up to {snapshot.coverage_end.isoformat()} in snapshot {snapshot.snapshot_id}"


def cnq_note_applies(assets: Iterable[str], period_start: date, period_end: date) -> bool:
    """True when CNQ.TO is involved and the period includes 2022-08-22."""
    return CNQ_TICKER in set(assets) and period_start <= CNQ_ANOMALY_DATE <= period_end


def cnq_notes(assets: Iterable[str], period_start: date, period_end: date) -> list[str]:
    """Processing notes to attach to an Exhibit (Req. 3.7)."""
    return [CNQ_NOTE] if cnq_note_applies(assets, period_start, period_end) else []


def survivorship_bias_text() -> str:
    """Limitation text attached to the Ruling when results derive from the Dataset (Req. 3.8)."""
    return SURVIVORSHIP_BIAS_TEXT


def detect_unsupported_topics(text: str) -> list[str]:
    """Names of unsupported topics (ESG scores, news, company fundamentals) found in ``text``."""
    return [name for name, pattern in _UNSUPPORTED_PATTERNS.items() if pattern.search(text or "")]


def unsupported_notice(topics: Iterable[str]) -> str | None:
    """Notice that the Dataset lacks the requested information (Req. 3.9), or None."""
    topics = list(topics)
    if not topics:
        return None
    joined = topics[0] if len(topics) == 1 else ", ".join(topics[:-1]) + " or " + topics[-1]
    return UNSUPPORTED_NOTICE.format(topics=joined)
