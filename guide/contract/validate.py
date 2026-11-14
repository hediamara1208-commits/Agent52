"""Schema validation for the Investor_Contract (Req. 1.3, 1.4)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).with_name("schema.json")


@dataclass(frozen=True)
class FieldError:
    """One failing contract field. `field` is a dotted path, e.g. "sector_caps.Technology"."""

    field: str
    message: str


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _field_path(error: Any) -> str:
    parts = [str(p) for p in error.absolute_path]
    if error.validator == "required":
        # message looks like "'name' is a required property"
        parts.append(error.message.split("'")[1])
    return ".".join(parts) if parts else "<contract>"


def validate_contract(c: Any) -> list[FieldError]:
    """Return the failing fields of `c`. An empty list means the contract is valid."""
    if not isinstance(c, dict):
        return [FieldError("<contract>", "contract must be a JSON object")]
    errors: list[FieldError] = []
    seen: set[tuple[str, str]] = set()
    for err in sorted(_validator().iter_errors(c), key=lambda e: [str(p) for p in e.absolute_path]):
        if err.validator == "additionalProperties" and isinstance(err.instance, dict):
            allowed = err.schema.get("properties")
            if allowed is not None:
                for key in sorted(k for k in err.instance if k not in allowed):
                    item = (".".join([*map(str, err.absolute_path), key]), "unexpected field")
                    if item not in seen:
                        seen.add(item)
                        errors.append(FieldError(*item))
                continue
        item = (_field_path(err), err.message)
        if item not in seen:
            seen.add(item)
            errors.append(FieldError(*item))
    return errors
