"""SessionView: the single JSON document both UI modes render (Req. 7.9, 7.14 to 7.17, 22.15).

The document holds plain JSON values only, so it round-trips exactly. The schema
``session_view.schema.json`` is the contract with the front end. The browser mode and
focus are never part of it.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).with_name("session_view.schema.json")


class SessionViewError(ValueError):
    """A SessionView failed schema validation; ``fields`` names the failing fields."""

    def __init__(self, fields: Sequence[str]):
        self.fields = tuple(fields)
        super().__init__("invalid SessionView, failing fields: " + ", ".join(self.fields))


@dataclass
class StageError:
    stage: str
    message: str


@dataclass
class SessionView:
    session_id: str
    status: Literal["running", "completed", "failed"] = "running"
    contract: dict | None = None
    stage: str = ""
    stages_done: list[str] = field(default_factory=list)
    active_agent: str | None = None
    exhibits: list[dict] = field(default_factory=list)
    verdict: dict | None = None
    ruling: dict | None = None
    rule_results: list[dict] = field(default_factory=list)
    sensitivity: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    summaries: dict[str, str] = field(default_factory=dict)
    snapshot: dict | None = None
    data_notices: list[str] = field(default_factory=list)
    error: StageError | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_FIELD_NAMES = tuple(f.name for f in fields(SessionView))


def _jsonable(value: Any) -> Any:
    """Convert Exhibits, mappings, dates, and dataclass-like objects to plain JSON values."""
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable(value.to_dict())
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat().replace("+00:00", "Z")
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    return value


def _field_name(error: Any) -> str:
    path = [str(p) for p in error.absolute_path]
    if error.validator == "required":
        m = re.search(r"'([^']+)' is a required property", error.message)
        if m:
            path.append(m.group(1))
    elif error.validator == "additionalProperties":
        m = re.search(r"'([^']+)' was unexpected", error.message)
        if m:
            path.append(m.group(1))
    return ".".join(path) if path else "session_view"


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_document(document: Any) -> None:
    if not isinstance(document, dict):
        raise SessionViewError(("session_view",))
    errors = sorted(
        _validator().iter_errors(document),
        key=lambda e: (list(map(str, e.absolute_path)), e.message),
    )
    if errors:
        raise SessionViewError(tuple(dict.fromkeys(_field_name(e) for e in errors)))


def session_view_to_dict(view: SessionView) -> dict[str, Any]:
    doc = _jsonable(view.to_dict())
    validate_document(doc)
    return doc


def session_view_to_json(view: SessionView) -> str:
    return json.dumps(session_view_to_dict(view), sort_keys=True, ensure_ascii=False)


def session_view_from_json(text: str) -> SessionView:
    try:
        doc = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        raise SessionViewError(("session_view",)) from None
    validate_document(doc)
    err = doc["error"]
    kwargs = {name: doc[name] for name in _FIELD_NAMES if name != "error"}
    return SessionView(**kwargs, error=StageError(**err) if err else None)


# ---- helpers that build an update for one event ------------------------------------------

def new_session_view(session_id: str, contract: Any = None, snapshot: Any = None) -> SessionView:
    return SessionView(
        session_id=session_id,
        contract=_jsonable(contract) if contract is not None else None,
        snapshot=_jsonable(snapshot) if snapshot is not None else None,
    )


def stage_finished(
    view: SessionView,
    stage: str,
    *,
    next_agent: str | None = None,
    summary: str | None = None,
    summary_key: str | None = None,
    completed: bool = False,
    **outputs: Any,
) -> SessionView:
    """Return a new view with ``stage`` marked done and its outputs written in.

    ``outputs`` may set any SessionView field except status and error (e.g. exhibits,
    verdict). ``summary`` is stored under ``summary_key`` (default: the stage name).
    """
    bad = [k for k in outputs if k not in _FIELD_NAMES or k in ("status", "error", "session_id")]
    if bad:
        raise ValueError("unknown or protected SessionView fields: " + ", ".join(sorted(bad)))
    updates = {k: _jsonable(v) for k, v in outputs.items()}
    done = list(view.stages_done)
    if stage not in done:
        done.append(stage)
    summaries = dict(view.summaries)
    if summary is not None:
        summaries[summary_key or stage] = summary
    return replace(
        view,
        **updates,
        stage=stage,
        stages_done=done,
        active_agent=None if completed else next_agent,
        summaries=summaries,
        status="completed" if completed else "running",
    )


def with_data_notice(view: SessionView, notice: str, snapshot: Any = None) -> SessionView:
    """Add a data (fallback) notice once; optionally replace the pinned snapshot info."""
    notices = list(view.data_notices)
    if notice not in notices:
        notices.append(notice)
    return replace(
        view,
        data_notices=notices,
        snapshot=_jsonable(snapshot) if snapshot is not None else view.snapshot,
    )


def failed(view: SessionView, stage: str, message: str) -> SessionView:
    """Mark the session failed at ``stage``; completed stages and inputs stay (Req. 7.20)."""
    return replace(
        view, status="failed", stage=stage, active_agent=None, error=StageError(stage, message)
    )
