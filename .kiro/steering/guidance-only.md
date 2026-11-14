---
inclusion: auto
name: Guidance-Only Rule
description: Enforces that the system only provides guidance and never triggers actions
---

# Guidance-Only Rule

The Guide_System is a **simulation-only** investment tribunal. It may **only guide** — it **shall not perform any action directly or indirectly**.

## Prohibited

- Placing, routing, or(prefilling) orders, transfers, or brokerage/bank actions
- Triggering any execution at a brokerage or bank
- Holding brokerage or bank credentials
- Returning return predictions or personalized financial advice

## Enforcement layers

1. **Guardrail** (Bedrock): Blocks order/transfer/brokerage instructions
2. **Judge-side check** (`tribunal/guidance_only.py`): Pattern-based static check of every agent output
3. **UI/API**: No action controls, no brokerage integrations
4. **Static scan test** (`tests/test_guidance_scan.py`): Checks source and configuration

## What agents must say

- Use "You may wish to consider..." phrasing for recommendations
- Never state numbers that aren't from Exhibits
- Never certifying their own work (orchestrator validates)
