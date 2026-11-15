"""The ESG exclusion list can travel in a snapshot as a typed Parquet reference table."""
from pathlib import Path

from guide.data.parquet_io import csv_to_parquet, read_parquet

ROOT = Path(__file__).resolve().parents[1]


def test_esg_exclusions_round_trip_and_xom_excluded():
    data = (ROOT / "data/esg_exclusions.csv").read_bytes()
    frame = read_parquet("esg_exclusions", csv_to_parquet("esg_exclusions", data))
    flags = frame["excluded"].astype(str).str.lower() == "true"
    assert "XOM" in set(frame.loc[flags, "ticker"])
