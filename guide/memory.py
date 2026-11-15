"""Session memory for the Guide, wrapping Amazon Bedrock AgentCore Memory (Req. 8.4).

Entries are keyed by user and profile: the AgentCore ``actorId`` is
``{user_id}/{profile_id}`` (``user_id`` is the Cognito user identifier, Req. 23.4)
so a store only reads and writes its own caller's entries. The entry kind (``contract`` or ``summary``) is the
``sessionId``. Every save appends an event; a load returns the newest one.
Credentials come from the default AWS credential chain.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping

from guide.config import Config

CONTRACT_KIND = "contract"
SUMMARY_KIND = "summary"


class MemoryError(RuntimeError):
    """Raised when AgentCore Memory is not configured or a call fails."""


class MemoryStore:
    """Save and load Investor_Contracts and summaries for one user's profiles."""

    def __init__(self, config: Config, user_id: str, client: Any | None = None) -> None:
        self._user_id = self._check_part(user_id, "user_id")
        if not config.agentcore_memory_id:
            raise MemoryError("agentcore_memory_id is not configured")
        self._memory_id = config.agentcore_memory_id
        if client is None:
            import boto3

            client = boto3.client("bedrock-agentcore", region_name=config.aws_region)
        self._client = client

    @staticmethod
    def _check_part(value: str, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a non-empty string")
        if "/" in value:
            raise ValueError(f"{name} must not contain '/'")
        return value

    def _check_profile(self, profile_id: str) -> str:
        """Return the ``{user_id}/{profile_id}`` key for ``profile_id``."""
        return f"{self._user_id}/{self._check_part(profile_id, 'profile_id')}"

    def _put(self, profile_id: str, kind: str, document: Any) -> None:
        try:
            self._client.create_event(
                memoryId=self._memory_id,
                actorId=self._check_profile(profile_id),
                sessionId=kind,
                eventTimestamp=datetime.now(timezone.utc),
                payload=[{"blob": json.dumps(document, sort_keys=True)}],
            )
        except ValueError:
            raise
        except Exception as exc:  # boto errors carry no secrets; keep type only
            raise MemoryError(f"memory save failed: {type(exc).__name__}") from exc

    def _latest(self, profile_id: str, kind: str) -> Any | None:
        newest: Mapping[str, Any] | None = None
        token: str | None = None
        try:
            while True:
                kwargs: dict[str, Any] = {
                    "memoryId": self._memory_id,
                    "actorId": self._check_profile(profile_id),
                    "sessionId": kind,
                    "includePayloads": True,
                }
                if token:
                    kwargs["nextToken"] = token
                page = self._client.list_events(**kwargs)
                for event in page.get("events", []):
                    if newest is None or event["eventTimestamp"] >= newest["eventTimestamp"]:
                        newest = event
                token = page.get("nextToken")
                if not token:
                    break
        except ValueError:
            raise
        except Exception as exc:
            raise MemoryError(f"memory load failed: {type(exc).__name__}") from exc
        if newest is None:
            return None
        for item in newest.get("payload", []):
            if "blob" in item:
                blob = item["blob"]
                return json.loads(blob) if isinstance(blob, str) else blob
        return None

    def save_contract(self, profile_id: str, contract: Mapping[str, Any]) -> None:
        """Store the Investor_Contract for ``profile_id``."""
        self._put(profile_id, CONTRACT_KIND, dict(contract))

    def save_summary(self, profile_id: str, summary: str | Mapping[str, Any]) -> None:
        """Store a session summary for ``profile_id``."""
        self._put(profile_id, SUMMARY_KIND, summary)

    def load_contract(self, profile_id: str) -> dict[str, Any] | None:
        """Return the latest saved contract, or ``None`` if there is none."""
        return self._latest(profile_id, CONTRACT_KIND)
