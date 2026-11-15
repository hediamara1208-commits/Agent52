"""Session_API Lambda handler (Req. 22, 23.6).

Six routes, nothing else. The owner is the Cognito ``sub`` claim that the API Gateway
authorizer validated; a request without it gets 401. Reads take the owner from the caller, so a
foreign session id is a 404. The handler places, routes, or triggers no order, transfer, or
brokerage or bank action (Req. 22.10). Tokens and request bodies are never logged.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Callable

from guide.contract.personas import load_personas
from guide.contract.profiler import CONTRACT_FIELDS, build_contract_from_form, build_contract_from_persona
from guide.contract.validate import validate_contract
from guide.tribunal import session_view as sv
from guide.tribunal.request_parser import MissingFields, parse_request

logger = logging.getLogger(__name__)

ROUTES: tuple[tuple[str, str], ...] = (
    ("GET", "/personas"),
    ("GET", "/profiles"),
    ("PUT", "/profiles/{id}"),
    ("POST", "/sessions"),
    ("GET", "/sessions/{id}"),
    ("GET", "/sessions/{id}/trace"),
)
_PROFILE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass
class Deps:
    """Everything the handlers touch; tests inject fakes, Lambda builds the real ones lazily."""

    store: Any  # SessionStore
    runtime: Any  # client with invoke_agent_runtime(agentRuntimeArn=..., payload=...)
    runtime_arn: str
    cors_origin: str
    universe: Callable[[], set[str]]
    personas: Callable[[], dict[str, Any]] = lambda: dict(load_personas().personas)


_deps: Deps | None = None


def _default_deps() -> Deps:
    global _deps
    if _deps is None:
        import boto3

        from guide.config import load_config
        from guide.data.snapshot import SnapshotStore
        from guide.session.store import DynamoSessionStore
        from guide.toolkit import metrics

        config = load_config()

        def universe() -> set[str]:
            source = SnapshotStore(config).pin()
            return set(source.read_table(metrics.UNIVERSE_TABLE)["ticker"])

        _deps = Deps(
            store=DynamoSessionStore(config.session_table),
            runtime=boto3.client("bedrock-agentcore"),
            runtime_arn=config.agent_runtime_arn,
            cors_origin=config.cors_origin,
            universe=universe,
        )
    return _deps


class _HttpError(Exception):
    def __init__(self, status: int, message: str, **extra: Any) -> None:
        self.status, self.message, self.extra = status, message, extra


def _response(deps: Deps, status: int, body: Any, headers: dict[str, str] | None = None) -> dict[str, Any]:
    h = {"Content-Type": "application/json", "Cache-Control": "no-store", **(headers or {})}
    if deps.cors_origin:
        h["Access-Control-Allow-Origin"] = deps.cors_origin
        h["Vary"] = "Origin"
    return {"statusCode": status, "headers": h, "body": json.dumps(body, ensure_ascii=False)}


def _owner(event: dict[str, Any]) -> str:
    ctx = event.get("requestContext") or {}
    claims = (ctx.get("authorizer") or {}).get("claims") or {}
    sub = claims.get("sub")
    if not sub or not isinstance(sub, str):
        raise _HttpError(401, "unauthorized")
    return sub


def _route(event: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """Return the route template and its path parameters, or raise 404."""
    method = str(event.get("httpMethod", "")).upper()
    path = str(event.get("path", "")).rstrip("/") or "/"
    params = dict(event.get("pathParameters") or {})
    for m, template in ROUTES:
        if m != method:
            continue
        regex = "^" + re.sub(r"\{id\}", r"([^/]+)", template) + "$"
        match = re.match(regex, path)
        if match:
            if match.groups():
                params["id"] = match.group(1)
            return template, params
    raise _HttpError(404, "not found")


def _json_body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body")
    try:
        body = json.loads(raw) if raw else None
    except (TypeError, json.JSONDecodeError):
        body = None
    if not isinstance(body, dict):
        raise _HttpError(400, "request body must be a JSON object")
    return body


def _contract_for(profile: dict[str, Any], personas: dict[str, Any]) -> dict[str, Any]:
    """Build the Investor_Contract of a profile; 422 on an unknown persona or invalid fields."""
    persona_id = profile.get("base_persona_id")
    base = None
    if persona_id is not None:
        base = personas.get(persona_id)
        if base is None:
            raise _HttpError(422, "invalid profile", fields=["base_persona_id"])
    values = profile.get("values") or {}
    if not isinstance(values, dict):
        raise _HttpError(422, "invalid profile", fields=["values"])
    contract = build_contract_from_form(values, base) if (values or base is None) else build_contract_from_persona(base)
    errors = validate_contract(contract)
    if errors:
        raise _HttpError(422, "invalid profile", fields=[e.field for e in errors])
    return contract


# ---- handlers -------------------------------------------------------------------------------

def _list_personas(deps: Deps, owner: str, event: dict[str, Any], params: dict[str, str]):
    items = []
    for persona in deps.personas().values():
        items.append(json.loads(json.dumps(asdict(persona), default=list)))
    return 200, {"personas": items}


def _list_profiles(deps: Deps, owner: str, event: dict[str, Any], params: dict[str, str]):
    return 200, {"profiles": [p for p in deps.store.list_profiles(owner)
                              if not str(p.get("profile_id", "")).startswith(_INPUT_PREFIX)]}


def _put_profile(deps: Deps, owner: str, event: dict[str, Any], params: dict[str, str]):
    profile_id = params.get("id", "")
    if not _PROFILE_ID.match(profile_id):
        raise _HttpError(404, "not found")
    profile = _json_body(event)
    profile.pop("owner", None)
    profile["profile_id"] = profile_id
    _contract_for(profile, deps.personas())
    deps.store.put_profile(owner, profile)
    return 200, profile


_INPUT_PREFIX = "session-input-"
_CHANGEABLE = ("position_size", "period") + tuple(CONTRACT_FIELDS)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _apply_appeal(deps: Deps, owner: str, body: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    """Copy the original inputs, apply exactly one change, return (new body, period or None).

    The original session and its stored inputs are never modified (Req. 30.2).
    """
    original_id = body.get("appeal_of")
    change = body.get("change")
    if not isinstance(original_id, str) or not _SESSION_ID.match(original_id):
        raise _HttpError(404, "not found")
    if not isinstance(change, dict) or set(change) != {"field", "value"} or change["field"] not in _CHANGEABLE:
        raise _HttpError(422, "change must be {field, value} with one changeable field", fields=["change"])
    view = deps.store.get_view(owner, original_id)
    saved = next((p for p in deps.store.list_profiles(owner)
                  if p.get("profile_id") == _INPUT_PREFIX + original_id), None)
    if view is None or saved is None:
        raise _HttpError(404, "not found")
    if view.status != "completed":
        raise _HttpError(409, "only a completed session can be appealed")

    profile = json.loads(json.dumps(saved["profile"]))
    text = saved["request_text"]
    period = saved.get("period")
    field, value = change["field"], change["value"]
    if field == "position_size":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1:
            raise _HttpError(422, "position_size must be a fraction in (0, 1]", fields=["change"])
        parsed = parse_request(text, deps.universe())
        if isinstance(parsed, MissingFields):
            raise _HttpError(422, "original request is not appealable", fields=["change"])
        text = f"{round(value * 100, 4):g}% in {parsed.ticker}"
    elif field == "period":
        ok = (isinstance(value, dict) and set(value) == {"start", "end"}
              and all(isinstance(v, str) and _ISO_DATE.match(v) for v in value.values())
              and value["start"] < value["end"])
        if not ok:
            raise _HttpError(422, "period must be {start, end} ISO dates, start before end", fields=["change"])
        period = {"start": value["start"], "end": value["end"]}
    else:
        values = dict(profile.get("values") or {})
        values[field] = value
        profile["values"] = values
    return {"profile": profile, "request_text": text, "change": change}, period


def _create_session(deps: Deps, owner: str, event: dict[str, Any], params: dict[str, str]):
    body = _json_body(event)
    appeal_of = body.get("appeal_of")
    period = None
    if appeal_of is not None:
        body, period = _apply_appeal(deps, owner, body)
    profile = body.get("profile")
    text = body.get("request_text")
    if not isinstance(profile, dict) or not isinstance(text, str) or not text.strip():
        raise _HttpError(422, "profile and request_text are required",
                         fields=[n for n, ok in (("profile", isinstance(profile, dict)),
                                                 ("request_text", isinstance(text, str) and bool(text.strip()))) if not ok])
    contract = _contract_for(profile, deps.personas())
    parsed = parse_request(text, deps.universe())
    if isinstance(parsed, MissingFields):
        raise _HttpError(422, "request is missing fields", missing=parsed.as_dict())

    session_id = uuid.uuid4().hex
    view = sv.new_session_view(session_id, contract=contract)
    deps.store.put_view(owner, view)
    payload = {"session_id": session_id, "owner": owner, "profile": profile, "request_text": text}
    if period is not None:
        payload["period"] = period
    if appeal_of is not None:
        payload["appeal_of"] = appeal_of
    record = {"profile_id": _INPUT_PREFIX + session_id, "profile": profile, "request_text": text}
    if period is not None:
        record["period"] = period
    if appeal_of is not None:
        record["appeal_of"] = appeal_of
        record["change"] = body["change"]
    deps.store.put_profile(owner, record)  # inputs kept so this session can be appealed (Req. 30.2)
    try:
        deps.runtime.invoke_agent_runtime(
            agentRuntimeArn=deps.runtime_arn, payload=json.dumps(payload).encode("utf-8")
        )
    except Exception as error:  # any failure to reach the runtime (Req. 23.6)
        failed_view = sv.failed(view, "runtime", f"Agent_Runtime unreachable ({type(error).__name__})")
        deps.store.put_view(owner, failed_view)
        return 503, sv.session_view_to_dict(failed_view)
    return 202, {"session_id": session_id, "status": "running"}


def _get_session(deps: Deps, owner: str, event: dict[str, Any], params: dict[str, str]):
    return 200, sv.session_view_to_dict(_load_view(deps, owner, params))


def _get_trace(deps: Deps, owner: str, event: dict[str, Any], params: dict[str, str]):
    view = _load_view(deps, owner, params)
    return 200, {"session_id": view.session_id, "trace": view.trace}


def _load_view(deps: Deps, owner: str, params: dict[str, str]) -> sv.SessionView:
    session_id = params.get("id", "")
    view = deps.store.get_view(owner, session_id) if _SESSION_ID.match(session_id) else None
    if view is None:
        raise _HttpError(404, "not found")
    return view


_HANDLERS = {
    ("GET", "/personas"): _list_personas,
    ("GET", "/profiles"): _list_profiles,
    ("PUT", "/profiles/{id}"): _put_profile,
    ("POST", "/sessions"): _create_session,
    ("GET", "/sessions/{id}"): _get_session,
    ("GET", "/sessions/{id}/trace"): _get_trace,
}


def handler(event: dict[str, Any], context: Any = None, deps: Deps | None = None) -> dict[str, Any]:
    deps = deps or _default_deps()
    try:
        owner = _owner(event)
        template, params = _route(event)
        status, body = _HANDLERS[(str(event["httpMethod"]).upper(), template)](deps, owner, event, params)
        headers = None
        if template.endswith("/trace"):
            headers = {"Content-Disposition": f'attachment; filename="trace-{params["id"]}.json"'}
        return _response(deps, status, body, headers)
    except _HttpError as err:
        return _response(deps, err.status, {"error": err.message, **err.extra})
    except Exception as error:  # never echo internals or event contents
        logger.error("unhandled error: %s", type(error).__name__)
        return _response(deps, 500, {"error": "internal error"})
