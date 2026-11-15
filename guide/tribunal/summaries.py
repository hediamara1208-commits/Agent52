"""Plain-language summaries of at most 60 words for Friendly_Mode (Req. 7.11, 7.12).

Each summary is built from a stage's structured output with a fixed template. No model
text is used. Every number comes from an Exhibit in the registry and keeps its
``[Exhibit N]`` link. ``summarize`` truncates at a sentence boundary so the limit holds.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from guide.toolkit.exhibits import ExhibitRegistry

MAX_WORDS = 60
AGENTS = ("advocate", "investigator", "judge")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def word_count(text: str) -> int:
    return len(text.split())


def summarize(text: str, max_words: int = MAX_WORDS) -> str:
    """Return `text` cut to whole sentences totalling at most `max_words` words.

    If the first sentence alone is too long, cut it at a word boundary, never inside an
    ``[Exhibit N]`` link, and end it with a period.
    """
    text = " ".join(text.split())
    if word_count(text) <= max_words:
        return text
    kept: list[str] = []
    total = 0
    for sentence in _SENTENCE_SPLIT.split(text):
        n = word_count(sentence)
        if total + n > max_words:
            break
        kept.append(sentence)
        total += n
    if kept:
        return " ".join(kept)
    words = text.split()[:max_words]
    while words and _open_link(words):
        words.pop()
    return (" ".join(words).rstrip(",;:") + ".") if words else ""


def _open_link(words: list[str]) -> bool:
    joined = " ".join(words)
    return joined.count("[") > joined.count("]")


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _lookup(value: Any, path: str) -> Any:
    cur = value
    for part in path.split(".") if path else []:
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        elif isinstance(cur, (tuple, list)) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            raise KeyError(path)
    return cur


def figure(registry: ExhibitRegistry, exhibit_number: int, field: str = "",
           kind: str = "num") -> str | None:
    """Format an Exhibit value with its link, or None if the Exhibit or field is missing.

    kind: ``pct`` (fraction shown as a percentage), ``cad`` or ``num``.
    """
    ex = registry.get(exhibit_number)
    if ex is None:
        return None
    try:
        v = _lookup(ex.value, field)
    except KeyError:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return None
    if kind == "pct":
        body = f"{v * 100:.1f}%"
    elif kind == "cad":
        body = f"{v:,.0f} CAD"
    else:
        body = f"{v:g}"
    return f"{body} [Exhibit {ex.number}]"


def _figure_sentences(output: Any, registry: ExhibitRegistry, limit: int = 2) -> list[str]:
    """Sentences for `output["figures"]`; entries whose Exhibit value is missing are skipped.

    Each figure is ``{"exhibit": int, "field": str, "label": str, "kind": str}``.
    """
    out: list[str] = []
    for f in _get(output, "figures", []) or []:
        txt = figure(registry, _get(f, "exhibit"), _get(f, "field", ""), _get(f, "kind", "num"))
        if txt is not None:
            out.append(f"{_get(f, 'label', 'Value')}: {txt}.")
        if len(out) >= limit:
            break
    return out


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _advocate(output: Any, registry: ExhibitRegistry) -> list[str]:
    options = list(_get(output, "options", []) or [])
    parts = []
    goal = (_get(output, "goal", "") or "").strip().rstrip(".")
    if goal:
        parts.append(f"The Advocate sees the goal as: {goal}.")
    parts.append(f"It proposes {_plural(len(options), 'option')} for the court.")
    rejected = [o for o in options if _get(o, "rejected", False)]
    if rejected:
        parts.append(f"{_plural(len(rejected), 'option')} already fail a hard rule.")
    return parts


def _investigator(output: Any, registry: ExhibitRegistry) -> list[str]:
    risks = list(_get(output, "risks", []) or [])
    options = {_get(r, "option") for r in risks if _get(r, "option")}
    parts = [f"The Investigator names {_plural(len(risks), 'material risk')}"
             + (f" across {_plural(len(options), 'option')}." if options else ".")]
    return parts


def _judge(output: Any, registry: ExhibitRegistry) -> list[str]:
    verdict = (_get(output, "verdict", "") or "").replace("_", " ")
    parts = [f"The Judge's verdict is: {verdict}." if verdict else "The Judge has not reached a verdict."]
    failing = list(_get(output, "failing_rules", []) or [])
    if failing:
        parts.append(f"{_plural(len(failing), 'rule')} failed: {', '.join(failing)}.")
    conditions = list(_get(output, "conditions", []) or [])
    if conditions:
        parts.append(f"{_plural(len(conditions), 'condition')} apply.")
    return parts


_BUILDERS = {"advocate": _advocate, "investigator": _investigator, "judge": _judge}


def build_summary(agent: str, output: Any, registry: ExhibitRegistry) -> str:
    """Template summary for one agent stage, at most 60 words, with Exhibit links.

    `output` is the stage's structured output (mapping or object). Figures listed in
    ``output["figures"]`` are read from the registry; missing ones are left out.
    """
    builder = _BUILDERS.get(agent)
    if builder is None:
        raise ValueError(f"no summary template for agent '{agent}'")
    parts = builder(output, registry) + _figure_sentences(output, registry)
    return summarize(" ".join(parts))


def build_summaries(outputs: Mapping[str, Any], registry: ExhibitRegistry) -> dict[str, str]:
    """Summaries for each stage present in `outputs` (agent name -> structured output)."""
    return {a: build_summary(a, outputs[a], registry) for a in AGENTS if a in outputs}
