"""Python validation for the Seed_Import_Job (Req. 20.2, 20.3, 20.6, 20.7, 20.8).

Mirrors the hard checks of ``data/build_dataset.py`` without importing it:
duplicate (date, ticker), missing tickers, currency mismatch, non-positive adj_close.
No network access and no data download.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

import pandas as pd

_MAX_LISTED = 10
_URL = re.compile(r"https?://\S+")
_RESTRICTED = re.compile(
    r"non-?commercial|personal use|personal, non|not permitted|no redistribution|"
    r"redistribution is prohibited|may not be redistributed",
    re.IGNORECASE,
)
_PERMITTED = re.compile(r"permitted|permission|licen[cs]e|public domain|redistribut", re.IGNORECASE)


def _tickers(values: Iterable) -> list[str]:
    return [str(v) for v in values]


def _sample(items: Iterable) -> str:
    items = sorted({str(i) for i in items})
    shown = ", ".join(items[:_MAX_LISTED])
    return shown + (f" (+{len(items) - _MAX_LISTED} more)" if len(items) > _MAX_LISTED else "")


def validate_tables(prices: pd.DataFrame, universe: pd.DataFrame) -> tuple[str, ...]:
    """Return one violation message per failed check; empty tuple means valid (Req. 20.6)."""
    violations: list[str] = []

    dup = prices.duplicated(["date", "ticker"], keep=False)
    if dup.any():
        pairs = {f"{r.ticker}@{r.date}" for r in prices.loc[dup, ["date", "ticker"]].itertuples()}
        violations.append(f"duplicate (date, ticker) rows: {_sample(pairs)}")

    missing = set(_tickers(universe["ticker"])) - set(_tickers(prices["ticker"]))
    if missing:
        violations.append(f"universe tickers without price rows: {_sample(missing)}")

    unknown = set(_tickers(prices["ticker"])) - set(_tickers(universe["ticker"]))
    if unknown:
        violations.append(f"price tickers not in the universe: {_sample(unknown)}")

    expected = dict(zip(universe["ticker"], universe["currency"]))
    seen = prices[["ticker", "currency"]].drop_duplicates()
    bad = {
        f"{r.ticker} ({r.currency} != {expected[r.ticker]})"
        for r in seen.itertuples()
        if r.ticker in expected and r.currency != expected[r.ticker]
    }
    if bad:
        violations.append(f"currency differs from the universe: {_sample(bad)}")

    adj = pd.to_numeric(prices["adj_close"], errors="coerce")
    bad_adj = prices.loc[adj.isna() | ~(adj > 0), "ticker"]
    if len(bad_adj):
        violations.append(f"adj_close missing or not positive for: {_sample(bad_adj)}")

    return tuple(violations)


@dataclass(frozen=True)
class UniverseAddition:
    ticker: str
    name: str
    asset_class: str
    market: str
    currency: str
    sector: str
    source_name: str
    data_file: str


@dataclass(frozen=True)
class RestrictionResult:
    accepted: tuple[str, ...]
    rejected: Mapping[str, str]  # ticker -> reason, so rejected tickers are named

    @property
    def violations(self) -> tuple[str, ...]:
        return tuple(f"{t}: {why}" for t, why in self.rejected.items())


def _addition_fields_missing(a: UniverseAddition) -> list[str]:
    return [f for f in UniverseAddition.__dataclass_fields__ if not str(getattr(a, f) or "").strip()]


def _doc_sections(doc: str) -> list[str]:
    parts = re.split(r"(?m)^#{1,3} ", doc)
    return [p for p in parts if p.strip()]


def _documentation_problem(addition: UniverseAddition, doc: str) -> str | None:
    """None when the Data_Source_Document entry satisfies Req. 20.2 and 20.3."""
    needles = [addition.ticker, addition.source_name, addition.data_file]
    section = next(
        (s for s in _doc_sections(doc) if any(n and n in s for n in needles)), None
    )
    if section is None:
        return "no entry in the data source document"
    lines = section.splitlines()
    if not any("terms" in ln.lower() and _URL.search(ln) for ln in lines):
        return "data source entry has no terms-of-use URL"
    if _RESTRICTED.search(section):
        return "terms of use do not permit use and redistribution in this project"
    if not any(_PERMITTED.search(ln) and "terms" not in ln.lower().split("|")[0] for ln in lines):
        return "data source entry has no permitted-use statement"
    return None


def restrict_universe(
    requested: Iterable[str],
    universe: Iterable[str],
    additions: Iterable[UniverseAddition] | None,
    data_sources_doc: str,
) -> RestrictionResult:
    """Accept universe tickers and documented additions only; name every rejected ticker (Req. 20.8)."""
    universe_set = set(_tickers(universe))
    by_ticker = {a.ticker: a for a in (additions or ())}
    accepted: list[str] = []
    rejected: dict[str, str] = {}
    for ticker in dict.fromkeys(_tickers(requested)):
        if ticker in universe_set:
            accepted.append(ticker)
            continue
        addition = by_ticker.get(ticker)
        if addition is None:
            rejected[ticker] = "not in the starter universe and not listed in the universe additions"
            continue
        missing = _addition_fields_missing(addition)
        if missing:
            rejected[ticker] = f"universe addition lacks: {', '.join(missing)}"
            continue
        problem = _documentation_problem(addition, data_sources_doc or "")
        if problem:
            rejected[ticker] = problem
            continue
        accepted.append(ticker)
    return RestrictionResult(tuple(accepted), rejected)
