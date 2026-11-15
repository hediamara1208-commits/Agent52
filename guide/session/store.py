"""Session_Store: SessionViews and Custom_Profiles, DynamoDB and in-memory (Req. 7.23, 22.5-22.12).

Every read and write takes the owner from the caller (the Cognito ``sub``), so a foreign
session identifier finds no item (Req. 22.8). No credentials are handled here; boto3 resolves
them from the environment or the role.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from guide.tribunal.session_view import (
    SessionView,
    session_view_from_json,
    session_view_to_json,
)

SESSION_TTL_SECONDS = 7 * 24 * 3600
SESSION_PREFIX = "session#"
PROFILE_PREFIX = "profile#"


@runtime_checkable
class SessionSink(Protocol):
    """Where the orchestrator publishes the SessionView after each stage and on failure."""

    def publish(self, view: SessionView) -> None: ...


@runtime_checkable
class SessionStore(Protocol):
    def put_view(self, owner: str, view: SessionView) -> None: ...

    def get_view(self, owner: str, session_id: str) -> SessionView | None: ...

    def put_profile(self, owner: str, profile: dict[str, Any]) -> None: ...

    def list_profiles(self, owner: str) -> list[dict[str, Any]]: ...


PRECEDENT_OWNER = "precedent"  # shared partition readable by every signed-in user (Req. 31.3)


@runtime_checkable
class PrecedentItemStore(Protocol):
    """Raw access to the shared ``precedent`` partition; items carry no ttl."""

    def put_precedent_item(self, sk: str, document: dict[str, Any]) -> None: ...

    def list_precedent_items(self, sk_prefix: str) -> list[dict[str, Any]]: ...


class StoreSink:
    """A SessionSink bound to one owner, writing into any SessionStore."""

    def __init__(self, store: SessionStore, owner: str) -> None:
        if not owner:
            raise ValueError("owner is required")
        self._store = store
        self._owner = owner

    def publish(self, view: SessionView) -> None:
        self._store.put_view(self._owner, view)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_owner(owner: str) -> None:
    if not owner or not isinstance(owner, str):
        raise ValueError("owner is required")


def _profile_id(profile: dict[str, Any]) -> str:
    pid = profile.get("profile_id")
    if not pid or not isinstance(pid, str):
        raise ValueError("profile_id is required")
    return pid


class InMemorySessionStore:
    """Same interface as DynamoSessionStore, for tests and the local runner."""

    def __init__(self, clock=time.time) -> None:
        self._items: dict[tuple[str, str], dict[str, Any]] = {}
        self._clock = clock

    def put_view(self, owner: str, view: SessionView) -> None:
        _require_owner(owner)
        key = (owner, SESSION_PREFIX + view.session_id)
        prior = self._items.get(key)
        ttl = prior["ttl"] if prior else int(self._clock()) + SESSION_TTL_SECONDS
        self._items[key] = {
            "view": session_view_to_json(view),
            "status": view.status,
            "updated_at": _now_iso(),
            "ttl": ttl,
        }

    def get_view(self, owner: str, session_id: str) -> SessionView | None:
        _require_owner(owner)
        item = self._items.get((owner, SESSION_PREFIX + session_id))
        if item is None or item["ttl"] <= self._clock():
            return None
        return session_view_from_json(item["view"])

    def put_profile(self, owner: str, profile: dict[str, Any]) -> None:
        _require_owner(owner)
        self._items[(owner, PROFILE_PREFIX + _profile_id(profile))] = {
            "view": json.dumps(profile, sort_keys=True, ensure_ascii=False),
            "status": "saved",
            "updated_at": _now_iso(),
        }

    def list_profiles(self, owner: str) -> list[dict[str, Any]]:
        _require_owner(owner)
        return [
            json.loads(item["view"])
            for (o, sk), item in sorted(self._items.items())
            if o == owner and sk.startswith(PROFILE_PREFIX)
        ]


    def put_precedent_item(self, sk: str, document: dict[str, Any]) -> None:
        self._items[(PRECEDENT_OWNER, sk)] = {
            "view": json.dumps(document, sort_keys=True, ensure_ascii=False),
            "status": "precedent",
            "updated_at": _now_iso(),
        }

    def list_precedent_items(self, sk_prefix: str) -> list[dict[str, Any]]:
        return [
            json.loads(item["view"])
            for (o, sk), item in sorted(self._items.items())
            if o == PRECEDENT_OWNER and sk.startswith(sk_prefix)
        ]


class DynamoSessionStore:
    """DynamoDB table: ``owner`` (HASH), ``sk`` (RANGE), ``view``, ``status``, ``updated_at``, ``ttl``."""

    def __init__(self, table_name: str, client: Any = None, clock=time.time) -> None:
        if client is None:
            import boto3

            client = boto3.client("dynamodb")
        self._table = table_name
        self._client = client
        self._clock = clock

    def put_view(self, owner: str, view: SessionView) -> None:
        _require_owner(owner)
        ttl = int(self._clock()) + SESSION_TTL_SECONDS
        # if_not_exists keeps ttl at creation plus 7 days across later stage updates.
        self._client.update_item(
            TableName=self._table,
            Key={"owner": {"S": owner}, "sk": {"S": SESSION_PREFIX + view.session_id}},
            UpdateExpression=(
                "SET #v = :v, #s = :s, updated_at = :u, #t = if_not_exists(#t, :t)"
            ),
            ExpressionAttributeNames={"#v": "view", "#s": "status", "#t": "ttl"},
            ExpressionAttributeValues={
                ":v": {"S": session_view_to_json(view)},
                ":s": {"S": view.status},
                ":u": {"S": _now_iso()},
                ":t": {"N": str(ttl)},
            },
        )

    def get_view(self, owner: str, session_id: str) -> SessionView | None:
        _require_owner(owner)
        resp = self._client.get_item(
            TableName=self._table,
            Key={"owner": {"S": owner}, "sk": {"S": SESSION_PREFIX + session_id}},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if not item:
            return None
        # DynamoDB TTL deletion lags; hide expired items meanwhile.
        ttl = item.get("ttl", {}).get("N")
        if ttl is not None and int(ttl) <= self._clock():
            return None
        return session_view_from_json(item["view"]["S"])

    def put_profile(self, owner: str, profile: dict[str, Any]) -> None:
        _require_owner(owner)
        self._client.put_item(
            TableName=self._table,
            Item={
                "owner": {"S": owner},
                "sk": {"S": PROFILE_PREFIX + _profile_id(profile)},
                "view": {"S": json.dumps(profile, sort_keys=True, ensure_ascii=False)},
                "status": {"S": "saved"},
                "updated_at": {"S": _now_iso()},
            },
        )

    def list_profiles(self, owner: str) -> list[dict[str, Any]]:
        _require_owner(owner)
        profiles: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {
            "TableName": self._table,
            "KeyConditionExpression": "#o = :o AND begins_with(sk, :p)",
            "ExpressionAttributeNames": {"#o": "owner"},
            "ExpressionAttributeValues": {":o": {"S": owner}, ":p": {"S": PROFILE_PREFIX}},
        }
        while True:
            resp = self._client.query(**kwargs)
            profiles.extend(json.loads(i["view"]["S"]) for i in resp.get("Items", []))
            last = resp.get("LastEvaluatedKey")
            if not last:
                return profiles
            kwargs["ExclusiveStartKey"] = last

    def put_precedent_item(self, sk: str, document: dict[str, Any]) -> None:
        self._client.put_item(
            TableName=self._table,
            Item={
                "owner": {"S": PRECEDENT_OWNER},
                "sk": {"S": sk},
                "view": {"S": json.dumps(document, sort_keys=True, ensure_ascii=False)},
                "status": {"S": "precedent"},
                "updated_at": {"S": _now_iso()},
            },
        )

    def list_precedent_items(self, sk_prefix: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {
            "TableName": self._table,
            "KeyConditionExpression": "#o = :o AND begins_with(sk, :p)",
            "ExpressionAttributeNames": {"#o": "owner"},
            "ExpressionAttributeValues": {
                ":o": {"S": PRECEDENT_OWNER},
                ":p": {"S": sk_prefix},
            },
        }
        while True:
            resp = self._client.query(**kwargs)
            items.extend(json.loads(i["view"]["S"]) for i in resp.get("Items", []))
            last = resp.get("LastEvaluatedKey")
            if not last:
                return items
            kwargs["ExclusiveStartKey"] = last
