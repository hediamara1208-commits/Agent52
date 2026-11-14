---
inclusion: fileMatch
fileMatchPattern: "guide/contract/**"
---

# Contract rules (only when editing guide/contract/)

## Investor Contract structure

| Field | Type | Constraints |
|-------|------|-------------|
| `risk_level` | enum | `low`, `low_to_moderate`, `moderate`, `high` |
| `horizon_years` | integer | Minimum 1 |
| `max_volatility` | float | 0.0 to 1.0 |
| `max_drawdown` | float | 0.0 to 1.0 |
| `per_asset_cap` | float | 0.0 to 1.0 |
| `per_asset_class_caps` | map | Asset class → cap |
| `sector_caps` | map | Sector → cap |
| `crypto_cap` | float | 0.0 to 1.0 |
| `esg_exclusions` | list | Screen names; `fossil_fuel_screen` maps to `data/esg_exclusions.csv` |
| `speculative_limit` | float or null | 0.0 to 1.0 |
| `soft_preferences` | list | `{id, text, provenance, excerpt}`; verbatim from context.md (Req. 29) |
| `base_portfolio` | map | ticker -> weight, sums to 1, basis `assumption` (Req. 28) |

## Provenance

Each field records its origin:
- `persona_quoted`: Quoted verbatim from context.md
- `persona_assumption`: Documented team assumption
- `user`: Edited by user
- `form`: Form value not from template
- `default`: Hard-coded default

## Persona templates

| Persona | Risk | Horizon | Key limits |
|---------|------|---------|------------|
| `amira` | high | 15+ years | Crypto 15 %, IT 40 %, per-asset 15 %, no speculative limit |
| `mateo` | moderate | 8-12 years | `fossil_fuel_screen`, speculative 10 %, per-asset 10 % |
| `robert` | low_to_moderate | 3-5 years | Crypto 2 %, speculative 5 %, max drawdown 15 % |

Full values and Base_Portfolios: design document, "Proposed Contract_Values" and "Demo cases".

## Validation

- **Schema validation**: `contract/schema.json` enforces types and ranges
- **Persona-specific checks**: `contract/profiler.py` enforces template constraints
- **Tolerance**: Edited contracts pass only generic schema

## File layout

```
guide/contract/
  schema.json           # Contract JSON schema
  personas.yaml         # Persona templates
  personas.schema.json  # Personas YAML schema
  validate.py           # Contract validator
  profiler.py           # Contract builder from persona/form
```
