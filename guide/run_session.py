"""Local runner: ``python -m guide.run_session "Robert 30% in TSLA" robert``.

Uses an in-memory sink and prints the final SessionView JSON. It calls the same
``run_session`` as the Agent_Runtime. Credentials come from the AWS default chain only.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from typing import Any, Sequence

from guide.config import load_config
from guide.contract.personas import SHIPPED_PATH, load_personas
from guide.contract.profiler import build_contract_from_persona
from guide.data.loader import SnapshotStore
from guide.session.store import InMemorySessionStore, StoreSink
from guide.toolkit import metrics
from guide.tribunal.entrypoint import SessionError, SessionRequest, run_session
from guide.tribunal.request_parser import MissingFields, parse_request
from guide.tribunal.session_view import session_view_to_json


def build_request(text: str, persona_id: str, source: Any, years: int = 5) -> SessionRequest:
    """Build a SessionRequest from request text and a shipped persona (raises ValueError)."""
    loaded = load_personas(SHIPPED_PATH)
    persona = loaded.personas.get(persona_id)
    if persona is None:
        raise ValueError(f"unknown persona {persona_id!r}; available: {sorted(loaded.personas)}")
    universe = set(source.read_table(metrics.UNIVERSE_TABLE)["ticker"])
    parsed = parse_request(text, universe)
    if isinstance(parsed, MissingFields):
        raise ValueError(f"request is missing: {parsed.as_dict()}")
    end = date.fromisoformat(str(source.read_table("prices_daily")["date"].max())[:10])
    return SessionRequest(
        build_contract_from_persona(persona), parsed.ticker, parsed.weight_fraction,
        end - timedelta(days=365 * years), end, text=text, profile_id=persona_id,
        base_portfolio=persona.contract_values["base_portfolio"].value)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m guide.run_session")
    ap.add_argument("text", help='request, for example "Robert 30%% in TSLA"')
    ap.add_argument("persona", nargs="?", default="robert")
    args = ap.parse_args(argv)

    config = load_config()
    store = InMemorySessionStore()
    sink = StoreSink(store, "local")
    try:
        source = SnapshotStore(config).pin()
        request = build_request(args.text, args.persona, source)
        view = run_session(request, sink, config=config, source=source)
    except SessionError as error:
        print(f"session failed at stage {error.stage}: {error.message}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(session_view_to_json(view))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
