#!/usr/bin/env bash
# Manual end-to-end check (gate 1): runs Robert "30% in TSLA" once.
# Wire this to a MANUAL Kiro hook (Agent Hooks panel -> trigger: manual), never to every prompt.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m guide.run_session "${REQUEST:-Robert 30% in TSLA}" "${PERSONA:-robert}" 2>&1 | head -200
