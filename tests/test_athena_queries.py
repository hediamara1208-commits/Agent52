import pytest

from athena.queries import (
    AthenaQueryError, EXPLORATION_QUERY_NAMES, VALIDATION_QUERY_NAMES,
    available_queries, build_query, run_query, validation_queries,
)
from guide.config import load_config

SID = "20240102T030405Z-abc123"


def test_every_query_is_snapshot_scoped_and_parameterized():
    for name in available_queries():
        q = build_query(name, SID)
        assert "snapshot_id = ?" in q.sql
        assert SID not in q.sql
        assert len(q.execution_parameters) == q.sql.count("?")


def test_validation_and_exploration_sets_exist():
    assert set(VALIDATION_QUERY_NAMES) | set(EXPLORATION_QUERY_NAMES) <= set(available_queries())
    assert len(validation_queries(SID)) == len(VALIDATION_QUERY_NAMES)


@pytest.mark.parametrize("bad", ["", "x'; DROP TABLE t;--", "20240102T030405Z-ABC", "20240102T030405Z-a\n"])
def test_bad_snapshot_ids_rejected(bad):
    with pytest.raises(ValueError):
        build_query("check_adj_close_non_positive", bad)


def test_unknown_query_rejected():
    with pytest.raises(ValueError):
        build_query("../etc/passwd", SID)


class FakeAthena:
    def __init__(self, state="SUCCEEDED"):
        self.started = None
        self.state = state
        self.stopped = False

    def start_query_execution(self, **kw):
        self.started = kw
        return {"QueryExecutionId": "q1"}

    def get_query_execution(self, **kw):
        return {"QueryExecution": {"Status": {"State": self.state}}}

    def stop_query_execution(self, **kw):
        self.stopped = True

    def get_query_results(self, **kw):
        return {"ResultSet": {"Rows": [{"Data": [{"VarCharValue": "n"}]}, {"Data": [{"VarCharValue": "3"}]}]}}


def test_run_query_uses_workgroup_and_parameters():
    fake = FakeAthena()
    cfg = load_config()
    rows = run_query(fake, build_query("check_adj_close_non_positive", SID), cfg)
    assert rows == [{"n": "3"}]
    assert fake.started["WorkGroup"] == cfg.athena_workgroup
    assert fake.started["ExecutionParameters"] == [f"'{SID}'"]


def test_run_query_times_out_and_stops():
    fake = FakeAthena(state="RUNNING")
    with pytest.raises(AthenaQueryError):
        run_query(fake, build_query("check_adj_close_non_positive", SID), load_config(),
                  timeout_seconds=0, poll_seconds=0)
    assert fake.stopped
