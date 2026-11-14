"""Configuration loaded from environment variables and ``config.yaml``.

Environment variables (prefix ``GUIDE_``) override file values. There are no
credential fields: AWS credentials come from the default AWS credential chain.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
_ENV_PREFIX = "GUIDE_"
_REMOVED_DATA_LOCATION_MESSAGE = (
    "data_location has been removed: Amazon S3 is always the primary data store. "
    "Configure cache_dir for local cached copies."
)


@dataclass(frozen=True)
class Config:
    aws_region: str = "us-east-1"
    model_id: str = ""
    guardrail_id: str = ""
    guardrail_version: str = "DRAFT"
    s3_bucket: str = ""
    s3_prefix: str = "dataset"
    cache_dir: str = "/workshop/Agent52/.cache/dataset"
    s3_connect_timeout_seconds: int = 3
    s3_read_timeout_seconds: int = 10
    s3_max_attempts: int = 3
    glue_database: str = "alphaforge_guide"
    athena_workgroup: str = "alphaforge-guide"
    athena_results_uri: str = "s3://alphaforge-guide-athena-results/results/"
    athena_bytes_scanned_cutoff: int = 104_857_600
    seed_dir: str = "/workshop/Agent52/data"
    persona_file: str = "guide/contract/personas.yaml"
    instruction_dir: str = "guide/agents"
    sensitivity_ranges: dict[str, tuple[float, float, float]] = field(
        default_factory=lambda: {
            "position_size": (0.0, 0.5, 0.01),
            "horizon_years": (1.0, 20.0, 1.0),
        }
    )
    speculative_volatility_threshold: float = 0.50
    trace_summary_max_chars: int = 400
    session_table: str = "alphaforge-guide-sessions"
    agent_runtime_arn: str = ""
    agentcore_memory_id: str = ""
    cors_origin: str = ""
    macro_publication_lag_days: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.s3_bucket.strip():
            raise ValueError("s3_bucket is required because Amazon S3 is the primary data store")

        positive_ints = {
            "s3_connect_timeout_seconds": self.s3_connect_timeout_seconds,
            "s3_read_timeout_seconds": self.s3_read_timeout_seconds,
            "s3_max_attempts": self.s3_max_attempts,
            "trace_summary_max_chars": self.trace_summary_max_chars,
        }
        for name, value in positive_ints.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.athena_bytes_scanned_cutoff < 0:
            raise ValueError("athena_bytes_scanned_cutoff must be zero or greater")
        if self.speculative_volatility_threshold < 0:
            raise ValueError("speculative_volatility_threshold must be zero or greater")

        for name, value in self.sensitivity_ranges.items():
            if len(value) != 3:
                raise ValueError(f"sensitivity_ranges.{name} must contain minimum, maximum, and step")
            minimum, maximum, step = value
            if minimum > maximum or step <= 0:
                raise ValueError(f"sensitivity_ranges.{name} must have minimum <= maximum and a positive step")

    def macro_lag(self, series_id: str) -> int:
        """Publication lag in days for a macro series (0 if not configured)."""
        return int(self.macro_publication_lag_days.get(series_id, 0))


def _config_error_for_removed_data_location(values: dict[str, Any], env: dict[str, str]) -> None:
    if "data_location" in values or env.get("GUIDE_DATA_LOCATION"):
        raise ValueError(_REMOVED_DATA_LOCATION_MESSAGE)


def _coerce_environment_value(name: str, value: str) -> Any:
    """Parse structured and numeric ``GUIDE_*`` values using YAML scalars."""
    if name in {"macro_publication_lag_days", "sensitivity_ranges"}:
        parsed = yaml.safe_load(value)
        if not isinstance(parsed, dict):
            raise ValueError(f"GUIDE_{name.upper()} must be a mapping")
        return parsed
    if name in {
        "s3_connect_timeout_seconds",
        "s3_read_timeout_seconds",
        "s3_max_attempts",
        "athena_bytes_scanned_cutoff",
        "trace_summary_max_chars",
    }:
        return int(value)
    if name == "speculative_volatility_threshold":
        return float(value)
    return value


def _normalise_values(values: dict[str, Any]) -> dict[str, Any]:
    if "macro_publication_lag_days" in values:
        macro_lags = values["macro_publication_lag_days"] or {}
        if not isinstance(macro_lags, dict):
            raise ValueError("macro_publication_lag_days must be a mapping")
        values["macro_publication_lag_days"] = {str(k): int(v) for k, v in macro_lags.items()}

    if "sensitivity_ranges" in values:
        ranges = values["sensitivity_ranges"] or {}
        if not isinstance(ranges, dict):
            raise ValueError("sensitivity_ranges must be a mapping")
        try:
            values["sensitivity_ranges"] = {
                str(name): tuple(float(item) for item in value) for name, value in ranges.items()
            }
        except (TypeError, ValueError) as error:
            raise ValueError("sensitivity_ranges values must be numeric three-item sequences") from error
    return values


def load_config(path: str | os.PathLike | None = None, env: dict[str, str] | None = None) -> Config:
    """Load config from YAML then apply ``GUIDE_*`` environment overrides."""
    env = os.environ if env is None else env
    cfg_path = Path(path or env.get("GUIDE_CONFIG", DEFAULT_CONFIG_PATH))
    values: dict[str, Any] = {}
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        if not isinstance(loaded, dict):
            raise ValueError("configuration YAML must contain a mapping")
        values = loaded

    _config_error_for_removed_data_location(values, env)

    names = {item.name for item in fields(Config)}
    values = {key: value for key, value in values.items() if key in names}
    for name in names:
        key = _ENV_PREFIX + name.upper()
        if key in env and env[key] != "":
            values[name] = _coerce_environment_value(name, env[key])

    return Config(**_normalise_values(values))


# --- Log redaction -------------------------------------------------------

_AWS_PATTERNS = [
    re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA)[A-Z0-9]{16}\b"),  # access key ids
    re.compile(r"(?i)(aws_secret_access_key|aws_session_token|secret_?access_?key)(\s*[=:]\s*)\S+"),
    re.compile(r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])"),  # 40-char secret keys
]
REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    text = _AWS_PATTERNS[0].sub(REDACTED, text)
    text = _AWS_PATTERNS[1].sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    # Only redact 40-char blobs that mix letters and digits (avoids plain words/paths).
    def _blob(m: re.Match) -> str:
        s = m.group(0)
        return REDACTED if any(c.isdigit() for c in s) and any(c.isalpha() for c in s) else s

    return _AWS_PATTERNS[2].sub(_blob, text)


class RedactingFilter(logging.Filter):
    """Redacts AWS key patterns from log messages and their arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.getMessage()))
        record.args = None
        return True


def install_log_redaction(logger: logging.Logger | None = None) -> RedactingFilter:
    """Attach the filter to the root logger's handlers (and logger itself)."""
    flt = RedactingFilter()
    target = logger or logging.getLogger()
    target.addFilter(flt)
    for handler in target.handlers:
        handler.addFilter(flt)
    return flt
