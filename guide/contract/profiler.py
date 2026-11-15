"""Profiler: builds the Investor_Contract from a Persona_Template or a form.

Deterministic, no model call (Req. 16.11, 16.15). The Persona_File is read only
through a Persona passed in by the caller, never by the blank-form path (16.14).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from guide.contract.personas import SHIPPED_PATH, Persona, load_personas
from guide.contract.validate import FieldError, validate_contract

CONTRACT_FIELDS = (
    "risk_level", "horizon_years", "max_volatility", "max_drawdown", "per_asset_cap",
    "per_asset_class_caps", "crypto_cap", "sector_caps", "esg_exclusions", "speculative_limit",
)
_VALUE_FIELDS = CONTRACT_FIELDS[1:]
_BASIS_TO_PROVENANCE = {
    "quoted": "persona_quoted",
    "assumption": "persona_assumption",
    "user": "user",
}
DEFAULTS: dict[str, Any] = {
    "risk_level": "moderate",
    "horizon_years": 10,
    "max_volatility": 0.20,
    "max_drawdown": 0.25,
    "per_asset_cap": 0.10,
    "per_asset_class_caps": {},
    "crypto_cap": 0.05,
    "sector_caps": {},
    "esg_exclusions": [],
    "speculative_limit": None,
    "soft_preferences": [],
}


def _horizon(h: Any) -> tuple[int, dict[str, Any] | None]:
    """Return (horizon_years, range or None). A range gives its lower bound (Req. 1.10)."""
    if isinstance(h, dict):
        rng = {k: h[k] for k in ("min", "max") if h.get(k) is not None}
        return int(rng["min"]), rng
    return int(h), None


def build_contract_from_persona(persona: Persona) -> dict[str, Any]:
    """Copy Contract_Values only; provenance follows each value's basis."""
    contract: dict[str, Any] = {"risk_level": persona.risk_level}
    risk_fact = persona.facts.get("risk_level")
    risk_prov = "persona_quoted" if risk_fact is not None and risk_fact.excerpt else "persona_assumption"
    provenance = {"risk_level": risk_prov}
    for name in _VALUE_FIELDS:
        cv = persona.contract_values.get(name)
        if cv is None:  # only optional speculative_limit can be absent
            contract[name] = deepcopy(DEFAULTS[name])
            provenance[name] = "default"
        else:
            contract[name] = deepcopy(cv.value)
            provenance[name] = _BASIS_TO_PROVENANCE.get(cv.basis or "", "persona_assumption")
    contract["soft_preferences"] = [
        {
            "id": p.id,
            "text": p.text,
            "provenance": _BASIS_TO_PROVENANCE.get(p.basis or "", "persona_assumption"),
            "excerpt": p.excerpt,
        }
        for p in persona.soft_preferences
    ]
    years, rng = _horizon(persona.horizon)
    if rng is not None:
        contract["horizon_range"] = rng
    contract["horizon_years"] = contract["horizon_years"] if "horizon_years" in persona.contract_values else years
    contract["provenance"] = provenance
    return contract


def _apply_horizon(values: dict[str, Any]) -> tuple[int, dict[str, Any] | None] | None:
    if "horizon" in values:
        return _horizon(values["horizon"])
    if "horizon_min" in values or "horizon_max" in values:
        # Web form fields (frontend ContractValues): horizon_min / horizon_max, either may be null.
        lo, hi = values.get("horizon_min"), values.get("horizon_max")
        if lo is None and hi is None:
            return None
        if lo is None:
            return _horizon(hi)
        return _horizon({"min": lo} if hi is None else {"min": lo, "max": hi})
    if "horizon_years" in values:
        return values["horizon_years"], None
    return None


def build_contract_from_form(values: dict[str, Any], base: Persona | None = None) -> dict[str, Any]:
    """Build a contract from submitted form values.

    With `base`, fields that differ from the template get provenance `user` and
    unchanged fields keep the template provenance. Without `base`, supplied fields
    are `form` and the rest are `default`.
    """
    if base is not None:
        contract = build_contract_from_persona(base)
        supplied_prov = "user"
        changed = lambda k, v: contract.get(k) != v  # noqa: E731
    else:
        contract = deepcopy(DEFAULTS)
        contract["provenance"] = {k: "default" for k in CONTRACT_FIELDS}
        supplied_prov = "form"
        changed = lambda k, v: True  # noqa: E731

    horizon = _apply_horizon(values)
    if horizon is not None:
        years, rng = horizon
        if changed("horizon_years", years) or contract.get("horizon_range") != rng:
            contract["horizon_years"] = years
            contract["provenance"]["horizon_years"] = supplied_prov
        if rng is None:
            contract.pop("horizon_range", None)
        else:
            contract["horizon_range"] = rng

    for key, value in values.items():
        if key in ("horizon", "horizon_years", "horizon_min", "horizon_max"):
            continue
        if key == "soft_preferences":
            # Each item carries its own provenance; items without one take the form's.
            items = [
                {"provenance": supplied_prov, **p} if isinstance(p, dict) else p
                for p in (value if isinstance(value, list) else [])
            ] if isinstance(value, list) else value
            if changed(key, items):
                contract[key] = deepcopy(items)
        elif key not in CONTRACT_FIELDS:
            contract[key] = value  # surfaces as "unexpected field" in schema validation
        elif changed(key, value):
            contract[key] = deepcopy(value)
            contract["provenance"][key] = supplied_prov
    return contract


def validate_contract_for_persona(c: dict[str, Any], persona_id: str) -> list[FieldError]:
    """Check the shipped-template limits of Req. 1.6 to 1.8 on unedited contracts only.

    A contract with any `user` provenance has been edited and is checked by the
    generic schema alone (Req. 1.11).
    """
    prov = c.get("provenance") or {}
    if any(v == "user" for v in prov.values()):
        return []
    errors: list[FieldError] = []

    def below_one(value: Any, field_name: str, label: str) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value >= 1.0:
            errors.append(FieldError(field_name, f"{label} must be below 100 percent for this template"))

    if persona_id == "amira":
        below_one((c.get("per_asset_class_caps") or {}).get("crypto"), "per_asset_class_caps.crypto", "crypto cap")
        below_one((c.get("sector_caps") or {}).get("Information Technology"),
                  "sector_caps.Information Technology", "Information Technology cap")
    elif persona_id == "mateo":
        if not c.get("esg_exclusions"):
            errors.append(FieldError("esg_exclusions", "at least one ESG exclusion is required for this template"))
        below_one(c.get("speculative_limit"), "speculative_limit", "speculative limit")
    elif persona_id == "robert":
        horizon = c.get("horizon_years")
        if not isinstance(horizon, (int, float)) or not 3 <= horizon <= 5:
            errors.append(FieldError("horizon_years", "horizon must be between 3 and 5 years for this template"))
        others = [
            p.contract_values["crypto_cap"].value
            for pid, p in load_personas(SHIPPED_PATH).personas.items()
            if pid in ("amira", "mateo") and "crypto_cap" in p.contract_values
        ]
        crypto = c.get("crypto_cap")
        if others and (not isinstance(crypto, (int, float)) or crypto >= min(others)):
            errors.append(FieldError("crypto_cap", "crypto cap must be lower than those of amira and mateo"))
    return errors


__all__ = [
    "CONTRACT_FIELDS", "DEFAULTS", "build_contract_from_persona", "build_contract_from_form",
    "validate_contract_for_persona", "validate_contract", "FieldError",
]
