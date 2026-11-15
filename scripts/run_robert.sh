#!/usr/bin/env bash
# Manual end-to-end check (gate 1): runs Robert "30% in TSLA" once and validates the SessionView.
# Wire this to a MANUAL Kiro hook (Agent Hooks panel -> trigger: manual), never to every prompt.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"
OUT="$(mktemp)"
trap 'rm -f "$OUT"' EXIT
"$PY" -m guide.run_session "${REQUEST:-Robert 30% in TSLA}" "${PERSONA:-robert}" >"$OUT"
head -c 4000 "$OUT"; echo
"$PY" - "$OUT" <<'PYEOF'
import json, sys
from pathlib import Path
import jsonschema
view = json.loads(Path(sys.argv[1]).read_text())
schema = json.loads(Path("guide/tribunal/session_view.schema.json").read_text())
jsonschema.validate(view, schema)
print("run_robert: SessionView is valid")
PYEOF
