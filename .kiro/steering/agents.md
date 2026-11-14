---
inclusion: fileMatch
fileMatchPattern: "guide/agents/**"
---

# Agents rules (only when editing guide/agents/)

## Instruction system

- **Instruction_File**: `guide/agents/instructions/<agent>.md` holds the system prompt
- **Skill_File**: `guide/agents/skills/<skill>.md` is reusable (e.g., `guidance_only.md`)
- **Instruction_Loader**: `agents/instructions.py` composes prompt and computes `Instruction_Hash`
- **Every agent**: Must include `guidance_only` skill; forbid order/transfer/brokerage actions

## Agent structure

Each Instruction_File must include: Role, Goals, Allowed tools, Output JSON format, Forbidden behaviors, Citation rule, Guidance-only rule, Tone, Included skills.

## Agent responsibilities

| Agent | Responsibility |
|-------|----------------|
| Profiler | Build validated contract from persona/template/form; never invent persona facts |
| Prosecutor | Argue against request; cite only Exhibits; no invented numbers |
| Defense | Argue for request; cite only Exhibits; include reduced-size claims if relevant |
| Judge | Check rules deterministically; write narrative only; request evidence (max 2) |
| Clerk | Write ruling with sensitivity; use template phrasing for recommendations |

## Bedrock integration

- **Tool use loop**: Retry up to 3 times with exponential backoff
- **GuardrailConfig**: On every call
- **Drop reasoningContent**: Remove before output reaches Trace or Ruling
- **Instruction_Hash**: Recorded in Trace for every agent call

## Enforcement

- **Citation validator**: Reject claims without valid Exhibit or wrong numbers (up to 2 revisions)
- **Guidance-only check**: Pattern-based static check on every output
- **Exhibit binding**: Every tool result must be an Exhibit with Snapshot_Id
