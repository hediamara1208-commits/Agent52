#!/usr/bin/env bash
# Build the Session_API dependency layer (jsonschema, pyyaml) into build/api_deps/python.
# pandas, numpy, pyarrow and boto3 come from the AWS SDK for pandas managed layer (see ApiStack).
# Needs network access to PyPI; downloads Linux x86_64 wheels so it works from any OS.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/build/api_deps"
rm -rf "$OUT"
mkdir -p "$OUT/python"
python3 -m pip install --quiet --no-cache-dir --target "$OUT/python" \
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.11 --only-binary=:all: \
  "jsonschema>=4.21" "pyyaml>=6.0"
find "$OUT" -name '__pycache__' -type d -prune -exec rm -rf {} +
echo "build_api_deps: layer contents in $OUT"
