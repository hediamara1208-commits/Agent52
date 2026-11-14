---
inclusion: fileMatch
fileMatchPattern: "guide/agents/**"
---

# Agents rules (only when editing guide/agents/)

## The three agents (Req. 4, 29, 36)

| Agent | Job | Reads | Returns (JSON) | Never |
|-------|-----|-------|----------------|-------|
| Advocate | Find the goal behind the request; propose at most 3 Options, at least one reducing the request's largest exposure | Request, Investor_Contract, Risk_Panel of the request | `{goal, options: [{asset, weight, rationale, exhibits}]}` | Decide if an Option passes; phrase an Option as "buy" or "sell"; propose another asset when `advocate_scope` is `size_only` |
| Investigator | State which risks of each Option are material for this investor | All Options with their Risk_Panels and Hard_Rule results, Investor_Contract | `{per_option: [{option_id, material_risks: [{risk, exhibits, why_for_this_person, contract_fields}]}]}` | Compute a number; name a contract field or Soft_Preference that does not exist |
| Judge | Assess each Soft_Preference per Option, compare Options, write the Verdict narrative | Hard_Rule results, Options, Investigator findings, Soft_Preferences, closest Precedent | `{assessments: [{option_id, preference_id, assessment, findings, exhibits}], narrative}` | Change a Hard_Rule result; upgrade a Verdict; call another agent or the Toolkit |

- The Profiler and the Clerk are code, not agents: no Instruction_File, no model call.
- Each agent is called once per session by the orchestrator, with at most 6 Toolkit calls and a timeout of `agent_timeout_seconds`. Agents never call each other.
- Model per agent comes from `model_ids` in config.

## Instruction system

- **Instruction_File**: `guide/agents/instructions/{advocate,investigator,judge}.md` with the sections Role, Goals, Allowed tools, Output JSON format, Forbidden behaviors, Citation rule, Guidance-only rule, Tone, Included skills.
- **Skill_File**: `guide/agents/skills/<skill>.md`; every agent includes `guidance_only`.
- **Instruction_Loader**: `agents/instructions.py` composes the prompt and computes the `Instruction_Hash`.

## Bedrock integration

- `guardrailConfig` on every call; retry throttling up to 3 times with exponential backoff.
- Drop `reasoningContent` before output reaches the Trace or the Ruling.
- Record the `Instruction_Hash` in the Trace for every agent call.

## Enforcement (code, not prompts)

- Every output is validated against its JSON schema; invalid output = failed stage, then the fallback of Req. 36.
- Citation validator: each claim cites an existing Exhibit and its numbers match (up to 2 revisions, then removed).
- Guidance-only check on every output.
