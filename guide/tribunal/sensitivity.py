"""Sensitivity_Analysis: the threshold at which the Verdict changes (Req. 6.5 to 6.7).

Re-evaluates the Hard_Rules with one input changed at a time: position size (0.5-point
grid), each Investor_Contract limit used by a failing rule, the horizon, and the 2022
drawdown period. All evaluations run on scratch registries; only the final result of
each input is stored as one ``sensitivity`` Exhibit in the session registry.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Mapping

from guide.config import load_config
from guide.toolkit import metrics
from guide.toolkit.exhibits import ExhibitRegistry
from guide.tribunal import rules
from guide.tribunal.rules import ACCEPT, EPS, GRID_STEP, RuleRequest, RuleResult

NO_CHANGE = "no change in tested range"
STRESS_PERIOD = "2022"
SOURCE_FILES = ("prices_daily", "fx_usdcad_daily", "assets_universe")
SCALAR_LIMITS = ("per_asset_cap", "max_volatility", "max_drawdown", "crypto_cap", "speculative_limit")
GROUP_LIMITS = {"per_asset_class_caps": "per_asset_class_caps", "sector_caps": "sector_caps"}


@dataclass
class SensitivityResult:
    variable: str
    changed: bool  # False means "no change in tested range"
    threshold: float | str | None
    baseline_verdict: str
    verdict_at_threshold: str | None
    exhibit: int
    text: str


def _verdict(contract, request: RuleRequest, source) -> str:
    scratch = ExhibitRegistry()
    ctx = rules._context(contract, request, source, scratch)
    results = rules._check(contract, request, request.weight, source, scratch, ctx)
    return rules.decide(results, contract, request, scratch, source=source).verdict


def _store(registry: ExhibitRegistry, request: RuleRequest, variable: str, value: Mapping[str, Any],
           notes: list[str] | None = None) -> int:
    ex = registry.add(
        metric="sensitivity",
        value={"variable": variable, **value},
        period_start=request.start,
        period_end=request.end,
        assets=tuple(sorted(set(request.base_portfolio) | {request.ticker})),
        currency="CAD",
        source_files=SOURCE_FILES,
        processing_notes=tuple(notes or ()),
        inputs={"variable": variable, "ticker": request.ticker, "weight": request.weight,
                "start": request.start.isoformat(), "end": request.end.isoformat(),
                "as_of": None if request.as_of is None else request.as_of.isoformat()},
    )
    return ex.number


def _finish(registry, request, variable, baseline, changed, threshold, after, text, notes=None):
    number = _store(registry, request, variable, {
        "changed": changed, "threshold": threshold if changed else NO_CHANGE,
        "baseline_verdict": baseline, "verdict_at_threshold": after,
    }, notes)
    return SensitivityResult(variable, changed, threshold if changed else NO_CHANGE, baseline, after, number, text)


def _position_size(contract, request, baseline, source, registry) -> SensitivityResult:
    cfg_max = load_config().sensitivity_ranges.get("position_size", (0.0, 0.5, GRID_STEP))[1]
    ctx = rules._context(contract, request, source, ExhibitRegistry())
    name = "position_size"
    if baseline == ACCEPT:
        lo = round(request.weight / GRID_STEP - EPS)
        hi = max(lo, math.floor(cfg_max / GRID_STEP + EPS))
        if lo >= hi or rules._passes_at(contract, request, rules._grid_weight(hi), source, ctx):
            return _finish(registry, request, name, baseline, False, None, None,
                           f"Position size: {NO_CHANGE} (up to {rules._grid_weight(hi):.1%}).")
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if rules._passes_at(contract, request, rules._grid_weight(mid), source, ctx):
                lo = mid
            else:
                hi = mid
        w = rules._grid_weight(hi)
        after = _verdict(contract, replace(request, weight=w), source)
        return _finish(registry, request, name, baseline, True, w, after,
                       f"Position size: the Verdict changes to {after} at {w:.1%}.")
    index = rules._largest_passing_index(contract, request, source, ctx)
    if not index:
        return _finish(registry, request, name, baseline, False, None, None,
                       f"Position size: {NO_CHANGE}; no size from 0.5% up to {request.weight:.1%} passes every rule.")
    w = rules._grid_weight(index)
    after = _verdict(contract, replace(request, weight=w), source)
    return _finish(registry, request, name, baseline, True, w, after,
                   f"Position size: at {w:.1%} or less the Verdict becomes {after}.")


def _limit_sensitivity(contract, request, baseline, source, registry, result: RuleResult) -> SensitivityResult:
    rule = result.rule
    variable = f"contract.{rule}" + (f".{result.detail}" if result.detail and rule in GROUP_LIMITS else "")
    if result.observed is None or (rule not in SCALAR_LIMITS and rule not in GROUP_LIMITS):
        return _finish(registry, request, variable, baseline, False, None, None,
                       f"{rule}: {NO_CHANGE}; the rule has no numeric limit.")
    # The limit that makes the failing rule pass is the observed value; verify by re-evaluation.
    threshold = math.ceil(result.observed * 1e6) / 1e6
    patched = copy.deepcopy(dict(contract))
    if rule in GROUP_LIMITS:
        patched[rule][result.detail] = threshold
    else:
        patched[rule] = threshold
    after = _verdict(patched, request, source)
    if after == baseline:
        return _finish(registry, request, variable, baseline, False, None, None,
                       f"{rule}: {NO_CHANGE}; other rules still fail.")
    return _finish(registry, request, variable, baseline, True, threshold, after,
                   f"{rule}: a limit of {threshold:.1%} (now {result.limit:.1%}) changes the Verdict to {after}.")


def _horizon(request, baseline, registry) -> SensitivityResult:
    low, high, _ = load_config().sensitivity_ranges.get("horizon_years", (1, 20, 1))
    return _finish(registry, request, "horizon_years", baseline, False, None, None,
                   f"Horizon: {NO_CHANGE} ({low:g} to {high:g} years); no Hard_Rule uses it.")


def _stress_period(contract, request, baseline, source, registry) -> SensitivityResult:
    period = metrics.resolve_period(STRESS_PERIOD)
    stressed = replace(request, start=period[0], end=period[1])
    try:
        after = _verdict(contract, stressed, source)
    except Exception as error:  # data missing for the period
        return _finish(registry, request, "period_2022", baseline, False, None, None,
                       f"2022 drawdown period: {NO_CHANGE}; not evaluated ({error}).",
                       [f"2022 evaluation failed: {error}"])
    if after == baseline:
        return _finish(registry, request, "period_2022", baseline, False, None, None,
                       f"2022 drawdown period: {NO_CHANGE}.")
    return _finish(registry, request, "period_2022", baseline, True, STRESS_PERIOD, after,
                   f"Evaluated on the 2022 drawdown period the Verdict becomes {after}.")


def run_sensitivity(
    contract: Mapping[str, Any],
    request: RuleRequest,
    results: list[RuleResult],
    registry: ExhibitRegistry,
    *,
    source,
) -> list[SensitivityResult]:
    """Run every sensitivity variation; each result is stored as one Exhibit."""
    baseline = _verdict(contract, request, source)
    out = [_position_size(contract, request, baseline, source, registry)]
    for result in results:
        if result.status == "fail":
            out.append(_limit_sensitivity(contract, request, baseline, source, registry, result))
    out.append(_horizon(request, baseline, registry))
    out.append(_stress_period(contract, request, baseline, source, registry))
    return out
