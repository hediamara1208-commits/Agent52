"""Benchmark runner (Req. 34.1 to 34.3, 34.5): N runs per case and arm, Wilson intervals,
Confidence_Labels, and the budget guard. Writes ``docs/benchmark.json`` and ``docs/benchmark.md``.

Runners are injected so tests use fakes; ``main`` wires the real ones (Bedrock).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import yaml

from guide.bench.stats import Label, confidence_label, wilson_interval

ARMS = ("guide", "baseline")
GUIDE_CALLS_PER_RUN = 3  # Advocate, Investigator, Judge (Req. 36)
BASELINE_CALLS_PER_RUN = 1
CONFIRM_ABOVE_CALLS = 300
MIN_PUBLISHED_N = 5
MIN_CASES = 10
ACCEPTING = ("accept", "accept_with_conditions")
RATE_METRICS = ("verdict_match", "yes_man", "number_verified", "number_unverifiable")
MEAN_METRICS = ("latency_seconds", "tokens")
_NUMBER_RE = re.compile(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?(\s*%)?")


@dataclass(frozen=True)
class Case:
    id: str
    ticker: str
    weight: float
    expected: tuple[str, ...]  # accepted Verdicts for "matches the expected outcome"
    violates_hard_rule: bool
    start: date
    end: date
    text: str = ""
    as_of: date | None = None
    persona: str | None = None
    contract: Mapping[str, Any] | None = None
    base_portfolio: Mapping[str, float] | None = None
    source: str = ""


@dataclass(frozen=True)
class RunRecord:
    verdict: str
    latency_seconds: float
    tokens: int | None
    numbers_total: int
    numbers_matched: int  # match an Exhibit
    calls: int


GuideRunner = Callable[[Case], RunRecord]
BaselineRunner = Callable[[Case], RunRecord]


# ---------------------------------------------------------------- cases

def load_cases(paths: Iterable[Path | str]) -> list[Case]:
    cases: list[Case] = []
    for path in paths:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        entries = data.get("cases", data) if isinstance(data, Mapping) else data
        for raw in entries:
            exp = raw["expected"]
            if isinstance(exp, Mapping):
                exp = exp.get("verdict", exp.get("outcome"))
            cases.append(Case(
                id=str(raw["id"]), ticker=str(raw["ticker"]), weight=float(raw["weight"]),
                expected=(exp,) if isinstance(exp, str) else tuple(exp),
                violates_hard_rule=bool(raw.get("violates_hard_rule", False)),
                start=_date(raw["start"]), end=_date(raw["end"]), text=str(raw.get("text", "")),
                as_of=_date(raw["as_of"]) if raw.get("as_of") else None,
                persona=raw.get("persona") or raw.get("profile"), contract=raw.get("contract"),
                base_portfolio=raw.get("base_portfolio"), source=str(path)))
    ids = [c.id for c in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("case ids must be unique across the case files")
    return cases


def _date(value: Any) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


# ---------------------------------------------------------------- numbers

def extract_numbers(text: str) -> list[tuple[float, int, bool]]:
    """(value, decimals as written, is_percent) for each number in ``text``."""
    out = []
    for m in _NUMBER_RE.finditer(text):
        raw = m.group(0).replace(",", "").replace("%", "").strip()
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        out.append((float(raw), decimals, bool(m.group(1))))
    return out


def exhibit_scalars(exhibits: Any) -> list[float]:
    """Every numeric leaf of the Exhibits (bools excluded)."""
    found: list[float] = []

    def walk(v: Any) -> None:
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            found.append(float(v))
        elif isinstance(v, Mapping):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)

    walk(exhibits)
    return found


def count_numbers(text: str, exhibits: Any) -> tuple[int, int]:
    """(numbers in the text, numbers matching an Exhibit value to the stated precision).
    A number written with ``%`` also matches the Exhibit value divided by 100 form."""
    values = exhibit_scalars(exhibits)
    numbers = extract_numbers(text)
    matched = 0
    for n, decimals, pct in numbers:
        tol = 0.5 * 10 ** -decimals
        for v in values:
            if abs(n - v) <= tol or (pct and abs(n - v * 100) <= tol):
                matched += 1
                break
    return len(numbers), matched


def strings_in(value: Any) -> str:
    parts: list[str] = []

    def walk(v: Any) -> None:
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, Mapping):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)

    walk(value)
    return "\n".join(parts)


# ---------------------------------------------------------------- budget

def planned_calls(n_cases: int, n_runs: int) -> int:
    return n_cases * n_runs * (GUIDE_CALLS_PER_RUN + BASELINE_CALLS_PER_RUN)


def check_budget(n_cases: int, n_runs: int, *, confirm: Callable[[str], bool],
                 assume_yes: bool = False, out: Callable[[str], None] = print) -> bool:
    """Print the planned number of Bedrock calls; above 300, proceed only on confirmation."""
    total = planned_calls(n_cases, n_runs)
    out(f"Planned Bedrock calls: {total} ({n_cases} cases x {n_runs} runs x "
        f"{GUIDE_CALLS_PER_RUN} guide + {BASELINE_CALLS_PER_RUN} baseline calls)")
    if total <= CONFIRM_ABOVE_CALLS or assume_yes:
        return True
    return bool(confirm(f"{total} calls exceed {CONFIRM_ABOVE_CALLS}. Continue? [y/N] "))


# ---------------------------------------------------------------- aggregation



def arm_counts(runs: Sequence[tuple[Case, RunRecord]]) -> dict[str, tuple[int, int]]:
    """(successes, trials) per rate metric over (case, run) pairs."""
    match = sum(r.verdict in c.expected for c, r in runs)
    violating = [(c, r) for c, r in runs if c.violates_hard_rule]
    yes_man = sum(r.verdict == "accept" for _, r in violating)
    total = sum(r.numbers_total for _, r in runs)
    matched = sum(r.numbers_matched for _, r in runs)
    return {
        "verdict_match": (match, len(runs)),
        "yes_man": (yes_man, len(violating)),
        "number_verified": (matched, total),
        "number_unverifiable": (total - matched, total),
    }


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize_arm(runs: Sequence[tuple[Case, RunRecord]]) -> dict[str, Any]:
    out: dict[str, Any] = {"runs": len(runs), "calls": sum(r.calls for _, r in runs)}
    for name, (k, n) in arm_counts(runs).items():
        lo, hi = wilson_interval(k, n)
        out[name] = {"successes": k, "n": n, "rate": (k / n if n else None), "ci95": [lo, hi]}
    out["latency_seconds"] = _mean([r.latency_seconds for _, r in runs])
    out["tokens"] = _mean([float(r.tokens) for _, r in runs if r.tokens is not None])
    return out


def build_results(cases: Sequence[Case], records: Mapping[str, Mapping[str, list[RunRecord]]],
                  n_runs: int, meta: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """``records[arm][case_id]`` is the list of N RunRecords."""
    by_id = {c.id: c for c in cases}
    pairs = {arm: [(by_id[cid], r) for cid, rs in records[arm].items() for r in rs] for arm in ARMS}
    overall = {arm: summarize_arm(pairs[arm]) for arm in ARMS}
    counts = {arm: arm_counts(pairs[arm]) for arm in ARMS}
    labels: dict[str, Label] = {m: confidence_label(counts["guide"][m], counts["baseline"][m])
                                for m in RATE_METRICS}
    for m in MEAN_METRICS:
        labels[m] = "Context"  # means are not rates; no interval, not a measured difference
    per_case: dict[str, Any] = {}
    for c in cases:
        per_case[c.id] = {"expected": list(c.expected), "violates_hard_rule": c.violates_hard_rule,
                          "source": c.source}
        cc = {}
        for arm in ARMS:
            cc[arm] = arm_counts([(c, r) for r in records[arm].get(c.id, [])])
            per_case[c.id][arm] = summarize_arm([(c, r) for r in records[arm].get(c.id, [])])
        per_case[c.id]["labels"] = {m: confidence_label(cc["guide"][m], cc["baseline"][m])
                                    for m in RATE_METRICS}
    return {"n_runs": n_runs, "n_cases": len(cases),
            "published": n_runs >= MIN_PUBLISHED_N and len(cases) >= MIN_CASES,
            "meta": dict(meta or {}), "overall": overall, "labels": labels, "cases": per_case}


# ---------------------------------------------------------------- execution

def run_benchmark(cases: Sequence[Case], n_runs: int, guide: GuideRunner, baseline: BaselineRunner,
                  *, confirm: Callable[[str], bool] = lambda _: False, assume_yes: bool = False,
                  out: Callable[[str], None] = print, meta: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    """Run both arms. Returns None (and makes no call) when the budget guard is not confirmed.
    A runner reporting more calls than its arm allows aborts the benchmark."""
    if n_runs < 1:
        raise ValueError("N must be at least 1")
    if not check_budget(len(cases), n_runs, confirm=confirm, assume_yes=assume_yes, out=out):
        out("Aborted: no Bedrock call was made.")
        return None
    limits = {"guide": GUIDE_CALLS_PER_RUN, "baseline": BASELINE_CALLS_PER_RUN}
    runners = {"guide": guide, "baseline": baseline}
    records: dict[str, dict[str, list[RunRecord]]] = {arm: {c.id: [] for c in cases} for arm in ARMS}
    for case in cases:
        for _ in range(n_runs):
            for arm in ARMS:
                rec = runners[arm](case)
                if rec.calls > limits[arm]:
                    raise RuntimeError(f"{arm} arm used {rec.calls} model calls on case {case.id}; "
                                       f"the limit is {limits[arm]}")
                records[arm][case.id].append(rec)
    return build_results(cases, records, n_runs, meta)


# ---------------------------------------------------------------- output

def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def _cell(m: Mapping[str, Any]) -> str:
    lo, hi = m["ci95"]
    return f"{_pct(m['rate'])} [{100 * lo:.1f}, {100 * hi:.1f}] ({m['successes']}/{m['n']})"


def render_markdown(results: Mapping[str, Any]) -> str:
    g, b = results["overall"]["guide"], results["overall"]["baseline"]
    lines = ["# Benchmark", "",
             f"N = {results['n_runs']} runs per case and arm, {results['n_cases']} cases. "
             "Rates show the Wilson 95 % interval in brackets. "
             "Labels: Measured (intervals do not overlap), Indicative (they overlap), Context (not measured).",
             ""]
    if not results["published"]:
        lines += [f"**Not publishable**: the published result needs N >= {MIN_PUBLISHED_N} and "
                  f">= {MIN_CASES} cases.", ""]
    names = {"verdict_match": "Verdict matches expected", "yes_man": "Yes-man rate (accepts a violating request)",
             "number_verified": "Numbers matching an Exhibit", "number_unverifiable": "Numbers not verifiable"}
    lines += ["| Metric | Guide_System | Baseline_Agent | Label |", "| --- | --- | --- | --- |"]
    for m in RATE_METRICS:
        lines.append(f"| {names[m]} | {_cell(g[m])} | {_cell(b[m])} | {results['labels'][m]} |")
    for m, label in (("latency_seconds", "Mean latency (s)"), ("tokens", "Mean tokens")):
        f = lambda v: "n/a" if v is None else f"{v:.1f}"
        lines.append(f"| {label} | {f(g[m])} | {f(b[m])} | {results['labels'][m]} |")
    lines += ["", "## Per case", "", "| Case | Expected | Guide match | Baseline match | Label |",
              "| --- | --- | --- | --- | --- |"]
    for cid, c in results["cases"].items():
        lines.append(f"| {cid} | {', '.join(c['expected'])} | {_cell(c['guide']['verdict_match'])} | "
                     f"{_cell(c['baseline']['verdict_match'])} | {c['labels']['verdict_match']} |")
    return "\n".join(lines) + "\n"


def write_outputs(results: Mapping[str, Any], docs_dir: Path | str = "docs") -> tuple[Path, Path]:
    d = Path(docs_dir)
    d.mkdir(parents=True, exist_ok=True)
    js, md = d / "benchmark.json", d / "benchmark.md"
    js.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    md.write_text(render_markdown(results), encoding="utf-8")
    return js, md


# ---------------------------------------------------------------- real runners

class CountingClient:
    """Proxy over a Bedrock runtime client that counts ``converse`` calls and tokens."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.calls = 0
        self.tokens = 0

    def converse(self, **kwargs: Any) -> Any:
        self.calls += 1
        response = self._client.converse(**kwargs)
        usage = response.get("usage") if isinstance(response, Mapping) else None
        if isinstance(usage, Mapping) and isinstance(usage.get("totalTokens"), int):
            self.tokens += usage["totalTokens"]
        return response


class _NullSink:
    def publish(self, view: Any) -> None:
        pass


def make_guide_runner(config: Any, client: Any, run_session: Callable[..., Any] | None = None,
                      contract_for: Callable[[Case], tuple[Mapping[str, Any], Mapping[str, float] | None]] | None = None,
                      clock: Callable[[], float] = time.monotonic) -> GuideRunner:
    """One Tribunal_Session per run through ``run_session``; tokens and calls come from a
    counting client, the Verdict from the SessionView, never from an agent's self-report."""
    from guide.tribunal.orchestrator import SessionRequest, run_session as real_run_session
    run = run_session or real_run_session
    contract_for = contract_for or _persona_contract

    def runner(case: Case) -> RunRecord:
        counting = CountingClient(client)
        contract, base = contract_for(case)
        request = SessionRequest(contract=contract, ticker=case.ticker, weight=case.weight,
                                 start=case.start, end=case.end, as_of=case.as_of, text=case.text,
                                 base_portfolio=base or case.base_portfolio)
        t0 = clock()
        view = run(request, sink=_NullSink(), config=config, client=counting)
        latency = clock() - t0
        verdict = (view.verdict or {}).get("verdict") or "unclear"
        total, matched = count_numbers(strings_in(view.ruling), view.exhibits)
        return RunRecord(verdict, latency, counting.tokens, total, matched, counting.calls)

    return runner


def _persona_contract(case: Case) -> tuple[Mapping[str, Any], Mapping[str, float] | None]:
    if case.contract is not None:
        return case.contract, case.base_portfolio
    from guide.contract.personas import load_personas
    from guide.contract.profiler import build_contract_from_persona
    personas = load_personas().personas
    if case.persona not in personas:
        raise ValueError(f"case {case.id}: unknown persona {case.persona!r} and no inline contract")
    return build_contract_from_persona(personas[case.persona]), case.base_portfolio


def make_baseline_runner(agent: Any, clock: Callable[[], float] = time.monotonic,
                         contract_for: Callable[[Case], tuple[Mapping[str, Any], Any]] | None = None) -> BaselineRunner:
    contract_for = contract_for or _persona_contract

    def runner(case: Case) -> RunRecord:
        contract, _ = contract_for(case)
        text = case.text or f"I want {case.weight:.0%} of my portfolio in {case.ticker}."
        res = agent.run(contract, text)
        total = len(extract_numbers(res.text))
        return RunRecord(res.verdict, res.latency_seconds, res.tokens, total, 0, res.calls)

    return runner


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m guide.bench")
    p.add_argument("-n", "--runs", type=int, required=True, help="runs per case and arm (>= 5 to publish)")
    p.add_argument("--cases", nargs="+", default=["demo/cases.yaml", "bench/cases.yaml"])
    p.add_argument("--docs-dir", default="docs")
    p.add_argument("--yes", action="store_true", help="skip the confirmation above 300 planned calls")
    args = p.parse_args(argv)

    import boto3
    from botocore.config import Config as BotoConfig
    from guide.bench.baseline import BaselineAgent
    from guide.config import load_config

    cases = load_cases(args.cases)
    config = load_config()
    client = boto3.client("bedrock-runtime", region_name=config.aws_region,
                          config=BotoConfig(retries={"total_max_attempts": 1, "mode": "standard"}))
    results = run_benchmark(
        cases, args.runs, make_guide_runner(config, client),
        make_baseline_runner(BaselineAgent(config, client=client)),
        confirm=lambda q: input(q).strip().lower() in {"y", "yes"}, assume_yes=args.yes,
        meta={"model_id": config.model_id})
    if results is None:
        return 1
    if not results["published"]:
        print(f"Warning: N={args.runs}, {len(cases)} cases: below the published minimum.", file=sys.stderr)
    js, md = write_outputs(results, args.docs_dir)
    print(f"Wrote {js} and {md}")
    return 0
