---
inclusion: fileMatch
fileMatchPattern: "guide/toolkit/**"
---
# Toolkit rules (only when editing guide/toolkit/)

## Core functions

| Function | Returns | Key requirements |
|----------|---------|------------------|
| `annualized_return` | float | Uses adj_close; 20-obs minimum |
| `annualized_volatility` | float | Uses adj_close returns |
| `max_drawdown` | (float, peak_date, trough_date) | Peak/trough dates required |
| `correlation` | float | Both assets must have 20+ obs |
| `drawdown_in_period` | float | Named period (e.g. 2022) |
| `portfolio_metrics` | (return, vol, drawdown) | Weighted position |

## Data handling

- **Currency**: All amounts in CAD; USD→CAD via fx_usdcad_daily
- **FX carry-forward**: Use most recent earlier rate; record in notes
- **Calendar alignment**: Date intersection of all assets; record count
- **As-of filtering**: Drop every observation after `as_of`
- **Macro lag**: Apply configured lag per series
- **CNQ.TO note**: Add when period includes 2022-08-22

## Exhibit requirements

Every Exhibit records:
- metric name, value, period (start/end), assets, currency
- source files (table@snapshot_id), processing notes
- Snapshot_Id, snapshot_retrieved_at
- Sequential number from ExhibitRegistry

## Test oracle

Starter data (CAD, daily rebalanced, dates where every held asset has a price, 2021-11-12 to 2026-11-12), Robert base portfolio XBB.TO 40 / ZST.TO 15 / XIU.TO 15 / SPY 15 / JNJ 8 / RY.TO 7: base vol 6.5 %, max drawdown -10.4 %; with 30 % TSLA vol 20.1 %, max drawdown -30.1 %, TSLA share of variance 86.7 %.
