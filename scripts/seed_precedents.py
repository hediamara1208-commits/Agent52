"""Seed the Precedent store with the five demo cases of Req. 33 (Req. 31.4).

Run once after deployment:  python scripts/seed_precedents.py [--table NAME] [--dry-run]

Each case in ``demo/cases.yaml`` runs through ``run_session`` with ``precedents=<store>``, so the
Precedent of every completed session is written to the shared ``precedent`` partition. The
default store is the DynamoDB Session_Store named in ``config.yaml``; credentials come from the
AWS credential chain only. ``seed`` takes an injectable store and ``run`` so tests never call AWS.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES_PATH = ROOT / "demo" / "cases.yaml"
START, END = date(2021, 11, 12), date(2026, 11, 12)


def load_demo_cases(path: Path | str = CASES_PATH) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return list(data.get("cases") or []), dict(data.get("custom_profiles") or {})


def _contract_and_base(case: Mapping[str, Any], profiles: Mapping[str, Any]) -> tuple[Mapping[str, Any], Any]:
    from guide.contract.personas import load_personas
    from guide.contract.profiler import build_contract_from_persona

    personas = load_personas().personas
    profile = case["profile"]
    custom = profiles.get(profile)
    persona = personas[custom["based_on"] if custom else profile]
    base = (custom or {}).get("base_portfolio") or persona.contract_values["base_portfolio"].value
    return build_contract_from_persona(persona), base


def seed(
    store: Any,
    *,
    cases: Sequence[Mapping[str, Any]] | None = None,
    profiles: Mapping[str, Any] | None = None,
    run: Callable[..., Any] | None = None,
    **run_kwargs: Any,
) -> list[str]:
    """Run each demo case once against ``store``; return the ids of the cases that completed."""
    from guide.tribunal.orchestrator import SessionRequest, run_session

    if cases is None:
        cases, loaded = load_demo_cases()
        profiles = profiles if profiles is not None else loaded
    run = run or run_session

    class _NullSink:
        def publish(self, view: Any) -> None:
            pass

    done: list[str] = []
    for case in cases:
        contract, base = _contract_and_base(case, profiles or {})
        req = case["request"]
        request = SessionRequest(
            contract=contract, ticker=req["ticker"], weight=float(req["weight"]), start=START, end=END,
            text=f"{float(req['weight']):.0%} in {req['ticker']}", session_id=f"seed-{case['id']}",
            profile_id=case["profile"], base_portfolio=base)
        view = run(request, sink=_NullSink(), precedents=store, **run_kwargs)
        if getattr(view, "status", None) == "completed":
            done.append(case["id"])
    return done


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Seed Precedents from the five demo cases.")
    p.add_argument("--table", help="Session_Store table (default: session_table of config.yaml)")
    p.add_argument("--dry-run", action="store_true", help="use an in-memory store; nothing is written to AWS")
    args = p.parse_args(argv)
    if args.dry_run:
        from guide.tribunal.precedents import InMemoryPrecedentStore
        store: Any = InMemoryPrecedentStore()
    else:
        from guide.config import load_config
        from guide.session.store import DynamoSessionStore
        store = DynamoSessionStore(args.table or load_config().session_table)
    done = seed(store)
    print(f"seeded {len(done)} of 5 demo cases: {', '.join(done)}")
    return 0 if len(done) == 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
