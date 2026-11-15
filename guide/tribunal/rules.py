"""Rule_Engine: Hard_Rules and the Verdict, decided by code (Req. 5.1 to 5.4, 5.9, 5.10, 5.13 to 5.15, 32.3).

The proposed portfolio is Base_Portfolio x (1 - w) + the requested asset at w.
No agent takes part: the Judge only receives these results and writes narrative.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Mapping

from guide.config import load_config
from guide.toolkit import metrics
from guide.toolkit.exhibits import ExhibitRegistry
from guide.trace.recorder import TraceRecorder

GRID_STEP = 0.005  # 0.5 percentage points, same grid as max_weight_within_contract
EPS = 1e-9
CAPPED_ASSET_CLASSES = ("equity", "crypto")  # per-asset cap does not apply to ETFs
LOW_RISK_LEVELS = ("low", "low_to_moderate")
ESG_TABLE = "esg_exclusions"
FOSSIL_FUEL_SCREEN = "fossil_fuel_screen"

ACCEPT = "accept"
ACCEPT_WITH_CONDITIONS = "accept_with_conditions"
REJECT = "reject"


@dataclass(frozen=True)
class RuleRequest:
    """The simulated request: ``weight`` of the portfolio in ``ticker``."""

    ticker: str
    weight: float
    base_portfolio: Mapping[str, float]
    start: date
    end: date
    as_of: date | None = None


@dataclass
class RuleResult:
    rule: str
    status: Literal["pass", "fail", "unverified"]
    observed: float | None
    limit: float | None
    exhibits: list[int] = field(default_factory=list)
    detail: str = ""


@dataclass
class Verdict:
    verdict: Literal["accept", "accept_with_conditions", "reject"]
    max_weight: float | None  # largest weight on the 0.5-point grid at which every rule passes
    failing_rules: list[str]
    unverified_rules: list[str]
    conditions: list[str]
    tension: str | None
    exhibits: list[int]
    reason: str


def proposed_portfolio(request: RuleRequest, weight: float) -> dict[str, float]:
    weights = {t: w * (1.0 - weight) for t, w in request.base_portfolio.items()}
    weights[request.ticker] = weights.get(request.ticker, 0.0) + weight
    return {t: w for t, w in weights.items() if w > 0}


def _universe(source) -> dict[str, dict[str, str]]:
    table = source.read_table(metrics.UNIVERSE_TABLE)
    return {
        row["ticker"]: {"asset_class": row.get("asset_class"), "sector": row.get("sector")}
        for row in table.to_dict("records")
    }


def _speculative_set(
    tickers, universe, source, registry: ExhibitRegistry, request: RuleRequest
) -> tuple[set[str], list[int], bool]:
    """Crypto plus equities whose own volatility exceeds the configured threshold."""
    threshold = load_config().speculative_volatility_threshold
    spec: set[str] = set()
    exhibits: list[int] = []
    complete = True
    for ticker in sorted(tickers):
        asset_class = universe.get(ticker, {}).get("asset_class")
        if asset_class == "crypto":
            spec.add(ticker)
        elif asset_class == "equity":
            ex = metrics.annualized_volatility(
                registry, source, ticker, request.start, request.end, request.as_of
            )
            if isinstance(ex, metrics.ToolError):
                complete = False
                continue
            exhibits.append(ex.number)
            if ex.value > threshold:
                spec.add(ticker)
    return spec, exhibits, complete


def _excluded_tickers(source) -> set[str] | None:
    try:
        table = source.read_table(ESG_TABLE)
    except Exception:
        return None
    flags = table["excluded"].astype(str).str.lower() == "true"
    return set(table.loc[flags, "ticker"])


def _worst(items: Mapping[str, float], caps: Mapping[str, float]) -> tuple[float | None, float | None, str]:
    """Return observed, limit and the key with the largest excess over its cap."""
    worst_key = None
    for key, cap in caps.items():
        if key in items and (worst_key is None or items[key] - cap > items[worst_key] - caps[worst_key]):
            worst_key = key
    if worst_key is None:
        return None, None, ""
    return items[worst_key], caps[worst_key], worst_key


def _status(observed: float | None, limit: float | None) -> str:
    return "pass" if observed is None or limit is None or observed <= limit + EPS else "fail"


@dataclass
class _Context:
    universe: dict[str, dict[str, str]]
    speculative: set[str]
    spec_complete: bool
    spec_exhibits: list[int]
    excluded: set[str] | None


def _context(contract, request, source, registry) -> _Context:
    universe = _universe(source)
    tickers = set(request.base_portfolio) | {request.ticker}
    spec, ex, complete = _speculative_set(tickers, universe, source, registry, request)
    excluded = _excluded_tickers(source) if FOSSIL_FUEL_SCREEN in contract["esg_exclusions"] else set()
    return _Context(universe, spec, complete, ex, excluded)


def _check(contract, request, weight, source, registry, ctx: _Context) -> list[RuleResult]:
    weights = proposed_portfolio(request, weight)
    info = ctx.universe
    results: list[RuleResult] = []

    capped = {t: w for t, w in weights.items() if info.get(t, {}).get("asset_class") in CAPPED_ASSET_CLASSES}
    cap = contract["per_asset_cap"]
    top = max(capped.values(), default=0.0)
    results.append(RuleResult("per_asset_cap", _status(top, cap), top, cap))

    by_class: dict[str, float] = {}
    by_sector: dict[str, float] = {}
    for t, w in weights.items():
        cls, sec = info.get(t, {}).get("asset_class"), info.get(t, {}).get("sector")
        by_class[cls] = by_class.get(cls, 0.0) + w
        by_sector[sec] = by_sector.get(sec, 0.0) + w
    for rule, grouped, caps in (
        ("per_asset_class_caps", by_class, contract["per_asset_class_caps"]),
        ("sector_caps", by_sector, contract["sector_caps"]),
    ):
        observed, limit, key = _worst(grouped, caps)
        results.append(RuleResult(rule, _status(observed, limit), observed, limit, detail=key))

    crypto = by_class.get("crypto", 0.0)
    results.append(RuleResult("crypto_cap", _status(crypto, contract["crypto_cap"]), crypto, contract["crypto_cap"]))

    # Volatility and drawdown come from a portfolio_metrics Exhibit.
    pm = metrics.portfolio_metrics(registry, source, weights, request.start, request.end, request.as_of)
    if isinstance(pm, metrics.ToolError):
        for rule in ("max_volatility", "max_drawdown"):
            results.append(RuleResult(rule, "unverified", None, contract[rule], detail=pm.message))
    else:
        vol, dd = pm.value["annualized_volatility"], -pm.value["max_drawdown"]
        results.append(RuleResult("max_volatility", _status(vol, contract["max_volatility"]),
                                  vol, contract["max_volatility"], [pm.number]))
        results.append(RuleResult("max_drawdown", _status(dd, contract["max_drawdown"]),
                                  dd, contract["max_drawdown"], [pm.number]))

    limit = contract.get("speculative_limit")
    if limit is not None:
        spec_weight = sum(w for t, w in weights.items() if t in ctx.speculative)
        status = _status(spec_weight, limit)
        if status == "pass" and not ctx.spec_complete:
            status = "unverified"
        results.append(RuleResult("speculative_limit", status, spec_weight, limit, list(ctx.spec_exhibits)))

    if FOSSIL_FUEL_SCREEN in contract["esg_exclusions"]:
        if ctx.excluded is None:
            results.append(RuleResult("esg_exclusion", "unverified", None, 0.0,
                                      detail=f"{ESG_TABLE} not available in the snapshot"))
        else:
            hit = sorted(t for t in weights if t in ctx.excluded)
            results.append(RuleResult("esg_exclusion", "fail" if hit else "pass",
                                      float(len(hit)), 0.0, detail=", ".join(hit)))
    return results


def evaluate_rules(
    contract: Mapping[str, Any],
    request: RuleRequest,
    registry: ExhibitRegistry,
    *,
    source,
    trace: TraceRecorder | None = None,
) -> list[RuleResult]:
    """Check every Hard_Rule on the portfolio proposed at ``request.weight``."""
    ctx = _context(contract, request, source, registry)
    results = _check(contract, request, request.weight, source, registry, ctx)
    if trace is not None:
        for r in results:
            trace.judge_check(
                r.rule,
                {"observed": r.observed, "limit": r.limit, "weight": request.weight},
                r.status,
            )
    return results


def _grid_weight(index: int) -> float:
    return round(index * GRID_STEP, 6)


def _passes_at(contract, request, weight, source, ctx) -> bool:
    scratch = ExhibitRegistry()  # search evaluations never reach the session registry
    return all(r.status != "fail" for r in _check(contract, request, weight, source, scratch, ctx))


def _largest_passing_index(contract, request, source, ctx) -> int | None:
    """Bisection over the 0.5-point grid; None when even a zero position fails."""
    if not _passes_at(contract, request, 0.0, source, ctx):
        return None
    lo = 0
    hi = math.ceil(request.weight / GRID_STEP - EPS)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _passes_at(contract, request, _grid_weight(mid), source, ctx):
            lo = mid
        else:
            hi = mid
    return lo


def decide(
    results: list[RuleResult],
    contract: Mapping[str, Any],
    request: RuleRequest,
    registry: ExhibitRegistry,
    *,
    source,
    trace: TraceRecorder | None = None,
) -> Verdict:
    """Compute the Verdict from the rule results; never depends on an agent."""
    failing = [r.rule for r in results if r.status == "fail"]
    unverified = [r.rule for r in results if r.status == "unverified"]
    cited = sorted({n for r in results for n in r.exhibits})

    tension = None
    asset_class = _universe(source).get(request.ticker, {}).get("asset_class")
    if (
        contract["risk_level"] in LOW_RISK_LEVELS
        and asset_class in CAPPED_ASSET_CLASSES
        and request.weight > contract["per_asset_cap"] + EPS
    ):
        tension = (
            f"The requested {request.weight:.1%} in {request.ticker} exceeds the per-asset cap of "
            f"{contract['per_asset_cap']:.1%} for a {contract['risk_level'].replace('_', '-')} investor."
        )

    def done(verdict, max_weight, conditions, reason, exhibits=None) -> Verdict:
        out = Verdict(verdict, max_weight, failing, unverified, conditions, tension,
                      sorted(set(cited) | set(exhibits or [])), reason)
        if trace is not None:
            trace.judge_check("verdict", {"failing": failing, "unverified": unverified},
                              {"verdict": verdict, "max_weight": max_weight})
        return out

    if not failing:
        return done(ACCEPT, request.weight, [], "Every Hard_Rule passes at the requested size.")

    if "esg_exclusion" in failing:
        return done(REJECT, None, [], "The ESG exclusion fails, and no position size satisfies an exclusion.")

    # The numeric condition is itself an Exhibit (task 21.2).
    mw = metrics.max_weight_within_contract(
        registry, source, request.ticker, contract, request.base_portfolio,
        request.start, request.end, request.as_of, step=GRID_STEP, max_weight=min(request.weight, 1.0),
    )
    if isinstance(mw, metrics.ToolError) or mw.value["max_weight"] <= 0:
        return done(REJECT, None, [], "No positive position size satisfies every Hard_Rule.",
                    [] if isinstance(mw, metrics.ToolError) else [mw.number])

    max_weight = float(mw.value["max_weight"])
    # Evidence for the condition: rule results at the maximum, recorded in the session registry.
    at_max = _check(contract, request, max_weight, source, registry, _context(contract, request, source, registry))
    exhibits = sorted({mw.number, *(n for r in at_max for n in r.exhibits)})
    conditions = [
        f"Keep the position in {request.ticker} at or below {max_weight:.1%} of the portfolio "
        f"(requested {request.weight:.1%}); failing rules: {', '.join(failing)}."
    ]
    return done(ACCEPT_WITH_CONDITIONS, max_weight, conditions,
                "Some Hard_Rules fail at the requested size and pass at the stated maximum.", exhibits)
