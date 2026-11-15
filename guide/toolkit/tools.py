"""Bedrock Converse tool specs and tool runner for the Toolkit (Req. 2.8).

Input schemas are generated from the signatures of the metric functions. The
session's ``registry``, ``source`` and ``as_of`` are bound by the runner, so a
model can never choose them. A ``toolUse`` block is dispatched to the function;
the ``toolResult`` carries the Exhibit number and value, or an error with no
Exhibit.
"""
from __future__ import annotations

import inspect
import typing
from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from guide.data.loader import DataSource
from guide.toolkit import metrics
from guide.toolkit.exhibits import Exhibit, ExhibitRegistry, thaw
from guide.toolkit.metrics import INVALID_ARGUMENT, ToolError

UNKNOWN_TOOL = "UNKNOWN_TOOL"

_BOUND_PARAMS = ("registry", "source", "as_of", "contract")

_TOOLS: dict[str, tuple[Callable[..., Exhibit | ToolError], str]] = {
    "annualized_return": (
        metrics.annualized_return,
        "Annualized return of one asset from adj_close, in CAD. Returns an Exhibit number and value.",
    ),
    "annualized_volatility": (
        metrics.annualized_volatility,
        "Annualized volatility of one asset from adj_close returns, in CAD. Returns an Exhibit number and value.",
    ),
    "max_drawdown": (
        metrics.max_drawdown,
        "Maximum drawdown of one asset with peak and trough dates. Returns an Exhibit number and value.",
    ),
    "correlation": (
        metrics.correlation,
        "Correlation of daily returns of two assets. Returns an Exhibit number and value.",
    ),
    "drawdown_in_period": (
        metrics.drawdown_in_period,
        "Maximum drawdown of one asset in a named year such as \"2022\" or a [start, end] range.",
    ),
    "portfolio_metrics": (
        metrics.portfolio_metrics,
        "Return, volatility and drawdown of a daily-rebalanced portfolio. Weights are fractions that sum to 1.",
    ),
    "risk_contribution": (
        metrics.risk_contribution,
        "Each asset's percentage share of total portfolio variance. Weights are fractions that sum to 1.",
    ),
    "portfolio_comparison": (
        metrics.portfolio_comparison,
        "Volatility, max drawdown, worst rolling 252-day return, 2022 return and annualized return "
        "of a base and a proposed portfolio. Weights are fractions that sum to 1.",
    ),
    "max_weight_within_contract": (
        metrics.max_weight_within_contract,
        "Largest position size of one asset, in 0.5-point steps, at which every Hard_Rule of the "
        "session's Investor_Contract passes; 0 when no positive size passes.",
    ),
}


def _strip_optional(annotation: Any) -> Any:
    args = [a for a in typing.get_args(annotation) if a is not type(None)]
    if len(args) == 1 and len(typing.get_args(annotation)) == 2:
        return args[0]
    return annotation


def _json_type(annotation: Any, name: str) -> dict[str, Any]:
    text = str(annotation)
    if name == "period_name_or_range":
        return {
            "description": "Year name such as \"2022\", or a [start, end] pair of ISO dates.",
            "oneOf": [
                {"type": "string"},
                {"type": "array", "items": {"type": "string", "format": "date"}, "minItems": 2, "maxItems": 2},
            ],
        }
    if "Mapping" in text or "dict" in text:
        return {"type": "object", "additionalProperties": {"type": "number", "minimum": 0}}
    if "date" in text:
        return {"type": "string", "format": "date", "description": "ISO date YYYY-MM-DD"}
    if annotation is float or text == "float":
        return {"type": "number"}
    if annotation is int or text == "int":
        return {"type": "integer"}
    return {"type": "string"}


def input_schema(func: Callable[..., Any]) -> dict[str, Any]:
    """Build a JSON schema from the function signature, hiding bound parameters."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in inspect.signature(func).parameters.items():
        if name in _BOUND_PARAMS:
            continue
        properties[name] = _json_type(param.annotation, name)
        if param.default is inspect.Parameter.empty:
            required.append(name)
        elif isinstance(param.default, str):
            properties[name]["default"] = param.default
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def tool_specs() -> list[dict[str, Any]]:
    """Bedrock Converse ``toolSpec`` entries for every Toolkit function."""
    return [
        {"toolSpec": {"name": name, "description": description, "inputSchema": {"json": input_schema(func)}}}
        for name, (func, description) in _TOOLS.items()
    ]


def tool_config() -> dict[str, Any]:
    """Complete Converse ``toolConfig`` value."""
    return {"tools": tool_specs()}


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"not an ISO date: {value!r}")


class ToolRunner:
    """Dispatches Converse ``toolUse`` blocks to Toolkit functions for one session."""

    def __init__(
        self,
        registry: ExhibitRegistry,
        source: DataSource,
        as_of: date | None = None,
        contract: Mapping[str, Any] | None = None,
    ) -> None:
        self.registry = registry
        self.source = source
        self.as_of = as_of
        self.contract = contract

    def tool_config(self) -> dict[str, Any]:
        return tool_config()

    def run(self, tool_use: Mapping[str, Any]) -> dict[str, Any]:
        return self(tool_use)

    def __call__(self, tool_use: Mapping[str, Any]) -> dict[str, Any]:
        name = str(tool_use.get("name", ""))
        entry = _TOOLS.get(name)
        if entry is None:
            return self._error(ToolError(UNKNOWN_TOOL, name or "missing tool name"))
        func = entry[0]
        raw = tool_use.get("input") or {}
        if not isinstance(raw, Mapping):
            return self._error(ToolError(INVALID_ARGUMENT, "input must be an object"))
        schema = input_schema(func)
        unknown = sorted(set(raw) - set(schema["properties"]))
        missing = [k for k in schema["required"] if k not in raw]
        if unknown or missing:
            detail = "; ".join(
                part for part in (
                    f"unknown arguments: {', '.join(unknown)}" if unknown else "",
                    f"missing arguments: {', '.join(missing)}" if missing else "",
                ) if part
            )
            return self._error(ToolError(INVALID_ARGUMENT, detail))
        try:
            kwargs = self._convert(func, raw)
        except (TypeError, ValueError) as error:
            return self._error(ToolError(INVALID_ARGUMENT, str(error)))

        params = inspect.signature(func).parameters
        if "contract" in params:
            if self.contract is None:
                return self._error(ToolError(INVALID_ARGUMENT, "no Investor_Contract bound to this session"))
            kwargs["contract"] = self.contract
        result = func(self.registry, self.source, as_of=self.as_of, **kwargs) \
            if "as_of" in params \
            else func(self.registry, self.source, **kwargs)
        if isinstance(result, ToolError):
            return self._error(result)
        return {
            "status": "success",
            "exhibit_number": result.number,
            "content": [{"json": {"exhibit_number": result.number, "metric": result.metric,
                                  "value": thaw(result.value)}}],
        }

    @staticmethod
    def _convert(func: Callable[..., Any], raw: Mapping[str, Any]) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        for key, value in raw.items():
            if key in ("start", "end"):
                kwargs[key] = _parse_date(value)
            elif key == "period_name_or_range" and isinstance(value, (list, tuple)):
                if len(value) != 2:
                    raise ValueError("period must be a year name or a [start, end] pair")
                kwargs[key] = (_parse_date(value[0]), _parse_date(value[1]))
            elif key in ("weights", "base", "proposed"):
                if not isinstance(value, Mapping):
                    raise TypeError(f"{key} must be an object of ticker to fraction")
                kwargs[key] = dict(value)
            else:
                kwargs[key] = value
        return kwargs

    @staticmethod
    def _error(error: ToolError) -> dict[str, Any]:
        return {"status": "error", "content": [{"json": error.to_dict()}]}
