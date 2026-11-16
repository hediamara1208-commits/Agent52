"""The security list the web app searches must be the dataset's asset list, row for row."""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frontend_universe_matches_assets_csv():
    rows = list(csv.DictReader((ROOT / "data" / "assets_universe.csv").open()))
    ts = (ROOT / "frontend" / "src" / "universe.ts").read_text()
    listed = [json.loads(line.rstrip(",")) for line in ts.splitlines() if re.match(r"\s*\{\"ticker\"", line)]
    assert [s["ticker"] for s in listed] == [r["ticker"] for r in rows]
    for s, r in zip(listed, rows):
        assert (s["name"], s["kind"], s["exchange"], s["currency"]) == (r["name"], r["asset_class"], r["market"], r["currency"])
