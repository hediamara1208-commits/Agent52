"""Request parser: extract a ticker and a position weight from free text.

Rule-based extraction first; an optional injectable fallback (for example a
model call) is consulted only for fields the rules could not find. Every
result is validated against the universe and a weight in (0, 1].
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional, Union

# Fallback receives the text and returns a dict that may contain "ticker"
# and/or "weight_fraction" (None or absent when unknown).
Fallback = Callable[[str], Optional[dict]]


@dataclass(frozen=True)
class ParsedRequest:
    ticker: str
    weight_fraction: float


@dataclass(frozen=True)
class MissingFields:
    asset: bool
    size: bool

    def as_dict(self) -> dict:
        return {"asset": self.asset, "size": self.size}


_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent\b|per\s*cent\b)", re.IGNORECASE)
_FRACTION_RE = re.compile(r"(?<![\w.])(0?\.\d+|1(?:\.0+)?)(?![\w%.])")
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9.\-=^]*")


def _valid_weight(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = float(value)
    return v if 0.0 < v <= 1.0 else None


def _extract_weight(text: str) -> Optional[float]:
    m = _PERCENT_RE.search(text)
    if m:
        return _valid_weight(float(m.group(1)) / 100.0)
    m = _FRACTION_RE.search(text)
    if m:
        return _valid_weight(float(m.group(1)))
    return None


def _extract_ticker(text: str, universe: set[str]) -> Optional[str]:
    by_upper = {t.upper(): t for t in universe}
    for tok in _TOKEN_RE.findall(text):
        tok = tok.rstrip(".-")
        # Exact-case match always counts; lowercase only for tickers of 3+
        # characters, so words like "a" or "in" are not mistaken for tickers.
        if tok in universe:
            return tok
        if len(tok) >= 3 and tok.upper() in by_upper:
            return by_upper[tok.upper()]
    return None


# Common names for the starter universe, so "30% in tesla" works like "30% in TSLA".
# Only names whose ticker is in the given universe are used.
_NAME_ALIASES = {
    "royal bank": "RY.TO", "rbc": "RY.TO", "td bank": "TD.TO", "toronto-dominion": "TD.TO",
    "manulife": "MFC.TO", "enbridge": "ENB.TO", "canadian natural": "CNQ.TO",
    "canadian national": "CNR.TO", "cn rail": "CNR.TO", "fortis": "FTS.TO",
    "couche-tard": "ATD.TO", "couche tard": "ATD.TO", "shopify": "SHOP.TO",
    "constellation software": "CSU.TO", "apple": "AAPL", "microsoft": "MSFT", "nvidia": "NVDA",
    "alphabet": "GOOGL", "google": "GOOGL", "amazon": "AMZN", "tesla": "TSLA",
    "jpmorgan": "JPM", "jp morgan": "JPM", "johnson & johnson": "JNJ", "johnson and johnson": "JNJ",
    "procter & gamble": "PG", "procter and gamble": "PG", "exxon": "XOM", "exxonmobil": "XOM",
    "s&p 500": "SPY", "nasdaq": "QQQ", "gold": "GLD", "bitcoin": "BTC-USD", "btc": "BTC-USD",
    "ether": "ETH-USD", "ethereum": "ETH-USD", "eth": "ETH-USD",
}


def _ticker_from_name(text: str, universe: set[str]) -> Optional[str]:
    low = text.lower()
    for name in sorted(_NAME_ALIASES, key=len, reverse=True):
        ticker = _NAME_ALIASES[name]
        if ticker in universe and re.search(r"(?<![\w&])" + re.escape(name) + r"(?![\w&])", low):
            return ticker
    return None


def _validated_ticker(value: object, universe: set[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    v = value.strip()
    if v in universe:
        return v
    for t in universe:
        if t.upper() == v.upper():
            return t
    return None


def parse_request(
    text: str,
    universe: set[str],
    fallback: Optional[Fallback] = None,
) -> Union[ParsedRequest, MissingFields]:
    """Return a ParsedRequest, or MissingFields naming what is absent."""
    text = text or ""
    ticker = _extract_ticker(text, universe) or _ticker_from_name(text, universe)
    weight = _extract_weight(text)

    if (ticker is None or weight is None) and fallback is not None:
        try:
            out = fallback(text)
        except Exception:
            out = None
        if isinstance(out, dict):
            if ticker is None:
                ticker = _validated_ticker(out.get("ticker"), universe)
            if weight is None:
                weight = _valid_weight(out.get("weight_fraction"))

    if ticker is None or weight is None:
        return MissingFields(asset=ticker is None, size=weight is None)
    return ParsedRequest(ticker=ticker, weight_fraction=weight)
