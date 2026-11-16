"""The committed dataset must pass the deterministic data-quality audit."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dataset_passes_blocking_checks():
    spec = importlib.util.spec_from_file_location("audit", ROOT / "scripts" / "data_quality_audit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    table, blocking, meta = mod.audit()
    assert blocking == []
    assert meta["n"] == len(table) == 31
    assert all(r["dup"] == 0 and r["bad"] == 0 and r["ccy"] == "ok" for r in table)
