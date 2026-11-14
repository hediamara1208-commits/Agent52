---
inclusion: fileMatch
fileMatchPattern: "guide/tribunal/**"
---

# Tribunal rules (only when editing guide/tribunal/)

## Fixed flow (Req. 36), run by `tribunal/orchestrator.py` behind `run_session`

1. CODE Profiler: Investor_Contract (Hard_Rules, Soft_Preferences, Base_Portfolio)
2. CODE Risk_Panel and Hard_Rules of the request
3. AI Advocate (1 call): goal and at most 3 Options
4. CODE Risk_Panel and Hard_Rules of every Option (failing Options kept as rejected)
5. AI Investigator (1 call): material risks per Option
6. AI Judge (1 call): Soft_Preference assessments, comparison, narrative
7. CODE Clerk template, citation validator, guidance-only check, Guardrail; then Ruling, Precedent, Trace

## Invariants

- At most 3 agent calls per session; agents never call each other.
- The Verdict comes from code (`rules.decide`); the Judge can only make it more cautious.
- If an agent fails, the session still ends with a valid Ruling (Req. 36.5 to 36.7).
- Numeric conditions come from `max_weight_within_contract` (0.5-point grid), never from a model.

## Delivery Tiers

Work only in Tier 1 and Tier 2 until the Sunday 12:30 freeze. See the Delivery Tiers section of `requirements.md`.

## Gate check

Saturday 23:00 local time: `scripts/run_robert.sh` runs Robert "30% in TSLA" end to end and prints a valid SessionView.
