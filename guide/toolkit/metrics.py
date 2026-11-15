"""Deterministic Toolkit metrics (Req. 2.1, 2.2, 2.4 to 2.7, 3.1 to 3.3, 3.6, 3.7, 3.12).

Every public function returns an ``Exhibit`` registered in the session's
``ExhibitRegistry``, or a ``ToolError`` that creates no Exhibit. Tables are read
only through a ``DataSource`` (a ``PinnedSnapshot``, or a test adapter exposing
``snapshot`` and ``read_table``).

Shared pipeline: ticker check, as-of and coverage-end filter, USD to CAD
conversion, date-intersection alignment, 20-observation check, adj_close simple
returns (ratios only), CNQ.TO note, then registration.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from guide.data import quality
from guide.data.loader import DataSource
from guide.toolkit import align
from guide.toolkit.exhibits import Exhibit, ExhibitRegistry

TRADING_DAYS_PER_YEAR = 252
MIN_OBSERVATIONS = 20
WEIGHT_TOLERANCE = 1e-6

UNIVERSE_TABLE = "assets_universe"
PRICES_TABLE = "prices_daily"
FX_TABLE = "fx_usdcad_daily"

UNKNOWN_TICKER = "UNKNOWN_TICKER"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
INVALID_ARGUMENT = "INVALID_ARGUMENT"
UNSUPPORTED_CURRENCY = "UNSUPPORTED_CURRENCY"

_YEAR_RE = re.compile(r"^(\d{4})$")


@dataclass(frozen=True)
class ToolError:
    """A Toolkit failure. It never touches the registry."""

    code: str
    detail: str

    @property
    def message(self) -> str:
        return f"{self.code}: {self.detail}"

    def to_dict(self) -> dict[str, str]:
        return {"error": self.code, "detail": self.detail}


@dataclass(frozen=True)
class _Panel:
    """Aligned CAD adj_close prices and the notes produced while building them."""

    prices: pd.DataFrame
    notes: list[str]
    source_files: list[str]
    period_start: date
    period_end: date


def _to_date(value: date | str | pd.Timestamp) -> date:
    return pd.Timestamp(value).date()


def _load_panel(
    source: DataSource,
    tickers: Sequence[str],
    start: date,
    end: date,
    as_of: date | None,
) -> _Panel | ToolError:
    try:
        start, end = _to_date(start), _to_date(end)
        cutoff = None if as_of is None else _to_date(as_of)
    except (TypeError, ValueError):
        return ToolError(INVALID_ARGUMENT, "start, end and as_of must be valid dates")
    if start > end:
        return ToolError(INVALID_ARGUMENT, f"start {start} is after end {end}")

    snapshot = source.snapshot

    # 1. Ticker check against the pinned snapshot's universe.
    universe = source.read_table(UNIVERSE_TABLE)
    known = set(universe["ticker"])
    for ticker in tickers:
        if ticker not in known:
            return ToolError(UNKNOWN_TICKER, ticker)
    currencies = dict(zip(universe["ticker"], universe["currency"]))

    # 2. As-of and coverage-end filter, then the requested period.
    prices, notes = align.filter_as_of(source.read_table(PRICES_TABLE), cutoff, snapshot)
    if cutoff is not None and cutoff > snapshot.coverage_end:
        cutoff = snapshot.coverage_end
    period_end_cap = pd.Timestamp(end if cutoff is None else min(end, cutoff))
    wide = align.price_matrix(prices, list(tickers), "adj_close")
    wide = wide.loc[(wide.index >= pd.Timestamp(start)) & (wide.index <= period_end_cap)]
    counts = {t: int(wide[t].notna().sum()) for t in tickers}

    # 3. USD to CAD, with FX carry-forward notes.
    source_files = [UNIVERSE_TABLE, PRICES_TABLE]
    if any(currencies.get(t) == "USD" for t in tickers):
        source_files.append(FX_TABLE)
        fx = source.read_table(FX_TABLE)
    else:
        fx = pd.DataFrame({"date": [], "usdcad": []})
    wide, fx_notes = align.convert_to_cad(wide, currencies, fx, cutoff)
    notes = notes + fx_notes

    # 4. Date-intersection alignment.
    aligned, align_notes = align.align_intersection(wide)
    notes = notes + align_notes

    # 5. Minimum observation check.
    if len(aligned) < MIN_OBSERVATIONS:
        detail = ", ".join(f"{t}={n}" for t, n in counts.items())
        return ToolError(
            INSUFFICIENT_DATA,
            f"{len(aligned)} aligned observations, at least {MIN_OBSERVATIONS} required "
            f"(observations per asset: {detail})",
        )

    period_start, period_end = aligned.index[0].date(), aligned.index[-1].date()
    notes = notes + [
        "Returns are daily simple returns computed from adj_close (ratios of adjusted closes, in CAD)."
    ]
    # 7. CNQ.TO split anomaly note.
    notes = notes + quality.cnq_notes(tickers, period_start, period_end)
    return _Panel(aligned, notes, source_files, period_start, period_end)


def _returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change().iloc[1:]


def _wealth(returns: pd.Series, first_date: pd.Timestamp) -> pd.Series:
    wealth = (1.0 + returns).cumprod()
    return pd.concat([pd.Series([1.0], index=[first_date]), wealth])


def _ann_return(returns: pd.Series) -> float:
    growth = float((1.0 + returns).prod())
    return float(growth ** (TRADING_DAYS_PER_YEAR / len(returns)) - 1.0)


def _ann_vol(returns: pd.Series) -> float:
    return float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))


def _drawdown(returns: pd.Series, first_date: pd.Timestamp) -> dict[str, Any]:
    """Largest peak-to-trough fall of the wealth index (a non-positive number)."""
    wealth = _wealth(returns, first_date)
    peaks = wealth.cummax()
    drawdowns = wealth / peaks - 1.0
    trough = drawdowns.idxmin()
    peak = wealth.loc[:trough].idxmax()
    return {
        "value": float(drawdowns.loc[trough]),
        "peak_date": peak.date().isoformat(),
        "trough_date": trough.date().isoformat(),
    }


def _register(
    registry: ExhibitRegistry,
    metric: str,
    value: Any,
    panel: _Panel,
    assets: Sequence[str],
    inputs: Mapping[str, Any],
) -> Exhibit:
    return registry.add(
        metric=metric,
        value=value,
        period_start=panel.period_start,
        period_end=panel.period_end,
        assets=tuple(assets),
        currency="CAD",
        source_files=tuple(panel.source_files),
        processing_notes=tuple(panel.notes),
        inputs=dict(inputs),
    )


def _check_currency(display_ccy: str) -> ToolError | None:
    if display_ccy != "CAD":
        return ToolError(UNSUPPORTED_CURRENCY, f"only CAD is supported, got {display_ccy}")
    return None


def _inputs(as_of: date | None, **kwargs: Any) -> dict[str, Any]:
    out = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in kwargs.items()}
    out["as_of"] = None if as_of is None else _to_date(as_of).isoformat()
    return out


def _single(
    registry: ExhibitRegistry,
    source: DataSource,
    metric: str,
    ticker: str,
    start: date,
    end: date,
    as_of: date | None,
    display_ccy: str,
    compute,
    extra_inputs: Mapping[str, Any] | None = None,
) -> Exhibit | ToolError:
    if (error := _check_currency(display_ccy)) is not None:
        return error
    panel = _load_panel(source, [ticker], start, end, as_of)
    if isinstance(panel, ToolError):
        return panel
    returns = _returns(panel.prices)[ticker]
    value = compute(returns, panel.prices.index[0])
    inputs = _inputs(as_of, ticker=ticker, start=start, end=end, display_ccy=display_ccy)
    inputs.update(extra_inputs or {})
    return _register(registry, metric, value, panel, [ticker], inputs)


def annualized_return(
    registry: ExhibitRegistry,
    source: DataSource,
    ticker: str,
    start: date,
    end: date,
    as_of: date | None = None,
    display_ccy: str = "CAD",
) -> Exhibit | ToolError:
    """Geometric annualized return over 252 trading days per year."""
    return _single(
        registry, source, "annualized_return", ticker, start, end, as_of, display_ccy,
        lambda r, _first: _ann_return(r),
    )


def annualized_volatility(
    registry: ExhibitRegistry,
    source: DataSource,
    ticker: str,
    start: date,
    end: date,
    as_of: date | None = None,
    display_ccy: str = "CAD",
) -> Exhibit | ToolError:
    """Sample standard deviation of daily returns times sqrt(252)."""
    return _single(
        registry, source, "annualized_volatility", ticker, start, end, as_of, display_ccy,
        lambda r, _first: _ann_vol(r),
    )


def max_drawdown(
    registry: ExhibitRegistry,
    source: DataSource,
    ticker: str,
    start: date,
    end: date,
    as_of: date | None = None,
    display_ccy: str = "CAD",
) -> Exhibit | ToolError:
    """Largest peak-to-trough fall; value holds ``value``, ``peak_date``, ``trough_date``."""
    return _single(
        registry, source, "max_drawdown", ticker, start, end, as_of, display_ccy,
        lambda r, first: _drawdown(r, first),
    )


def correlation(
    registry: ExhibitRegistry,
    source: DataSource,
    ticker_a: str,
    ticker_b: str,
    start: date,
    end: date,
    as_of: date | None = None,
    display_ccy: str = "CAD",
) -> Exhibit | ToolError:
    """Pearson correlation of daily returns on the dates both assets share."""
    if (error := _check_currency(display_ccy)) is not None:
        return error
    if ticker_a == ticker_b:
        return ToolError(INVALID_ARGUMENT, "correlation needs two different tickers")
    panel = _load_panel(source, [ticker_a, ticker_b], start, end, as_of)
    if isinstance(panel, ToolError):
        return panel
    returns = _returns(panel.prices)
    value = float(returns[ticker_a].corr(returns[ticker_b]))
    if math.isnan(value):
        return ToolError(INSUFFICIENT_DATA, "correlation is undefined for constant prices")
    inputs = _inputs(
        as_of, ticker_a=ticker_a, ticker_b=ticker_b, start=start, end=end, display_ccy=display_ccy
    )
    return _register(registry, "correlation", value, panel, [ticker_a, ticker_b], inputs)


def resolve_period(period: str | tuple[date, date] | list) -> tuple[date, date] | None:
    """Resolve a named calendar year such as ``"2022"`` or a ``(start, end)`` pair."""
    if isinstance(period, str):
        match = _YEAR_RE.match(period.strip())
        if not match:
            return None
        year = int(match.group(1))
        return date(year, 1, 1), date(year, 12, 31)
    try:
        start, end = period
        return _to_date(start), _to_date(end)
    except (TypeError, ValueError):
        return None


def drawdown_in_period(
    registry: ExhibitRegistry,
    source: DataSource,
    ticker: str,
    period_name_or_range: str | tuple[date, date],
    as_of: date | None = None,
) -> Exhibit | ToolError:
    """Max drawdown within a named calendar year (e.g. ``"2022"``) or a date range."""
    resolved = resolve_period(period_name_or_range)
    if resolved is None:
        return ToolError(INVALID_ARGUMENT, f"unknown period: {period_name_or_range!r}")
    start, end = resolved
    return _single(
        registry, source, "drawdown_in_period", ticker, start, end, as_of, "CAD",
        lambda r, first: _drawdown(r, first),
        extra_inputs={"period": period_name_or_range if isinstance(period_name_or_range, str)
                      else [start.isoformat(), end.isoformat()]},
    )


def portfolio_metrics(
    registry: ExhibitRegistry,
    source: DataSource,
    weights: Mapping[str, float],
    start: date,
    end: date,
    as_of: date | None = None,
) -> Exhibit | ToolError:
    """Return, volatility and drawdown of a daily-rebalanced weighted portfolio."""
    if not weights:
        return ToolError(INVALID_ARGUMENT, "weights must not be empty")
    if any(
        isinstance(w, bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or w < 0
        for w in weights.values()
    ):
        return ToolError(INVALID_ARGUMENT, "weights must be non-negative finite numbers")
    if abs(sum(weights.values()) - 1.0) > WEIGHT_TOLERANCE:
        return ToolError(INVALID_ARGUMENT, f"weights must sum to 1, got {sum(weights.values()):.6f}")

    tickers = sorted(weights)
    panel = _load_panel(source, tickers, start, end, as_of)
    if isinstance(panel, ToolError):
        return panel
    w = np.array([weights[t] for t in tickers], dtype=float)
    returns = pd.Series(_returns(panel.prices)[tickers].to_numpy() @ w, index=panel.prices.index[1:])
    drawdown = _drawdown(returns, panel.prices.index[0])
    value = {
        "annualized_return": _ann_return(returns),
        "annualized_volatility": _ann_vol(returns),
        "max_drawdown": drawdown["value"],
        "peak_date": drawdown["peak_date"],
        "trough_date": drawdown["trough_date"],
    }
    panel.notes.append("Portfolio is rebalanced daily to the stated weights.")
    inputs = _inputs(as_of, weights={t: float(weights[t]) for t in tickers}, start=start, end=end)
    return _register(registry, "portfolio_metrics", value, panel, tickers, inputs)


def _check_weights(weights: Mapping[str, float], label: str = "weights") -> ToolError | None:
    if not weights:
        return ToolError(INVALID_ARGUMENT, f"{label} must not be empty")
    if any(
        isinstance(w, bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or w < 0
        for w in weights.values()
    ):
        return ToolError(INVALID_ARGUMENT, f"{label} must be non-negative finite numbers")
    if abs(sum(weights.values()) - 1.0) > WEIGHT_TOLERANCE:
        return ToolError(INVALID_ARGUMENT, f"{label} must sum to 1, got {sum(weights.values()):.6f}")
    return None


def _portfolio_returns(prices: pd.DataFrame, weights: Mapping[str, float]) -> pd.Series:
    tickers = sorted(weights)
    w = np.array([weights[t] for t in tickers], dtype=float)
    return pd.Series(_returns(prices)[tickers].to_numpy() @ w, index=prices.index[1:])


def risk_contribution(
    registry: ExhibitRegistry,
    source: DataSource,
    weights: Mapping[str, float],
    start: date,
    end: date,
    as_of: date | None = None,
) -> Exhibit | ToolError:
    """Each asset's percentage share of the total portfolio variance (shares sum to 100)."""
    if (error := _check_weights(weights)) is not None:
        return error
    tickers = sorted(weights)
    panel = _load_panel(source, tickers, start, end, as_of)
    if isinstance(panel, ToolError):
        return panel
    returns = _returns(panel.prices)[tickers]
    w = np.array([weights[t] for t in tickers], dtype=float)
    cov = returns.cov().to_numpy()
    total = float(w @ cov @ w)
    if not math.isfinite(total) or total <= 0.0:
        return ToolError(INSUFFICIENT_DATA, "portfolio variance is zero, shares are undefined")
    shares = w * (cov @ w) / total * 100.0
    value = {"share_of_variance_pct": {t: float(s) for t, s in zip(tickers, shares)}}
    panel.notes.append("Shares are w_i * (Cov w)_i / (w' Cov w) of daily returns, in percent.")
    inputs = _inputs(as_of, weights={t: float(weights[t]) for t in tickers}, start=start, end=end)
    return _register(registry, "risk_contribution", value, panel, tickers, inputs)


def _comparison_stats(returns: pd.Series, first_date: pd.Timestamp) -> dict[str, Any]:
    wealth = _wealth(returns, first_date)
    window = TRADING_DAYS_PER_YEAR
    worst_rolling = None
    if len(wealth) > window:
        worst_rolling = float((wealth / wealth.shift(window) - 1.0).min())
    in_2022 = returns[returns.index.year == 2022]
    return_2022 = float((1.0 + in_2022).prod() - 1.0) if len(in_2022) else None
    return {
        "annualized_volatility": _ann_vol(returns),
        "max_drawdown": _drawdown(returns, first_date)["value"],
        "worst_rolling_252d_return": worst_rolling,
        "return_2022": return_2022,
        "annualized_return": _ann_return(returns),
    }


def portfolio_comparison(
    registry: ExhibitRegistry,
    source: DataSource,
    base: Mapping[str, float],
    proposed: Mapping[str, float],
    start: date,
    end: date,
    as_of: date | None = None,
) -> Exhibit | ToolError:
    """Volatility, drawdown, worst rolling 252-day return, 2022 return and return of two portfolios."""
    for label, weights in (("base", base), ("proposed", proposed)):
        if (error := _check_weights(weights, label)) is not None:
            return error
    tickers = sorted(set(base) | set(proposed))
    panel = _load_panel(source, tickers, start, end, as_of)
    if isinstance(panel, ToolError):
        return panel
    first = panel.prices.index[0]
    value = {
        "base": _comparison_stats(_portfolio_returns(panel.prices, {t: base.get(t, 0.0) for t in tickers}), first),
        "proposed": _comparison_stats(
            _portfolio_returns(panel.prices, {t: proposed.get(t, 0.0) for t in tickers}), first
        ),
    }
    panel.notes.append(
        "Both portfolios are rebalanced daily. Worst rolling return is null when fewer than 253 "
        "aligned prices exist; the 2022 return is null when the period has no 2022 observation."
    )
    inputs = _inputs(
        as_of,
        base={t: float(w) for t, w in sorted(base.items())},
        proposed={t: float(w) for t, w in sorted(proposed.items())},
        start=start,
        end=end,
    )
    return _register(registry, "portfolio_comparison", value, panel, tickers, inputs)


def max_weight_within_contract(
    registry: ExhibitRegistry,
    source: DataSource,
    asset: str,
    contract: Mapping[str, Any],
    base: Mapping[str, float],
    start: date,
    end: date,
    as_of: date | None = None,
    step: float = 0.005,
    max_weight: float = 1.0,
) -> Exhibit | ToolError:
    """Largest weight of ``asset`` (grid of ``step``, up to ``max_weight``) at which every Hard_Rule passes.

    The value is 0 when no positive size passes. Search evaluations use a scratch registry, so
    only the result is stored as an Exhibit.
    """
    from guide.tribunal import rules  # imported here: rules imports this module

    if not isinstance(step, (int, float)) or isinstance(step, bool) or not 0 < step <= 1:
        return ToolError(INVALID_ARGUMENT, "step must be a number in (0, 1]")
    if not isinstance(max_weight, (int, float)) or isinstance(max_weight, bool) or not 0 < max_weight <= 1:
        return ToolError(INVALID_ARGUMENT, "max_weight must be a number in (0, 1]")
    if (error := _check_weights(base, "base")) is not None:
        return error
    try:
        start_d, end_d = _to_date(start), _to_date(end)
    except (TypeError, ValueError):
        return ToolError(INVALID_ARGUMENT, "start and end must be valid dates")
    if asset not in set(source.read_table(UNIVERSE_TABLE)["ticker"]):
        return ToolError(UNKNOWN_TICKER, asset)

    request = rules.RuleRequest(asset, max_weight, dict(base), start_d, end_d, as_of)
    ctx = rules._context(contract, request, source, ExhibitRegistry())

    def grid(index: int) -> float:
        return round(index * step, 6)

    def passes(index: int) -> bool:
        return rules._passes_at(contract, request, grid(index), source, ctx)

    top = int(math.floor(max_weight / step + 1e-9))
    if top < 1 or not passes(0):
        best = 0
    elif passes(top):
        best = top
    else:
        lo, hi = 0, top
        while hi - lo > 1:
            mid = (lo + hi) // 2
            lo, hi = (mid, hi) if passes(mid) else (lo, mid)
        best = lo

    value = {"asset": asset, "max_weight": grid(best) if best else 0.0, "step": float(step),
             "searched_up_to": float(max_weight)}
    tickers = sorted(set(base) | {asset})
    inputs = _inputs(as_of, asset=asset, base={t: float(w) for t, w in sorted(base.items())},
                     start=start_d, end=end_d, step=float(step), max_weight=float(max_weight))
    return registry.add(
        metric="max_weight_within_contract",
        value=value,
        period_start=start_d,
        period_end=end_d,
        assets=tuple(tickers),
        currency="CAD",
        source_files=(UNIVERSE_TABLE, PRICES_TABLE, FX_TABLE),
        processing_notes=(
            f"Largest weight on a {step:.1%} grid for which every Hard_Rule passes; 0 means no positive size passes.",
        ),
        inputs=inputs,
    )


ESG_TABLE = "esg_exclusions"


def exclusion_cost(
    registry: ExhibitRegistry,
    source: DataSource,
    excluded: str,
    start: date,
    end: date,
    as_of: date | None = None,
    replacement: str | None = None,
) -> Exhibit | ToolError:
    """Return and volatility given up by swapping an excluded asset for its replacement.

    The replacement is the non-excluded asset of the same asset class with the highest
    return correlation to ``excluded`` (each candidate correlation is its own cited
    Exhibit), unless ``replacement`` is given. ``cost`` is the excluded asset's
    annualized return minus the replacement's; positive means the exclusion costs return.
    """
    universe = source.read_table(UNIVERSE_TABLE)
    classes = dict(zip(universe["ticker"], universe["asset_class"]))
    if excluded not in classes:
        return ToolError(UNKNOWN_TICKER, excluded)
    try:
        table = source.read_table(ESG_TABLE)
    except Exception:
        return ToolError(INSUFFICIENT_DATA, f"{ESG_TABLE} not available in the snapshot")
    flags = table["excluded"].astype(str).str.lower() == "true"
    banned = set(table.loc[flags, "ticker"])
    if excluded not in banned:
        return ToolError(INVALID_ARGUMENT, f"{excluded} is not on the exclusion list")

    correlation_exhibit: int | None = None
    auto_pick = replacement is None
    if auto_pick:
        best: tuple[float, str, int] | None = None
        for cand in sorted(t for t, c in classes.items()
                           if c == classes[excluded] and t != excluded and t not in banned):
            ex = correlation(registry, source, excluded, cand, start, end, as_of)
            if isinstance(ex, ToolError):
                continue
            if best is None or ex.value > best[0]:
                best = (ex.value, cand, ex.number)
        if best is None:
            return ToolError(INSUFFICIENT_DATA, f"no non-excluded {classes[excluded]} replacement for {excluded}")
        _, replacement, correlation_exhibit = best
    else:
        if replacement not in classes:
            return ToolError(UNKNOWN_TICKER, replacement)
        if replacement == excluded or replacement in banned:
            return ToolError(INVALID_ARGUMENT, "replacement must be a different, non-excluded asset")
        ex = correlation(registry, source, excluded, replacement, start, end, as_of)
        if isinstance(ex, ToolError):
            return ex
        correlation_exhibit = ex.number

    panel = _load_panel(source, [excluded, replacement], start, end, as_of)
    if isinstance(panel, ToolError):
        return panel
    returns = _returns(panel.prices)
    ret = {t: _ann_return(returns[t]) for t in (excluded, replacement)}
    vol = {t: _ann_vol(returns[t]) for t in (excluded, replacement)}
    value = {
        "excluded": excluded,
        "replacement": replacement,
        "correlation_exhibit": correlation_exhibit,
        "excluded_annualized_return": ret[excluded],
        "replacement_annualized_return": ret[replacement],
        "return_cost": ret[excluded] - ret[replacement],
        "excluded_annualized_volatility": vol[excluded],
        "replacement_annualized_volatility": vol[replacement],
        "volatility_change": vol[replacement] - vol[excluded],
    }
    panel.source_files.append(ESG_TABLE)
    panel.notes.append(
        f"Replacement {replacement} is the non-excluded {classes[excluded]} asset with the highest "
        f"return correlation to {excluded} (Exhibit {correlation_exhibit})."
        if auto_pick else
        f"Replacement {replacement} was chosen by the caller (correlation Exhibit {correlation_exhibit})."
    )
    inputs = _inputs(as_of, excluded=excluded, replacement=replacement, start=start, end=end)
    return _register(registry, "exclusion_cost", value, panel, [excluded, replacement], inputs)
