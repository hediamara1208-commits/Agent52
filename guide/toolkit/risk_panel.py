"""Risk_Panel: the fixed Exhibit set computed by code for every Option (Req. 4.3, 28.3 to 28.5).

Exhibits, in order: ``portfolio_comparison`` (volatility, maximum drawdown, worst rolling
252-day return, 2022 return of base and proposed), ``risk_contribution`` (share of variance per
asset), ``currency_exposure``, ``sector_weights``, ``correlation_with_base`` and
``max_weight_within_contract``. No agent computes any of these figures.

An Option is a mapping ``{"id", "ticker", "weight", "start", "end", "as_of"}``; ``start`` and
``end`` fall back to the contract. The proposed portfolio is Base_Portfolio x (1 - weight) plus
``weight`` in ``ticker`` (same construction as ``rules.proposed_portfolio``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping

import pandas as pd

from guide.data.loader import DataSource
from guide.toolkit import metrics
from guide.toolkit.exhibits import Exhibit, ExhibitRegistry
from guide.toolkit.metrics import ToolError

PANEL_KEYS = (
    "portfolio_comparison",
    "risk_contribution",
    "currency_exposure",
    "sector_weights",
    "correlation_with_base",
    "max_weight_within_contract",
)
UNCLASSIFIED = "Unclassified"


@dataclass
class RiskPanel:
    """One entry per key of ``PANEL_KEYS``; a failed computation keeps its ``ToolError``."""

    option_id: str | None
    items: dict[str, Exhibit | ToolError] = field(default_factory=dict)

    @property
    def exhibit_numbers(self) -> list[int]:
        return [e.number for e in self.items.values() if isinstance(e, Exhibit)]

    @property
    def errors(self) -> dict[str, ToolError]:
        return {k: v for k, v in self.items.items() if isinstance(v, ToolError)}


def _base_portfolio(contract: Mapping[str, Any]) -> Mapping[str, float] | None:
    base = contract.get("base_portfolio")
    if isinstance(base, Mapping) and isinstance(base.get("value"), Mapping):
        base = base["value"]
    return base if isinstance(base, Mapping) and base else None


def _proposed(base: Mapping[str, float], ticker: str, weight: float) -> dict[str, float]:
    weights = {t: w * (1.0 - weight) for t, w in base.items()}
    weights[ticker] = weights.get(ticker, 0.0) + weight
    return {t: w for t, w in weights.items() if w > 0}


def _group(weights: Mapping[str, float], labels: Mapping[str, str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for ticker, weight in weights.items():
        label = labels.get(ticker)
        key = UNCLASSIFIED if label is None or pd.isna(label) or label == "" else str(label)
        out[key] = out.get(key, 0.0) + float(weight)
    return dict(sorted(out.items()))


def _grouped_exhibit(
    registry: ExhibitRegistry,
    source: DataSource,
    metric: str,
    column: str,
    base: Mapping[str, float],
    proposed: Mapping[str, float],
    ticker: str,
    weight: float,
    start: date,
    end: date,
    as_of: date | None,
    currency: str,
    note: str,
) -> Exhibit | ToolError:
    universe = source.read_table(metrics.UNIVERSE_TABLE)
    labels = dict(zip(universe["ticker"], universe[column]))
    unknown = sorted(t for t in set(base) | set(proposed) if t not in labels)
    if unknown:
        return ToolError(metrics.UNKNOWN_TICKER, ", ".join(unknown))
    value = {"base": _group(base, labels), "proposed": _group(proposed, labels)}
    return registry.add(
        metric=metric,
        value=value,
        period_start=start,
        period_end=end,
        assets=tuple(sorted(set(base) | set(proposed))),
        currency=currency,
        source_files=(metrics.UNIVERSE_TABLE,),
        processing_notes=(note,),
        inputs=metrics._inputs(
            as_of, ticker=ticker, weight=float(weight), start=start, end=end,
            base={t: float(w) for t, w in sorted(base.items())},
        ),
    )


def _correlation_with_base(
    registry: ExhibitRegistry,
    source: DataSource,
    base: Mapping[str, float],
    ticker: str,
    start: date,
    end: date,
    as_of: date | None,
) -> Exhibit | ToolError:
    """Pearson correlation of the added asset's daily returns with the Base_Portfolio's."""
    tickers = sorted(set(base) | {ticker})
    panel = metrics._load_panel(source, tickers, start, end, as_of)
    if isinstance(panel, ToolError):
        return panel
    base_returns = metrics._portfolio_returns(panel.prices, {t: base.get(t, 0.0) for t in tickers})
    asset_returns = metrics._returns(panel.prices)[ticker]
    value = float(asset_returns.corr(base_returns))
    if math.isnan(value):
        return ToolError(metrics.INSUFFICIENT_DATA, "correlation with the base portfolio is undefined")
    panel.notes.append(
        f"Correlation of {ticker} daily returns with the daily-rebalanced Base_Portfolio returns."
    )
    inputs = metrics._inputs(
        as_of, ticker=ticker, start=start, end=end,
        base={t: float(w) for t, w in sorted(base.items())},
    )
    return metrics._register(registry, "correlation_with_base", value, panel, tickers, inputs)


def risk_panel(
    option: Mapping[str, Any],
    contract: Mapping[str, Any],
    *,
    registry: ExhibitRegistry,
    source: DataSource,
) -> RiskPanel | ToolError:
    """Compute the fixed Risk_Panel Exhibits of one Option.

    Returns a ``ToolError`` only when the Option or contract is unusable; individual
    metric failures are kept in ``RiskPanel.items`` and create no Exhibit.
    """
    ticker, weight = option.get("ticker"), option.get("weight")
    if not isinstance(ticker, str) or not ticker:
        return ToolError(metrics.INVALID_ARGUMENT, "option needs a ticker")
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= weight <= 1:
        return ToolError(metrics.INVALID_ARGUMENT, "option weight must be a number in [0, 1]")
    base = _base_portfolio(contract)
    if base is None:
        return ToolError(metrics.INVALID_ARGUMENT, "contract has no base_portfolio")
    if (error := metrics._check_weights(base, "base_portfolio")) is not None:
        return error
    start_raw = option.get("start", contract.get("start"))
    end_raw = option.get("end", contract.get("end"))
    as_of = option.get("as_of", contract.get("as_of"))
    if start_raw is None or end_raw is None:
        return ToolError(metrics.INVALID_ARGUMENT, "option needs start and end dates")
    try:
        start, end = metrics._to_date(start_raw), metrics._to_date(end_raw)
        as_of = None if as_of is None else metrics._to_date(as_of)
    except (TypeError, ValueError):
        return ToolError(metrics.INVALID_ARGUMENT, "start, end and as_of must be valid dates")
    if start > end:
        return ToolError(metrics.INVALID_ARGUMENT, f"start {start} is after end {end}")
    if ticker not in set(source.read_table(metrics.UNIVERSE_TABLE)["ticker"]):
        return ToolError(metrics.UNKNOWN_TICKER, ticker)

    weight = float(weight)
    proposed = _proposed(base, ticker, weight)
    panel = RiskPanel(option.get("id"))
    items = panel.items
    items["portfolio_comparison"] = metrics.portfolio_comparison(
        registry, source, base, proposed, start, end, as_of
    )
    items["risk_contribution"] = metrics.risk_contribution(
        registry, source, proposed, start, end, as_of
    )
    items["currency_exposure"] = _grouped_exhibit(
        registry, source, "currency_exposure", "currency", base, proposed, ticker, weight,
        start, end, as_of, "CAD",
        "Share of portfolio weight by listing currency of each asset (before conversion to CAD).",
    )
    items["sector_weights"] = _grouped_exhibit(
        registry, source, "sector_weights", "sector", base, proposed, ticker, weight,
        start, end, as_of, "CAD",
        "Share of portfolio weight by sector in assets_universe; assets without a sector are Unclassified.",
    )
    items["correlation_with_base"] = _correlation_with_base(
        registry, source, base, ticker, start, end, as_of
    )
    items["max_weight_within_contract"] = metrics.max_weight_within_contract(
        registry, source, ticker, contract, base, start, end, as_of
    )
    return panel
