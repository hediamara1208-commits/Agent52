"""Snapshot-scoped Athena queries (Req. 19.2, 19.5, 19.6, 19.7).

Queries live in ``athena/sql/*.sql``. Every query filters on ``snapshot_id = ?``
and the id is passed through ``ExecutionParameters``; it is never concatenated
into the SQL text. Ids that do not match ``SNAPSHOT_ID_RE`` are rejected first.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from guide.data.parquet_io import TABLE_SCHEMAS
from guide.data.snapshot import SNAPSHOT_ID_RE

SQL_DIR = Path(__file__).with_name("sql")

VALIDATION_QUERY_NAMES: tuple[str, ...] = (
    *(f"check_row_count_{t}" for t in TABLE_SCHEMAS),
    *(f"check_duplicates_{t}" for t in TABLE_SCHEMAS),
    "check_ticker_set_equality",
    "check_adj_close_non_positive",
    "check_currency_mismatch",
)
EXPLORATION_QUERY_NAMES: tuple[str, ...] = tuple(f"explore_{t}" for t in TABLE_SCHEMAS)

DEFAULT_TIMEOUT_SECONDS = 60.0


class AthenaQueryError(RuntimeError):
    """Raised when a query fails, is cancelled, or times out."""


@dataclass(frozen=True)
class AthenaQuery:
    name: str
    sql: str
    execution_parameters: tuple[str, ...]


def available_queries() -> list[str]:
    return sorted(p.stem for p in SQL_DIR.glob("*.sql"))


def build_query(name: str, snapshot_id: str) -> AthenaQuery:
    if not isinstance(snapshot_id, str) or not SNAPSHOT_ID_RE.fullmatch(snapshot_id):
        raise ValueError("snapshot_id does not match the Snapshot_Id format")
    if not isinstance(name, str) or name not in available_queries():
        raise ValueError(f"unknown saved query: {name!r}")
    sql = (SQL_DIR / f"{name}.sql").read_text(encoding="utf-8").strip()
    placeholders = sql.count("?")
    if placeholders == 0:
        raise ValueError(f"saved query {name!r} is not snapshot-scoped")
    # Athena expects varchar execution parameters as SQL string literals. The id
    # is regex-validated (no quotes possible), so the literal is safe.
    return AthenaQuery(name, sql, (f"'{snapshot_id}'",) * placeholders)


def validation_queries(snapshot_id: str) -> list[AthenaQuery]:
    return [build_query(name, snapshot_id) for name in VALIDATION_QUERY_NAMES]


def run_query(
    athena: Any,
    query: AthenaQuery,
    config: Any,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_seconds: float = 1.0,
) -> list[dict[str, str]]:
    """Run a query in the configured workgroup and return rows as dicts."""
    started = athena.start_query_execution(
        QueryString=query.sql,
        ExecutionParameters=list(query.execution_parameters),
        QueryExecutionContext={"Database": config.glue_database},
        WorkGroup=config.athena_workgroup,
    )
    execution_id = started["QueryExecutionId"]
    deadline = time.monotonic() + timeout_seconds
    while True:
        status = athena.get_query_execution(QueryExecutionId=execution_id)["QueryExecution"]["Status"]
        state = status["State"]
        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            reason = status.get("StateChangeReason", "no reason given")
            raise AthenaQueryError(f"query {query.name} {state.lower()}: {reason}")
        if time.monotonic() >= deadline:
            try:
                athena.stop_query_execution(QueryExecutionId=execution_id)
            except Exception:  # best effort; the timeout is the error that matters
                pass
            raise AthenaQueryError(f"query {query.name} timed out after {timeout_seconds}s")
        time.sleep(poll_seconds)

    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"QueryExecutionId": execution_id}
        if token:
            kwargs["NextToken"] = token
        page = athena.get_query_results(**kwargs)
        for row in page["ResultSet"]["Rows"]:
            values = [d.get("VarCharValue", "") for d in row["Data"]]
            if header is None:
                header = values
            else:
                rows.append(dict(zip(header, values)))
        token = page.get("NextToken")
        if not token:
            return rows
