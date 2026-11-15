"""The single entry point of the runtime (Req. 22.6, 22.14).

The Agent_Runtime, the tests, and ``python -m guide.run_session`` all call
``run_session``. It loads the Instruction_Files, pins the snapshot, runs the
orchestrator, and publishes SessionViews to the sink; the orchestrator does that
work, so this module only fixes the public signature.
"""
from __future__ import annotations

from typing import Any

from guide.session.store import SessionSink
from guide.tribunal import orchestrator
from guide.tribunal.orchestrator import SessionError, SessionRequest
from guide.tribunal.session_view import SessionView

__all__ = ["run_session", "SessionRequest", "SessionError"]


def run_session(request: SessionRequest, sink: SessionSink, **kwargs: Any) -> SessionView:
    """Run one Tribunal_Session; keyword arguments are those of the orchestrator's run_session."""
    return orchestrator.run_session(request, sink=sink, **kwargs)
