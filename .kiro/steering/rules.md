---
inclusion: auto
name: Judge Rules
description: Rules checked by the Judge agent
---

# Judge rules

The Judge checks hard rules deterministically. The model only writes narrative.

## Hard rules (code-determined)

| Rule | Check | Verdict impact |
|------|-------|----------------|
| per-asset cap | Position size ≤ cap | Reject if violated |
| per-asset-class cap | Total in asset class ≤ cap | Reject if violated |
| sector cap | Total in sector ≤ cap | Reject if violated |
| crypto cap | Crypto exposure ≤ cap | Reject if violated |
| max volatility | Portfolio vol ≤ limit | Reject if violated |
| max drawdown | Portfolio drawdown ≤ limit | Reject if violated |
| ESG exclusion | No excluded assets | Reject if violated |
| speculative limit | Speculative assets ≤ limit | Reject if violated |

## Soft preferences (model-weighted)

- Business model understanding
- Company age and stability
- Other qualitative factors

## Bisection for numeric limits

When a numeric rule fails, bisect position size to find maximum acceptable size.

## Tension statement

For `low_to_moderate` risk personas exceeding per-asset cap, note the tension even if accept.

## Requirements

- Requirements 5.1-5.4, 5.9, 5.10
