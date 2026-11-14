"""Data alignment helpers: as-of filtering, USD to CAD conversion, calendar
alignment, and macro publication lag (Req. 3.1 to 3.6).

All functions are pure. Functions that change data return ``(data, notes)``
where ``notes`` are processing notes for the Exhibit.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Mapping

import pandas as pd

from guide.config import Config

FX_FILE = "fx_usdcad_daily.csv"
PRICES_FILE = "prices_daily.csv"
MACRO_FILE = "macro_rates.csv"


def _to_ts(d: date | str | pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(d).normalize()


def filter_as_of(df: pd.DataFrame, as_of: date | None, date_col: str = "date") -> pd.DataFrame:
    """Drop every observation dated after ``as_of`` (Req. 3.6). ``None`` keeps all."""
    if as_of is None:
        return df.copy()
    dates = pd.to_datetime(df[date_col])
    return df.loc[dates <= _to_ts(as_of)].copy()


def price_matrix(prices: pd.DataFrame, tickers: list[str], column: str = "adj_close") -> pd.DataFrame:
    """Wide table (date index, one column per ticker) of ``column`` values."""
    sub = prices[prices["ticker"].isin(tickers)].copy()
    sub["date"] = pd.to_datetime(sub["date"])
    wide = sub.pivot(index="date", columns="ticker", values=column).sort_index()
    return wide.reindex(columns=list(tickers))


def convert_to_cad(
    wide: pd.DataFrame,
    currencies: Mapping[str, str],
    fx: pd.DataFrame,
    as_of: date | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Convert USD-quoted columns to CAD with ``usdcad`` (Req. 3.1, 3.2).

    ``currencies`` maps ticker to its quote currency. FX rows after ``as_of``
    are ignored. A price date with no FX row uses the most recent earlier
    rate; the number of such dates is recorded. Dates before the first FX rate
    cannot be converted and become NaN (dropped later by alignment).
    """
    notes: list[str] = []
    usd = [t for t in wide.columns if currencies.get(t) == "USD"]
    out = wide.copy()
    if not usd:
        return out, notes
    rates = filter_as_of(fx, as_of)
    rates["date"] = pd.to_datetime(rates["date"])
    series = rates.drop_duplicates("date").set_index("date")["usdcad"].sort_index()
    rate = series.reindex(series.index.union(out.index)).ffill().reindex(out.index)
    for t in usd:
        has_price = out[t].notna()
        out[t] = out[t] * rate
        # Dates where a price exists but the FX table has no row: carried forward.
        carried = [d for d in out.index[has_price] if d not in series.index and pd.notna(rate.get(d))]
        unconvertible = int((has_price & rate.isna()).sum())
        notes.append(f"{t}: converted from USD to CAD using usdcad from {FX_FILE}")
        if carried:
            notes.append(
                f"{t}: FX rate missing on {len(carried)} date(s); carried forward the most "
                f"recent earlier usdcad rate (first: {carried[0].date()}, last: {carried[-1].date()})"
            )
        if unconvertible:
            notes.append(f"{t}: {unconvertible} date(s) before the first available FX rate were dropped")
    return out, notes


def align_intersection(wide: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Keep only dates on which every compared asset has a price (Req. 3.3)."""
    before = {c: int(wide[c].notna().sum()) for c in wide.columns}
    aligned = wide.dropna(how="any")
    detail = ", ".join(f"{c}={n}" for c, n in before.items())
    notes = [
        "Calendar alignment: date intersection (only dates on which all compared assets have a price)",
        f"Observation count after alignment: {len(aligned)} (before alignment: {detail})",
    ]
    return aligned, notes


def macro_available(
    macro: pd.DataFrame,
    series_id: str,
    as_of: date | None,
    config: Config,
) -> pd.DataFrame:
    """Observations of ``series_id`` available on ``as_of`` (Req. 3.4, 3.5, 3.6).

    An observation is available once ``reference date + publication lag`` is
    on or before ``as_of``. The lag comes from ``config.macro_lag``. With
    ``as_of=None`` all observations are returned. Rows are sorted by date.
    """
    sub = macro[macro["series_id"] == series_id].copy()
    sub["date"] = pd.to_datetime(sub["date"])
    sub = sub.sort_values("date")
    if as_of is None:
        return sub
    cutoff = _to_ts(as_of) - timedelta(days=config.macro_lag(series_id))
    return sub[sub["date"] <= cutoff]


def macro_value(
    macro: pd.DataFrame, series_id: str, as_of: date | None, config: Config
) -> tuple[float | None, pd.Timestamp | None]:
    """Latest available value and its reference date, or ``(None, None)``."""
    avail = macro_available(macro, series_id, as_of, config)
    if avail.empty:
        return None, None
    last = avail.iloc[-1]
    return float(last["value"]), last["date"]
