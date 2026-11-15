"""Tolerant Persona_File loader (Req. 16.2, 16.3, 16.5, 16.6)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml
from jsonschema import Draft202012Validator

SHIPPED_PATH = Path(__file__).with_name("personas.yaml")
SCHEMA_PATH = Path(__file__).with_name("personas.schema.json")


class PersonaFileError(Exception):
    """The Persona_File is missing, unreadable, or not parsable YAML."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class PersonaFact:
    value: Any
    excerpt: str | tuple[str, ...] | None = None


@dataclass(frozen=True)
class ContractValue:
    value: Any
    basis: str | None = None  # quoted | assumption | user
    rationale: str | None = None
    excerpt: str | tuple[str, ...] | None = None


@dataclass(frozen=True)
class SoftPreference:
    id: str
    text: str
    basis: str | None = None  # quoted | assumption | user
    excerpt: str | None = None


@dataclass(frozen=True)
class Persona:
    id: str
    display_name: str
    risk_level: str
    horizon: Any  # number or {"min": x, "max": y}
    facts: Mapping[str, PersonaFact] = field(default_factory=dict)
    contract_values: Mapping[str, ContractValue] = field(default_factory=dict)
    soft_preferences: tuple[SoftPreference, ...] = ()


@dataclass(frozen=True)
class PersonaLoadResult:
    personas: Mapping[str, Persona]
    field_errors: tuple[tuple[str, str], ...]


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _error_field(err: Any) -> str:
    path = [str(p) for p in err.absolute_path]
    if err.validator == "required":
        path.append(err.message.split("'")[1])
    if not path:
        return "<entry>"
    if path[0] in ("contract_values", "facts", "soft_preferences") and len(path) > 1:
        return ".".join(path[:2])
    return path[0]


def _excerpt(raw: Any) -> str | tuple[str, ...] | None:
    return tuple(raw) if isinstance(raw, list) else raw


def _to_persona(entry: dict[str, Any]) -> Persona:
    facts = {
        k: PersonaFact(v["value"], _excerpt(v.get("excerpt")))
        for k, v in (entry.get("facts") or {}).items()
    }
    values = {
        k: ContractValue(v["value"], v.get("basis"), v.get("rationale"), _excerpt(v.get("excerpt")))
        for k, v in entry["contract_values"].items()
    }
    prefs = tuple(
        SoftPreference(p["id"], p["text"], p.get("basis"), p.get("excerpt"))
        for p in entry.get("soft_preferences") or []
    )
    return Persona(
        entry["id"], entry["display_name"], entry["risk_level"], entry["horizon"], facts, values, prefs
    )


def _entries(data: Any) -> list[Any]:
    raw = data.get("personas") if isinstance(data, dict) else None
    if isinstance(raw, dict):  # mapping keyed by id is accepted too
        return [{"id": k, **v} if isinstance(v, dict) and "id" not in v else v for k, v in raw.items()]
    if isinstance(raw, list):
        return raw
    raise PersonaFileError("the file has no 'personas' list")


def load_personas(path: Path | str = SHIPPED_PATH) -> PersonaLoadResult:
    """Return every valid entry and the (persona id, field) errors of excluded entries."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise PersonaFileError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise PersonaFileError(f"cannot parse {path}: {exc}") from exc

    personas: dict[str, Persona] = {}
    errors: list[tuple[str, str]] = []
    for n, entry in enumerate(_entries(data), start=1):
        label = f"entry {n}"
        if not isinstance(entry, dict):
            errors.append((label, "<entry>"))
            continue
        if isinstance(entry.get("id"), str) and entry["id"]:
            label = entry["id"]
        found = {(label, _error_field(e)) for e in _validator().iter_errors(entry)}
        if label in personas and not found:
            found.add((label, "id"))
        if found:
            errors.extend(sorted(found))
            continue
        personas[label] = _to_persona(entry)
    return PersonaLoadResult(personas, tuple(errors))
