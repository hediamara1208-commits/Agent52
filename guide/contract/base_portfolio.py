"""A custom Base_Portfolio: the investor's current holdings, given with a profile.

It is portfolio state, not an Investor_Contract rule, so it travels next to the contract values
and never inside the contract. The Session_API and the runtime both check it here.
"""
from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

MAX_HOLDINGS = 30
SUM_TOLERANCE = 0.01  # weights may sum to 0.99..1.01 (rounding in a form); they are rescaled to 1


class BasePortfolioError(ValueError):
    """The submitted Base_Portfolio is unusable; the message says why, in plain words."""


def validate_base_portfolio(raw: Any, universe: Collection[str] | None = None) -> dict[str, float]:
    """Return {ticker: weight} with weights summing to exactly 1, or raise BasePortfolioError.

    Accepts weights as fractions (0.6) or, when they sum to about 100, as percentages (60).
    """
    if not isinstance(raw, Mapping) or not raw:
        raise BasePortfolioError("base_portfolio must map tickers to weights")
    if len(raw) > MAX_HOLDINGS:
        raise BasePortfolioError(f"base_portfolio has more than {MAX_HOLDINGS} holdings")
    weights: dict[str, float] = {}
    for key, value in raw.items():
        ticker = str(key).strip().upper()
        if not ticker:
            raise BasePortfolioError("base_portfolio has an empty ticker")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not value > 0:
            raise BasePortfolioError(f"weight of {ticker} must be a positive number")
        if ticker in weights:
            raise BasePortfolioError(f"{ticker} appears twice")
        weights[ticker] = float(value)
    total = sum(weights.values())
    if abs(total - 100) <= 100 * SUM_TOLERANCE:  # percentages
        weights = {t: w / 100 for t, w in weights.items()}
        total = sum(weights.values())
    if abs(total - 1) > SUM_TOLERANCE:
        raise BasePortfolioError(f"weights must sum to 100% (they sum to {total * 100:.1f}%)")
    if universe is not None:
        known = {u.upper() for u in universe}
        unknown = sorted(t for t in weights if t not in known)
        if unknown:
            raise BasePortfolioError(f"not in the assets universe: {', '.join(unknown)}")
    return {t: w / total for t, w in weights.items()}


def split_profile(profile: Mapping[str, Any]) -> tuple[dict[str, Any], Any]:
    """(contract values without base_portfolio, the raw base_portfolio or None).

    The base may come as ``profile["base_portfolio"]`` or, from older clients, inside ``values``."""
    values = dict(profile.get("values") or {}) if isinstance(profile.get("values") or {}, Mapping) else profile.get("values")
    raw = profile.get("base_portfolio")
    if isinstance(values, dict) and "base_portfolio" in values:
        inner = values.pop("base_portfolio")
        raw = raw if raw is not None else inner
    return values, raw
