import json

import boto3
import pytest
from botocore.stub import ANY, Stubber

from guide.session.store import (
    SESSION_TTL_SECONDS,
    DynamoSessionStore,
    InMemorySessionStore,
    SessionSink,
    StoreSink,
)
from guide.tribunal.session_view import new_session_view, session_view_to_json

NOW = 1_000_000.0


def _view(sid="s1", status="running"):
    v = new_session_view(sid)
    v.status = status
    return v


def test_in_memory_owner_isolation_and_sink():
    store = InMemorySessionStore(clock=lambda: NOW)
    sink = StoreSink(store, "alice")
    assert isinstance(sink, SessionSink)
    sink.publish(_view("s1"))
    sink.publish(_view("s1", "completed"))
    assert store.get_view("alice", "s1").status == "completed"
    assert store.get_view("bob", "s1") is None


def test_in_memory_ttl_fixed_at_creation_and_expiry():
    t = [NOW]
    store = InMemorySessionStore(clock=lambda: t[0])
    store.put_view("alice", _view())
    t[0] = NOW + SESSION_TTL_SECONDS - 1
    store.put_view("alice", _view(status="completed"))  # update must not extend ttl
    assert store.get_view("alice", "s1") is not None
    t[0] = NOW + SESSION_TTL_SECONDS
    assert store.get_view("alice", "s1") is None


def test_in_memory_profiles_per_owner():
    store = InMemorySessionStore()
    store.put_profile("alice", {"profile_id": "p1", "values": {"a": 1}})
    store.put_profile("bob", {"profile_id": "p2", "values": {}})
    store.put_view("alice", _view())
    assert [p["profile_id"] for p in store.list_profiles("alice")] == ["p1"]
    with pytest.raises(ValueError):
        store.put_profile("alice", {"values": {}})
    with pytest.raises(ValueError):
        store.get_view("", "s1")


@pytest.fixture
def dynamo():
    client = boto3.client(
        "dynamodb",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )
    with Stubber(client) as stub:
        yield DynamoSessionStore("tbl", client=client, clock=lambda: NOW), stub


def test_dynamo_put_view_sets_ttl_if_not_exists(dynamo):
    store, stub = dynamo
    stub.add_response(
        "update_item",
        {},
        {
            "TableName": "tbl",
            "Key": {"owner": {"S": "alice"}, "sk": {"S": "session#s1"}},
            "UpdateExpression": (
                "SET #v = :v, #s = :s, updated_at = :u, #t = if_not_exists(#t, :t)"
            ),
            "ExpressionAttributeNames": {"#v": "view", "#s": "status", "#t": "ttl"},
            "ExpressionAttributeValues": {
                ":v": {"S": session_view_to_json(_view())},
                ":s": {"S": "running"},
                ":u": {"S": ANY},
                ":t": {"N": str(int(NOW) + SESSION_TTL_SECONDS)},
            },
        },
    )
    store.put_view("alice", _view())
    stub.assert_no_pending_responses()


def test_dynamo_get_view_uses_caller_owner_and_hides_foreign(dynamo):
    store, stub = dynamo
    key = {"owner": {"S": "bob"}, "sk": {"S": "session#s1"}}
    stub.add_response(
        "get_item", {}, {"TableName": "tbl", "Key": key, "ConsistentRead": True}
    )
    assert store.get_view("bob", "s1") is None
    item = {
        "owner": {"S": "alice"},
        "sk": {"S": "session#s1"},
        "view": {"S": session_view_to_json(_view("s1", "completed"))},
        "ttl": {"N": str(int(NOW) + 10)},
    }
    stub.add_response(
        "get_item",
        {"Item": item},
        {
            "TableName": "tbl",
            "Key": {"owner": {"S": "alice"}, "sk": {"S": "session#s1"}},
            "ConsistentRead": True,
        },
    )
    assert store.get_view("alice", "s1").status == "completed"
    item["ttl"] = {"N": str(int(NOW))}
    stub.add_response("get_item", {"Item": item})
    assert store.get_view("alice", "s1") is None


def test_dynamo_profiles_put_and_list_paginated(dynamo):
    store, stub = dynamo
    profile = {"profile_id": "p1", "owner": "alice", "base_persona_id": None, "values": {}}
    stub.add_response(
        "put_item",
        {},
        {
            "TableName": "tbl",
            "Item": {
                "owner": {"S": "alice"},
                "sk": {"S": "profile#p1"},
                "view": {"S": json.dumps(profile, sort_keys=True)},
                "status": {"S": "saved"},
                "updated_at": {"S": ANY},
            },
        },
    )
    store.put_profile("alice", profile)
    last = {"owner": {"S": "alice"}, "sk": {"S": "profile#p1"}}
    stub.add_response(
        "query",
        {"Items": [{"view": {"S": json.dumps(profile)}}], "LastEvaluatedKey": last},
    )
    stub.add_response(
        "query",
        {"Items": [{"view": {"S": json.dumps({**profile, "profile_id": "p2"})}}]},
    )
    assert [p["profile_id"] for p in store.list_profiles("alice")] == ["p1", "p2"]
