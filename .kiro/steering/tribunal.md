---
inclusion: fileMatch
fileMatchPattern: "guide/tribunal/**"
---

# Tribunal rules (only when editing guide/tribunal/)

## Architecture

- **Orchestrator is the hub**: `tribunal/orchestrator.py` coordinates all agents and runs `run_session` as the single entry point.
- **Agents are thin**: Prosecutor, Defense, Judge, Clerk each have one role prompt over shared Toolkit and Exhibit_Registry.
- **Rules are deterministic**: Judge checks hard rules against contract; model only writes narrative.
- **Citations are enforced**: `tribunal/citations.py` validates claims against Exhibits before Judge sees them.

## Flow

1. `run_session(request, persona_id, custom_profile)` loads instructions, pins snapshot, runs pipeline
2. Profiler builds validated contract from persona/template/form
3. Prosecutor and Defense argue with Exhibit citations only
4. Citation validator enforces Exhibit references and number matching
5. Judge checks rules deterministically, writes narrative only
6. Clerk writes ruling with sensitivity analysis

## Delivery Tiers

Work only in Tier 1 and Tier 2 until the Sunday 12:30 freeze. Tier 3 tasks are marked with `*` in `tasks.md`.

- **Tier 1** (demo-critical): Requirements 1-7, 9.1-9.6, 9.8, 10.1-10.9, 11, 13, 16, 21, 28-35
- **Tier 2** (AWS showcase): Requirements 8.1-8.9, 17.1-17.3, 17.14, 18.1-18.5, 18.7-18.9, 19.2, 19.5-19.8, 20.1, 20.4-20.7, 20.11, 22, 23.1-23.6, 25.3, 25.6, 26.1-26.5, 26.7
- **Tier 3** (deferred): Everything else; do not start before freeze

## Gate check

At Saturday 23:00 local time: `python -m guide.run_session` must run Robert "30% in TSLA" end to end and produce valid SessionView.
