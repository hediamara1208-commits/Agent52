---
inclusion: fileMatch
fileMatchPattern: "data/**"
---

# Data rules (only when editing data/)

## S3-primary architecture

- **System of record**: Amazon S3 (versioned bucket, deny-delete policy)
- **Dataset snapshots**: Immutable, dated copies identified by `Snapshot_Id`
- **Local cache**: Only for efficiency and fallback; not a separate data source
- **No local data directory**: The `data/` folder holds starter CSVs only (unchanged)

## File layout

```
data/
  assets_universe.csv
  prices_daily.csv
  corporate_actions.csv
  fx_usdcad_daily.csv
  macro_rates.csv
  sources_metadata.csv
  context.md          # Persona definitions (French)
  build_dataset.py    # Baseline script (unchanged reference)
  README.md
```

## Snapshot format

```
s3://{bucket}/{prefix}/
  pointers/current.json       # Current_Snapshot_Pointer (mutable)
  snapshots/{snapshot_id}/
    raw/{table}.csv           # Raw CSV (write-once)
    manifest.json             # Snapshot_Manifest (write-once)
  curated/{table}/
    snapshot_id={sid}/part-0000.parquet
```

## Key constraints

- **Numbers from code only**: Every Exhibit cites a Snapshot_Id and comes from Toolkit
- **As-of filtering**: No observation after `as_of` date
- **FX carry-forward**: Use most recent rate when missing; record it
- **Macro publication lag**: Series lagged to publication date (configurable)
- **CNQ.TO note**: Special distribution on 2022-08-22; unverified
- **Survivorship bias**: Always note in Ruling

## Data sources

- **Prices & corporate actions**: Yahoo Finance (via yfinance) per datathon permission
- **FX**: Bank of Canada
- **Macro**: Bank of Canada and FRED
- **No new downloads**: Starter data only; documented additions only
