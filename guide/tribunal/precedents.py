"""Precedents: summaries of completed Tribunal_Sessions that later sessions cite (Req. 31).

Items live in the Session_Store under the shared partition ``owner = "precedent"`` with sort
key ``asset#<ticker>#<session_id>``. They hold the Persona or profile identifier and no user
identifier. Everything stored comes from the SessionView, which code built from Exhibits and
rule results; no agent text is read here except the Judge's Soft_Preference assessments.
"""
from __future__ import annotations

from typing import Any

from guide.session.store import InMemorySessionStore, PrecedentItemStore
from guide.tribunal.option_ids import REQUEST_OPTION_ID
from guide.tribunal.session_view import SessionView

ASSET_PREFIX = "asset#"
MAX_EXHIBITS = 40


class InMemoryPrecedentStore(InMemorySessionStore):
    """Test store: the in-memory Session_Store, used only for its Precedent partition."""


def precedent_sk(asset: str, session_id: str) -> str:
    return f"{ASSET_PREFIX}{asset}#{session_id}"


def build_precedent(view: SessionView, profile_id: str) -> dict[str, Any]:
    """Summarise a completed SessionView; raise ValueError if it cannot be summarised."""
    if not profile_id or not isinstance(profile_id, str):
        raise ValueError("profile_id is required")
    if view.status != "completed" or not view.ruling or not view.verdict:
        raise ValueError("only a completed session with a Ruling and Verdict yields a Precedent")
    request = next(
        (o for o in view.ruling.get("options", []) if o.get("option_id") == REQUEST_OPTION_ID),
        None,
    )
    if request is None:
        raise ValueError("the Ruling holds no request option")
    verdict = view.verdict
    return {
        "session_id": view.session_id,
        "profile_id": profile_id,
        "asset": request["ticker"],
        "weight": float(request["weight"]),
        "verdict": verdict["verdict"],
        "max_weight": verdict.get("max_weight"),
        "deciding_rules": list(verdict.get("failing_rules", [])),
        "unverified_rules": list(verdict.get("unverified_rules", [])),
        "soft_preferences": [
            {k: a.get(k) for k in ("preference", "assessment", "findings", "exhibits") if k in a}
            for a in view.ruling.get("assessments", [])
        ],
        "exhibit_values": [
            {k: e.get(k) for k in ("number", "metric", "value", "snapshot_id")}
            for e in view.exhibits[:MAX_EXHIBITS]
        ],
        "contract": view.contract,
    }


def put_precedent(store: PrecedentItemStore, view: SessionView, profile_id: str) -> dict[str, Any]:
    """Store the Precedent of a completed session and return it (Req. 31.1, 31.3)."""
    doc = build_precedent(view, profile_id)
    store.put_precedent_item(precedent_sk(doc["asset"], doc["session_id"]), doc)
    return doc


def closest(
    store: PrecedentItemStore, asset: str, weight: float, *, exclude_session: str | None = None
) -> dict[str, Any] | None:
    """The Precedent for ``asset`` with the position size nearest ``weight``, or None (Req. 31.2).

    Ties go to the smaller weight, then the session id, so the choice is deterministic.
    """
    candidates = [
        p
        for p in store.list_precedent_items(f"{ASSET_PREFIX}{asset}#")
        if p["session_id"] != exclude_session
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: (abs(p["weight"] - weight), p["weight"], p["session_id"]))
