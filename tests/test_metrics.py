"""Unit tests for Toolkit metrics (hand-computed values and the Robert oracle)."""
from __future__ import annotations

import math
from datetime import date, datetime, timezone

import pandas as pd
import pytest

from guide.data.loader import LocalSource
from guide.data.snapshot import SnapshotInfo
from guide.toolkit import metrics
from guide.toolkit.exhibits import ExhibitRegistry


def _info(coverage_end: date) -> SnapshotInfo:
    return SnapshotInfo(
        snapshot_id="20261113T000000Z-test",
        source="starter",
        retrieved_at=datetime(2026, 11, 13, tzinfo=timezone.utc),
        coverage_end=coverage_end,
        served_from="primary",
        fallback_cause=None,
    )


class _Source:
    """Test adapter exposing in-memory or CSV tables through ``read_table``."""

    def __init__(self, tables: dict[str, pd.DataFrame], coverage_end: date) -> None:
        self.tables = tables
        self.snapshot = _info(coverage_end)

    def read_table(self, table: str) -> pd.DataFrame:
        return self.tables[table].copy()


def _small_source(n: int = 25) -> _Source:
    dates = pd.bdate_range("2024-01-02", periods=n)
    rows = []
    for i, d in enumerate(dates):
        rows.append({"date": d.date(), "ticker": "AAA.TO", "adj_close": 100.0 * (1.01 ** i)})
        rows.append({"date": d.date(), "ticker": "BBB.TO", "adj_close": 50.0 * (0.99 ** i)})
    universe = pd.DataFrame(
        {"ticker": ["AAA.TO", "BBB.TO", "CNQ.TO"], "currency": ["CAD", "CAD", "CAD"]}
    )
    return _Source(
        {"assets_universe": universe, "prices_daily": pd.DataFrame(rows)}, dates[-1].date()
    )


def test_annualized_return_and_volatility_hand_computed():
    src, reg = _small_source(), ExhibitRegistry()
    n = 24  # returns
    ret = metrics.annualized_return(reg, src, "AAA.TO", date(2024, 1, 1), date(2025, 1, 1))
    assert ret.value == pytest.approx(1.01 ** 252 - 1)
    assert n == 24
    vol = metrics.annualized_volatility(reg, src, "AAA.TO", date(2024, 1, 1), date(2025, 1, 1))
    assert vol.value == pytest.approx(0.0, abs=1e-12)
    assert (ret.number, vol.number) == (1, 2)
    assert ret.currency == "CAD"


def test_max_drawdown_has_peak_and_trough_():
    src, reg = _small_source(), ExhibitRegistry()
    dd = metrics.max_drawdown(reg, src, "BBB.TO", date(2024, 1, 1), date(2025, 1, 1))
    assert dd.value["value"] == pytest.approx(0.99 ** 24 - 1)
    assert dd.value["peak_date"] == "2024-01-02"
    corr = metrics.correlation(reg, src, "AAA.TO", "BBB.TO", date(2024, 1, 1), date(2025, 1, 1))
    assert -1.0 <= corr.value <= 1.0


def test_correlation_of_asset_with_its_square_is_near_one():
    dates = pd.bdate_range("2024-01-02", periods=30)
    price = [100.0 * (1.02 if i % 2 else 0.99) ** (i + 1) for i in range(30)]
    rows = []
    for d, p in zip(dates, price):
        rows.append({"date": d.date(), "ticker": "AAA.TO", "adj_close": p})
        rows.append({"date": d.date(), "ticker": "BBB.TO", "adj_close": p * p / 100})
    src = _Source(
        {
            "assets_universe": pd.DataFrame({"ticker": ["AAA.TO", "BBB.TO"], "currency": ["CAD", "CAD"]}),
            "prices_daily": pd.DataFrame(rows),
        },
        dates[-1].date(),
    )
    corr = metrics.correlation(ExhibitRegistry(), src, "AAA.TO", "BBB.TO", date(2024, 1, 1), date(2025, 1, 1))
    assert corr.value > 0.95


def test_portfolio_metrics_matches_single_asset_when_fully_weighted():
    src, reg = _small_source(), ExhibitRegistry()
    pm = metrics.portfolio_metrics(reg, src, {"AAA.TO": 1.0}, date(2024, 1, 1), date(2025, 1, 1))
    assert pm.value["annualized_return"] == pytest.approx(1.01 ** 252 - 1)
    assert pm.value["max_drawdown"] == pytest.approx(0.0)


def test_errors_create_no_exhibit():
    src, reg = _small_source(), ExhibitRegistry()
    start, end = date(2024, 1, 1), date(2025, 1, 1)
    assert metrics.annualized_return(reg, src, "NOPE", start, end).code == metrics.UNKNOWN_TICKER
    # CNQ.TO is in the universe but has no prices.
    assert metrics.annualized_return(reg, src, "CNQ.TO", start, end).code == metrics.INSUFFICIENT_DATA
    short = metrics.annualized_return(reg, src, "AAA.TO", start, date(2024, 1, 15))
    assert short.code == metrics.INSUFFICIENT_DATA
    assert metrics.portfolio_metrics(reg, src, {"AAA.TO": 0.5}, start, end).code == metrics.INVALID_ARGUMENT
    assert len(reg) == 0


def test_no_observation_after_as_of_is_used_and_coverage_note_added():
    src, reg = _small_source(30), ExhibitRegistry()
    as_of = date(2024, 1, 31)
    ex = metrics.annualized_return(reg, src, "AAA.TO", date(2024, 1, 1), date(2025, 1, 1), as_of)
    assert ex.period_end <= as_of
    late = metrics.annualized_return(
        reg, src, "AAA.TO", date(2024, 1, 1), date(2030, 1, 1), date(2030, 1, 1)
    )
    assert any("data available up to" in note for note in late.processing_notes)


def test_cnq_note_added_when_period_includes_split_date():
    dates = pd.bdate_range("2022-08-01", periods=30)
    rows = [{"date": d.date(), "ticker": "CNQ.TO", "adj_close": 40.0 + i * 0.1} for i, d in enumerate(dates)]
    src = _Source(
        {
            "assets_universe": pd.DataFrame({"ticker": ["CNQ.TO"], "currency": ["CAD"]}),
            "prices_daily": pd.DataFrame(rows),
        },
        dates[-1].date(),
    )
    ex = metrics.annualized_volatility(ExhibitRegistry(), src, "CNQ.TO", date(2022, 8, 1), date(2022, 12, 31))
    assert any("CNQ.TO 2022-08-22" in note for note in ex.processing_notes)


class _CsvSource(_Source):
    def __init__(self) -> None:
        local = LocalSource()
        super().__init__(
            {
                "assets_universe": local.read_csv("assets_universe.csv"),
                "prices_daily": local.read_csv("prices_daily.csv"),
                "fx_usdcad_daily": local.read_csv("fx_usdcad_daily.csv"),
            },
            date(2026, 11, 12),
        )


def test_robert_oracle_on_starter_data():
    src, reg = _CsvSource(), ExhibitRegistry()
    base = {"XBB.TO": 0.40, "ZST.TO": 0.15, "XIU.TO": 0.15, "SPY": 0.15, "JNJ": 0.08, "RY.TO": 0.07}
    start, end = date(2021, 11, 12), date(2026, 11, 12)
    b = metrics.portfolio_metrics(reg, src, base, start, end)
    assert round(b.value["annualized_volatility"], 3) == 0.065
    assert round(b.value["max_drawdown"], 3) == -0.104
    tsla = {k: v * 0.7 for k, v in base.items()} | {"TSLA": 0.30}
    t = metrics.portfolio_metrics(reg, src, tsla, start, end)
    assert round(t.value["annualized_volatility"], 3) == 0.201
    assert round(t.value["max_drawdown"], 3) == -0.301
    assert math.isfinite(t.value["annualized_return"])


def test_risk_contribution_and_comparison_on_starter_data():
    src, reg = _CsvSource(), ExhibitRegistry()
    base = {"XBB.TO": 0.40, "ZST.TO": 0.15, "XIU.TO": 0.15, "SPY": 0.15, "JNJ": 0.08, "RY.TO": 0.07}
    tsla = {k: v * 0.7 for k, v in base.items()} | {"TSLA": 0.30}
    start, end = date(2021, 11, 12), date(2026, 11, 12)
    rc = metrics.risk_contribution(reg, src, tsla, start, end)
    shares = rc.value["share_of_variance_pct"]
    assert abs(shares["TSLA"] - 86.7) < 1.0
    assert abs(sum(shares.values()) - 100.0) < 1e-6
    cmp = metrics.portfolio_comparison(reg, src, base, tsla, start, end)
    assert round(cmp.value["proposed"]["max_drawdown"], 3) == -0.301
    assert cmp.value["base"]["return_2022"] is not None
    assert cmp.value["proposed"]["worst_rolling_252d_return"] < 0


def test_max_weight_within_contract_returns_grid_exhibit_or_error():
    from tests.test_rules import _persona

    src, reg = _CsvSource(), ExhibitRegistry()
    contract, base = _persona("robert")
    start, end = date(2021, 11, 12), date(2026, 11, 12)
    ex = metrics.max_weight_within_contract(reg, src, "TSLA", contract, base, start, end)
    assert ex.value["max_weight"] == 0.05
    assert len(reg) == 1  # search evaluations leave no Exhibits
    err = metrics.max_weight_within_contract(reg, src, "NOPE", contract, base, start, end)
    assert isinstance(err, metrics.ToolError) and len(reg) == 1
