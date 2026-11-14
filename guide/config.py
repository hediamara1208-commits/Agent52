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
DEFAULT_DATA_DIR = "/workshop/Agent52/data"
_ENV_PREFIX = "GUIDE_"


@dataclass(frozen=True)
class Config:
    aws_region: str = "us-east-1"
    model_id: str = ""
    guardrail_id: str = ""
    guardrail_version: str = "DRAFT"
    s3_bucket: str = ""
    s3_prefix: str = "data"
    data_location: str = "local"  # "local" or "s3"
    data_dir: str = DEFAULT_DATA_DIR
    macro_publication_lag_days: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.data_location not in ("local", "s3"):
            raise ValueError(f"data_location must be 'local' or 's3', got {self.data_location!r}")

    def macro_lag(self, series_id: str) -> int:
        """Publication lag in days for a macro series (0 if not configured)."""
        return int(self.macro_publication_lag_days.get(series_id, 0))


def load_config(path: str | os.PathLike | None = None, env: dict[str, str] | None = None) -> Config:
    """Load config from YAML (if present) then apply ``GUIDE_*`` env overrides."""
    env = os.environ if env is None else env
    cfg_path = Path(path or env.get("GUIDE_CONFIG", DEFAULT_CONFIG_PATH))
    values: dict[str, Any] = {}
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as fh:
            values = yaml.safe_load(fh) or {}
    names = {f.name for f in fields(Config)}
    values = {k: v for k, v in values.items() if k in names}
    for name in names - {"macro_publication_lag_days"}:
        key = _ENV_PREFIX + name.upper()
        if key in env and env[key] != "":
            values[name] = env[key]
    if "macro_publication_lag_days" in values:
        values["macro_publication_lag_days"] = {
            str(k): int(v) for k, v in (values["macro_publication_lag_days"] or {}).items()
        }
    return Config(**values)


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
