"""Appeal (Req. 30): compare an original Tribunal_Session with its Appeal.

``diff_sessions`` is pure code over two SessionViews (or their dicts). It reports the Hard_Rule
results that changed, the Soft_Preference assessments that changed, and the Exhibits whose metric
matches but whose value differs. It never calls an agent and never alters either session.
"""
from __future__ import annotations

from typing import Any, Mapping

from guide.tribunal.session_view import session_view_to_dict


def _doc(session: Any) -> Mapping[str, Any]:
    return session if isinstance(session, Mapping) else session_view_to_dict(session)


def _verdict(doc: Mapping[str, Any]) -> dict[str, Any]:
    v = doc.get("verdict") or {}
    return {"verdict": v.get("verdict"), "max_weight": v.get("max_weight")}


def _exhibit_key(e: Mapping[str, Any]) -> tuple[str, tuple[str, ...]]:
    return str(e.get("metric")), tuple(sorted(e.get("assets") or []))


def diff_sessions(a: Any, b: Any) -> dict[str, Any]:
    """Return what differs between session ``a`` (original) and ``b`` (Appeal)."""
    da, db = _doc(a), _doc(b)

    ra = {r["rule"]: r for r in da.get("rule_results", [])}
    rb = {r["rule"]: r for r in db.get("rule_results", [])}
    rules = []
    for name in sorted(set(ra) | set(rb)):
        x, y = ra.get(name), rb.get(name)
        key = lambda r: None if r is None else (r.get("status"), r.get("observed"), r.get("limit"))  # noqa: E731
        if key(x) != key(y):
            rules.append({
                "rule": name,
                "original": None if x is None else {k: x.get(k) for k in ("status", "observed", "limit")},
                "appeal": None if y is None else {k: y.get(k) for k in ("status", "observed", "limit")},
            })

    def prefs(d: Mapping[str, Any]) -> dict[str, str]:
        return {p.get("preference"): p.get("assessment")
                for p in (d.get("ruling") or {}).get("assessments", []) if p.get("preference")}

    pa, pb = prefs(da), prefs(db)
    soft = [{"preference": k, "original": pa.get(k), "appeal": pb.get(k)}
            for k in sorted(set(pa) | set(pb)) if pa.get(k) != pb.get(k)]

    ea = {_exhibit_key(e): e for e in da.get("exhibits", [])}
    eb = {_exhibit_key(e): e for e in db.get("exhibits", [])}
    exhibits = [
        {"metric": k[0], "assets": list(k[1]),
         "original": {"number": ea[k].get("number"), "value": ea[k].get("value")},
         "appeal": {"number": eb[k].get("number"), "value": eb[k].get("value")}}
        for k in sorted(set(ea) & set(eb)) if ea[k].get("value") != eb[k].get("value")
    ]

    va, vb = _verdict(da), _verdict(db)
    return {
        "original_session_id": da.get("session_id"),
        "appeal_session_id": db.get("session_id"),
        "verdict": {"original": va, "appeal": vb, "changed": va != vb},
        "hard_rules": rules,
        "soft_preferences": soft,
        "exhibits": exhibits,
    }
