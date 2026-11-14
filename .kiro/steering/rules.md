---
inclusion: auto
name: Judge Rules
description: Hard_Rules checked by code, verdict logic, and the Soft_Preferences weighed by the Judge agent
---

# Rules and verdict logic (Req. 5, 28, 29, 32)

## Hard_Rules (code only, `tribunal/rules.py`)

Checked on the proposed portfolio (Base_Portfolio scaled by 1 - w, plus the requested asset at w).

| Rule | Check | Applies to |
|------|-------|------------|
| per-asset cap | weight <= `per_asset_cap` | single securities and crypto only (`asset_class` equity or crypto); not ETFs |
| per-asset-class caps | total per asset class <= cap | as listed in the contract |
| sector caps | total per sector <= cap | sector of `assets_universe.csv` |
| crypto cap | total crypto <= `crypto_cap` | crypto assets |
| max volatility | portfolio annualized volatility <= limit | whole portfolio (CAD) |
| max drawdown | portfolio maximum drawdown <= limit | whole portfolio (CAD) |
| speculative limit | total speculative weight <= limit | crypto plus assets with annualized volatility > `speculative_volatility_threshold` (0.45) |
| ESG exclusion | requested asset not marked excluded in `data/esg_exclusions.csv` | contracts that list `fossil_fuel_screen` |

## Verdict (code)

- All Hard_Rules pass at the requested size: `accept`.
- Some fail, and `max_weight_within_contract` (0.5-point grid) finds a positive size where all pass: `accept_with_conditions` at that size.
- An ESG exclusion fails, or no positive size passes: `reject`.
- For `low_to_moderate` personas exceeding the per-asset cap, state the tension.

## Soft_Preferences (Judge agent)

Verbatim excerpts from `data/context.md` section 3, stored in the persona file. The Judge assesses each as `satisfied`, `tension`, or `not_satisfied` per Option. `not_satisfied` on the retained Option turns `accept` into `accept_with_conditions`; nothing turns `reject` into `accept`.
