"""Wilson 95 % intervals and Confidence_Labels (Req. 34.3). Pure code, no model."""
from __future__ import annotations

import math
from typing import Literal

Label = Literal["Measured", "Indicative", "Context"]
Z95 = 1.959963984540054


def wilson_interval(successes: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a proportion; (0, 1) when there is no trial."""
    if n < 0 or successes < 0 or successes > n:
        raise ValueError("need 0 <= successes <= n")
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def confidence_label(a: tuple[int, int] | None, b: tuple[int, int] | None) -> Label:
    """``Measured`` when the two arms' intervals do not overlap, ``Indicative`` when they
    do, ``Context`` when either arm has no measurement (a (successes, n) pair with n > 0)."""
    if a is None or b is None or a[1] <= 0 or b[1] <= 0:
        return "Context"
    lo_a, hi_a = wilson_interval(*a)
    lo_b, hi_b = wilson_interval(*b)
    return "Measured" if hi_a < lo_b or hi_b < lo_a else "Indicative"
