---
inclusion: fileMatch
fileMatchPattern: "guide/tribunal/**"
---

# Tribunal rules (only when editing guide/tribunal/)

## Fixed flow (Req. 36), run by `tribunal/orchestrator.py` behind `run_session`

1. CODE Profiler: Investor_Contract (Hard_Rules, Soft_Preferences, Base_Portfolio)
2. CODE Risk_Panel and Hard_Rules of the request (evidence only; no verdict is published)
3. AI Advocate (1 call): goal and at most 3 Options; code always adds the largest size meeting every Hard_Rule
4. CODE Risk_Panel and Hard_Rules of every Option (failing Options kept as rejected)
5. AI Investigator (1 call): material risks per Option
6. AI Judge (1 call, at most 1 send-back): decides the Verdict and the adopted Option, assesses Soft_Preferences, writes the narrative
7. CODE check of the ruling against the Hard_Rules, Clerk template, citation validator, guidance-only check, Guardrail; then Ruling, Precedent, Trace

## Invariants (a court: code = evidence and law, agents plead, the Judge rules)

- No verdict exists or is shown before the Judge rules. `rules.decide` is computed only as evidence (max size within the rules) and as the labeled code fallback.
- The Judge may only adopt an Option that passes every Hard_Rule; `accept` only for the request itself; `reject` is always lawful (`judge.check_decision`). An unlawful ruling is sent back once with the objection.
- At most 4 agent calls per session (Advocate, Investigator, Judge, one send-back); agents never call each other.
- If the Judge fails or rules unlawfully twice, the Verdict is the code fallback, labeled `decided_by: "code"` in the Ruling (Req. 36.7).
- Sizes come from the Options (code-verified), never invented by a model.

## Delivery Tiers

Work only in Tier 1 and Tier 2 until the Sunday 12:30 freeze. See the Delivery Tiers section of `requirements.md`.

## Gate check

Saturday 23:00 local time: `scripts/run_robert.sh` runs Robert "30% in TSLA" end to end and prints a valid SessionView.
