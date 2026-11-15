"""Proposed-portfolio construction (Req. 28.2). Pure code, no model call."""
from __future__ import annotations

from typing import Mapping


def propose(base: Mapping[str, float], asset: str, weight: float) -> dict[str, float]:
    """Scale every base weight by (1 - weight) and add `asset` at `weight`.

    If `asset` is already held, `weight` is added to its scaled weight.
    """
    if not 0.0 <= weight <= 1.0:
        raise ValueError(f"weight must be between 0 and 1, got {weight}")
    proposed = {ticker: w * (1.0 - weight) for ticker, w in base.items()}
    proposed[asset] = proposed.get(asset, 0.0) + weight
    return proposed
