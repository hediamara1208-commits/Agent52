"""Typed, deterministic CSV-to-Parquet conversion for Dataset tables.

The Dataset has a fixed schema. Keeping it in one module lets the Snapshot
Writer and Glue catalog use the same column definitions (Req. 18.1 to 18.3).
"""
from __future__ import annotations

import io
from collections.abc import Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq


TABLE_SCHEMAS: dict[str, pa.Schema] = {
    "assets_universe": pa.schema(
        [
            pa.field("asset_id", pa.string()),
            pa.field("ticker", pa.string()),
            pa.field("name", pa.string()),
            pa.field("asset_class", pa.string()),
            pa.field("market", pa.string()),
            pa.field("currency", pa.string()),
            pa.field("sector", pa.string()),
        ]
    ),
    "prices_daily": pa.schema(
        [
            pa.field("date", pa.date32()),
            pa.field("ticker", pa.string()),
            pa.field("open", pa.float64()),
            pa.field("high", pa.float64()),
            pa.field("low", pa.float64()),
            pa.field("close", pa.float64()),
            pa.field("adj_close", pa.float64()),
            pa.field("volume", pa.int64()),
            pa.field("currency", pa.string()),
        ]
    ),
    "corporate_actions": pa.schema(
        [
            pa.field("ex_date", pa.date32()),
            pa.field("ticker", pa.string()),
            pa.field("action", pa.string()),
            pa.field("value", pa.float64()),
            pa.field("unit", pa.string()),
        ]
    ),
    "fx_usdcad_daily": pa.schema(
        [
            pa.field("date", pa.date32()),
            pa.field("usdcad", pa.float64()),
            pa.field("cadusd", pa.float64()),
        ]
    ),
    "macro_rates": pa.schema(
        [
            pa.field("date", pa.date32()),
            pa.field("series_id", pa.string()),
            pa.field("value", pa.float64()),
            pa.field("unit", pa.string()),
            pa.field("frequency", pa.string()),
            pa.field("label", pa.string()),
            pa.field("source", pa.string()),
        ]
    ),
}


# Reference tables: hand-authored, documented files carried in a snapshot next to the market
# data (docs/data_sources.md). They are not part of the seed's required market tables.
REFERENCE_SCHEMAS: dict[str, pa.Schema] = {
    "esg_exclusions": pa.schema(
        [
            pa.field("ticker", pa.string()),
            pa.field("excluded", pa.string()),
            pa.field("reason", pa.string()),
            pa.field("source_url", pa.string()),
            pa.field("retrieved", pa.string()),
        ]
    ),
}


class TableSchemaError(ValueError):
    """Raised when Dataset table columns differ from their declared schema."""


def _schema_for(table: str) -> pa.Schema:
    try:
        return TABLE_SCHEMAS[table] if table in TABLE_SCHEMAS else REFERENCE_SCHEMAS[table]
    except KeyError as error:
        known = ", ".join(sorted({**TABLE_SCHEMAS, **REFERENCE_SCHEMAS}))
        raise ValueError(f"Unknown Dataset table {table!r}; expected one of: {known}") from error


def _as_bytes(data: bytes | bytearray | memoryview) -> bytes:
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("Dataset data must be bytes")
    return bytes(data)


def _validate_columns(table: str, actual: Iterable[str], schema: pa.Schema) -> None:
    """Reject column additions and omissions before a snapshot is written."""
    expected = list(schema.names)
    actual_names = list(actual)
    missing = [name for name in expected if name not in actual_names]
    extra = [name for name in actual_names if name not in expected]
    duplicate = sorted({name for name in actual_names if actual_names.count(name) > 1})
    if missing or extra or duplicate:
        details: list[str] = []
        if missing:
            details.append(f"missing columns: {', '.join(missing)}")
        if extra:
            details.append(f"extra columns: {', '.join(extra)}")
        if duplicate:
            details.append(f"duplicate columns: {', '.join(duplicate)}")
        raise TableSchemaError(f"{table}: " + "; ".join(details))


def _read_csv_table(table: str, data: bytes | bytearray | memoryview) -> pa.Table:
    schema = _schema_for(table)
    parsed = pacsv.read_csv(
        pa.BufferReader(_as_bytes(data)),
        read_options=pacsv.ReadOptions(autogenerate_column_names=False, encoding="utf8"),
        convert_options=pacsv.ConvertOptions(
            column_types={field.name: field.type for field in schema},
            strings_can_be_null=False,
        ),
    )
    _validate_columns(table, parsed.column_names, schema)
    # Enforce the declared column order without altering the CSV's row order.
    return parsed.select(schema.names).cast(schema, safe=True)


def read_csv_typed(table: str, data: bytes) -> pd.DataFrame:
    """Read an ISO-date CSV into a DataFrame using the declared Arrow schema."""
    return _read_csv_table(table, data).to_pandas()


def csv_to_parquet(table: str, data: bytes) -> bytes:
    """Convert a Dataset CSV to deterministic Snappy-compressed Parquet bytes.

    The writer receives a single, explicitly typed Arrow table and does not add
    timestamp metadata. It retains incoming row order and fixes the row-group
    layout so equal input bytes produce equal Parquet bytes for a given PyArrow
    version.
    """
    typed = _read_csv_table(table, data)
    output = pa.BufferOutputStream()
    pq.write_table(
        typed,
        output,
        compression="snappy",
        version="2.6",
        data_page_version="1.0",
        use_dictionary=True,
        write_statistics=True,
        row_group_size=max(typed.num_rows, 1),
        store_schema=True,
    )
    return output.getvalue().to_pybytes()


def read_parquet(table: str, data: bytes) -> pd.DataFrame:
    """Read a typed Dataset Parquet file into a DataFrame.

    The Parquet payload must have exactly the columns declared for ``table``.
    Its columns are safely cast to that schema so callers receive the same
    declared types as :func:`read_csv_typed`.
    """
    schema = _schema_for(table)
    parsed = pq.read_table(pa.BufferReader(_as_bytes(data)))
    _validate_columns(table, parsed.column_names, schema)
    return parsed.select(schema.names).cast(schema, safe=True).to_pandas()
