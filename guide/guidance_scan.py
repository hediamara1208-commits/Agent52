"""Static checks for the Guidance_Only_Rule.

The scanner deliberately looks only for prohibited brokerage or bank integrations
and their credentials.  It does not inspect user requests or agent output; those
are handled by the runtime guidance-only check and Bedrock Guardrail.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Pattern, Sequence
import re


@dataclass(frozen=True)
class ScanPattern:
    """A named regular expression used by the guidance-only static scanner."""

    name: str
    expression: Pattern[str]


@dataclass(frozen=True)
class GuidanceScanFinding:
    """One prohibited client import or credential identifier in scanned text."""

    pattern: str
    line: int
    column: int
    match: str
    path: str | None = None


# These are package names for brokerage and bank API clients.  Matching is
# limited to import statements so ordinary prose about a provider is allowed.
_CLIENT_MODULES = (
    r"(?:alpaca(?:_trade_api)?|ib_insync|ibapi|robin_stocks|robinhood|"
    r"tastytrade|tradier|schwab|tda(?:_api)?|plaid|dwolla|truelayer|"
    r"yodlee|finicity|gocardless|saltedge|openbanking|ccxt|coinbase"
    r"(?:_advanced_py)?|oandapyv20)"
)

_IMPORT_EXPRESSION = re.compile(
    rf"""(?imx)
    ^\s*(?:
        from\s+{_CLIENT_MODULES}(?:[.\s]|$)
      | import\s+{_CLIENT_MODULES}(?:[.\s]|$)
      | import\s+(?:[^\n;]+?\s+from\s+)?[\"']{_CLIENT_MODULES}(?:[/\.\"']|$)
      | (?:const|let|var)\s+\w+\s*=\s*require\(\s*[\"']{_CLIENT_MODULES}(?:[/\.\"']|$)
    )
    """
)

# A credential field is unsafe even when its value is empty.  Provider-specific
# prefixes also catch conventional environment-variable names such as APCA keys.
_CREDENTIAL_EXPRESSION = re.compile(
    r"""(?ix)
    \b(?:
        (?:brokerage|bank)[_-]?(?:api[_-]?)?
            (?:key(?:[_-]?id)?|secret(?:[_-]?key)?|token|password|session[_-]?token)
      |
        (?:alpaca|apca|ibkr|interactive[_-]?brokers|robinhood|tastytrade|tradier|
        schwab|plaid|dwolla|truelayer|yodlee|finicity|gocardless)[_-]?
        (?:api[_-]?)?(?:key(?:[_-]?id)?|secret(?:[_-]?key)?|token|password|session[_-]?token)
    )\b
    """
)

DEFAULT_PATTERNS: tuple[ScanPattern, ...] = (
    ScanPattern("brokerage_or_bank_api_client_import", _IMPORT_EXPRESSION),
    ScanPattern("brokerage_or_bank_credential", _CREDENTIAL_EXPRESSION),
)


def scan_text(
    text: str,
    patterns: Sequence[ScanPattern] = DEFAULT_PATTERNS,
    *,
    path: str | None = None,
) -> list[GuidanceScanFinding]:
    """Return every configured prohibited-pattern match in ``text``.

    ``patterns`` is an explicit input so repository checks can use the same
    scanner with an approved, reviewable pattern list.  Findings are ordered by
    text position, then by configured pattern order.
    """
    findings: list[tuple[int, int, GuidanceScanFinding]] = []
    for pattern_index, pattern in enumerate(patterns):
        for match in pattern.expression.finditer(text):
            offset = match.start()
            line = text.count("\n", 0, offset) + 1
            previous_newline = text.rfind("\n", 0, offset)
            column = offset + 1 if previous_newline == -1 else offset - previous_newline
            findings.append(
                (
                    offset,
                    pattern_index,
                    GuidanceScanFinding(
                        pattern=pattern.name,
                        line=line,
                        column=column,
                        match=match.group(0),
                        path=path,
                    ),
                )
            )
    findings.sort(key=lambda item: (item[0], item[1]))
    return [finding for _, _, finding in findings]


def scan_file(
    path: str | Path,
    patterns: Sequence[ScanPattern] = DEFAULT_PATTERNS,
) -> list[GuidanceScanFinding]:
    """Read one UTF-8 source or configuration file and return its findings."""
    file_path = Path(path)
    return scan_text(file_path.read_text(encoding="utf-8"), patterns, path=str(file_path))


def scan_files(
    paths: Iterable[str | Path],
    patterns: Sequence[ScanPattern] = DEFAULT_PATTERNS,
) -> list[GuidanceScanFinding]:
    """Scan each supplied source or configuration file in iteration order."""
    findings: list[GuidanceScanFinding] = []
    for path in paths:
        findings.extend(scan_file(path, patterns))
    return findings
