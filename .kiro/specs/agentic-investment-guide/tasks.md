# Implementation Plan: Agentic Investment Guide

## Overview

Implementation language: Python 3.11 for the backend, agents, data layer, API, and CDK app (boto3, pandas, pyarrow, jsonschema, pytest, hypothesis, moto, aws-cdk-lib), and TypeScript with React for the UI (Vite, Vitest, React Testing Library, fast-check). The plan builds the deterministic core first (config, S3-primary data layer with Local_Cache, tolerant Persona_File and contract, Exhibits, Toolkit). It then adds governance logic (citations, rules, guidance-only check, sensitivity), the Instruction_Loader with the Instruction_Files and Skill_Files, the agents, the orchestrator, and the web UI (Friendly_Mode and Advanced_Mode over one shared SessionView). The data platform follows: CDK stacks for S3, Glue, and Athena, the Snapshot_Writer, and the Seed_Import_Job. Tasks 17 to 19 add the AWS delivery layer: the Session_API, Session_Store, and Agent_Runtime packaging, the CDK stacks with one-command deployment, and the optional Snapshot_Pipeline. The guidance-only constraint is enforced in four layers: Guardrail denied topics, the Judge-side check, a static scan test, and a UI and API without action controls. Alerts (Requirement 15) and the Flight Simulator (Requirement 12) are optional stretch work: their sub-tasks are marked with `*` and the MVP works without them. The Companion_Extension (Requirement 14) was removed from the scope.

Hosting decision: the UI is a React single-page app on AWS Amplify Hosting with Cognito sign-in, calling a Session_API (API Gateway and Lambda) in front of the unchanged Python core on Amazon Bedrock AgentCore Runtime. Amplify Hosting cannot run a Streamlit server. The design records the options, the decision, and the trade-off, and the AWS service map marks each service as MVP or stretch.

Completed tasks 1.1, 3.1, 3.3, 6.1, and 7.1 keep their text and status. Where the S3-primary data architecture or the tolerant Persona_File changes their behavior, a follow-up task reworks them (1.3 and 1.8 for 1.1, 3.7 for 3.1, 3.8 for 3.3, 6.5 and 6.6 for 6.1, 2.5 for in-progress 2.1). Task 7.1 mentions a Companion API and Requirement 14.9: that reference is historical, because Requirement 14 was removed, and no task depends on it.

## Hackathon execution order (2026-11-14)

The Delivery Tiers in the requirements document decide what is built. Tasks marked `*` are optional and Kiro may skip them. Work in four parallel tracks, one owner per track and per folder. Pull before each task, push after each task.

| Track | Owner | Order |
| --- | --- | --- |
| A: data and toolkit | | 1.11, 2.1, 2.5, 1.3, 1.4, 1.6, 1.8 (lean), 2.2, 21.1, 22.1, 23.1, 3.7, 3.8, 4.1, 21.2, 21.3, 23.2, 4.2, 4.3, 4.7 |
| B: agents and tribunal | | 6.2, 6.6, 6.7, 7.3, 7.4, 7.5, 7.6, 7.8, 7.9, 7.10, 29.1, 29.2, 29.3, 29.4, 8.3, 29.5, 29.6, 24.1, 9.1, 17.1, 9.4, then gate 1, then 17.3, 26.1, 25.1, 25.2, 27.1, 29.7 |
| C: front end | | 11.1 first (the SessionView schema is the contract between tracks), then 11.2, 11.3, 11.4, 11.5 against fixture SessionViews, 24.2, 26.2, 28.2 |
| D: AWS and deliverables | | 12.1, 12.7, 12.8, 12.12, 12.13, 12.15 (lean), 12.17, 18.1, 18.2, 28.1, 18.3, 17.2, 17.4, 17.5, 17.6, 18.4, 18.5, 18.6 (lean), 18.7, then gate 2, then 12.2, 27.2, 28.3 |

Gates (local time): Saturday 23:00, `python -m guide.run_session` runs Robert end to end; Sunday 09:00, hosting gate (option b if option a is not working end to end); Sunday 12:30, feature freeze with the five demo cases on the deployed URL; Sunday 20:00, demo video recorded; Sunday 23:59, code, `demo/sessions/`, and Replay_Mode pushed.

Deferred to Tier 3 (do not start before the freeze): 1.10, 12.25, 18.12, and every task whose requirements are all in Tier 3.

## Tasks

- [ ] 1. Set up project structure, configuration, and data access
  - [x] 1.1 Create the `guide/` package layout, `tests/`, `pyproject.toml`/`requirements.txt`, `config.py`, and `data/loader.py`
    - Config loads from environment and `config.yaml`: region, model id, guardrail id and version, S3 bucket, data location, data dir, macro publication lags. No credential fields.
    - Implement `DataSource` protocol with `LocalSource` (/workshop/Agent52/data) and `S3Source`
    - Add a log filter that redacts AWS key patterns
    - _Requirements: 3.5, 8.5, 8.6, 8.7_

  - [ ]* 1.2 Write unit tests for config and loader
    - Run after the 1.3 and 1.8 rework; add `moto` as a dev dependency
    - Config: no credential fields; `data_location` is rejected with a message pointing to `cache_dir`; all data keys of 8.7 load from YAML and `GUIDE_*` env; log redaction works
    - Loader with `moto`: pointer `IfNoneMatch` gives 304 and keeps the cache, a new ETag replaces it; reads come from Parquet by `VersionId`; access denied raises `DataConfigError` without fallback; unreachable with empty cache raises `DatasetUnavailable`
    - _Requirements: 8.5, 8.6, 8.7, 17.5, 17.9, 17.13, 18.9_

  - [x] 1.3 Rework `config.py` and `config.yaml` for the S3-primary data architecture (follow-up to 1.1)
    - Remove `data_location` and `data_dir`; `load_config` raises a clear error if `data_location` is present
    - Add `s3_bucket` (required), `s3_prefix`, `cache_dir`, `s3_connect_timeout_seconds`, `s3_read_timeout_seconds`, `s3_max_attempts`, `glue_database`, `athena_workgroup`, `athena_results_uri`, `athena_bytes_scanned_cutoff`, `seed_dir`, `persona_file`, `instruction_dir`, `sensitivity_ranges`, `speculative_volatility_threshold`, `trace_summary_max_chars`, `session_table`, `agent_runtime_arn`, `agentcore_memory_id`, `cors_origin`
    - Keep the redaction filter and the no-credentials rule unchanged; add `cache_dir` to `.gitignore`
    - _Requirements: 6.6, 8.5, 8.6, 8.7, 9.6, 17.8, 19.1, 22.11, 23.2_

  - [x] 1.4 Create `data/snapshot.py` with Snapshot_Id, manifest, and pointer models
    - `SNAPSHOT_ID_RE`, `FileEntry`, `SnapshotManifest`, `SnapshotPointer`, `SnapshotInfo` (served_from `primary`, `cache`, or `cache_fallback`)
    - `data/manifest.schema.json` and `data/pointer.schema.json`; `manifest_to_json`/`manifest_from_json`, `pointer_to_json`/`pointer_from_json` with `ManifestError(fields)` on schema failure
    - _Requirements: 17.14, 17.15, 17.16, 20.2_

  - [ ]* 1.5 Write property test for manifest and pointer serialization round trip
    - **Property 39: Manifest and pointer serialization round trip**
    - **Validates: Requirements 17.14, 17.15, 17.16**

  - [x] 1.6 Create `data/parquet_io.py`
    - `TABLE_SCHEMAS` for assets_universe, prices_daily, corporate_actions, fx_usdcad_daily, macro_rates with explicit types (date32, string, double, int64)
    - `read_csv_typed`, `csv_to_parquet` (deterministic output, row order kept, fails on missing or extra columns), `read_parquet`; add `pyarrow` to `requirements.txt`
    - _Requirements: 18.1, 18.2, 18.3_

  - [ ]* 1.7 Write property test for the Parquet round trip
    - **Property 40: Parquet round trip**
    - **Validates: Requirements 18.1, 18.2, 18.3**

  - [ ] 1.8 Rework `data/loader.py` into a lean S3-primary `SnapshotStore` and create `data/cache.py` (follow-up to 1.1, Tier 2 lean)
    - `SnapshotStore.pin()` reads the Current_Snapshot_Pointer and the Snapshot_Manifest once per session (plain GET, no conditional request) and returns a `PinnedSnapshot`
    - `PinnedSnapshot.read_table` reads the pinned Parquet files by key, cache-first in `cache_dir`, and verifies the SHA-256 checksum of the manifest; a mismatch re-downloads once, then raises `DataIntegrityError(file)`
    - Access denied raises `DataConfigError(resource)`; any other S3 error raises `DatasetUnavailable(location)`; no Cache_Fallback in Tier 2
    - Keep `LocalSource` for tests and seeding only
    - The full version (ETag-conditional pointer, VersionId reads, Cache_Fallback classification) is task 1.10
    - _Requirements: 8.5, 8.6, 17.1, 17.2, 17.3, 17.7, 17.9, 18.9_

  - [ ]* 1.9 Write property test for cache validity
    - **Property 42: Cache validity**
    - **Validates: Requirements 17.4, 17.6, 17.7**

  - [ ]* 1.10 Full SnapshotStore (Tier 3): ETag-conditional pointer, VersionId reads, verified Cache_Fallback with `served_from`, `classify_s3_error`
    - _Requirements: 17.4, 17.5, 17.6, 17.8, 17.10 to 17.13_

  - [ ] 1.11 Extend `Config` in `guide/config.py` with `model_ids` (advocate, investigator, judge; empty falls back to `model_id`), `advocate_scope` (`size_only` or `universe`, validated), and `agent_timeout_seconds` (positive); the keys already exist in `config.yaml`
    - _Requirements: 4.9, 8.7, 36.3_

- [ ] 2. Implement Investor_Contract, schema validation, and Profiler
  - [x] 2.1 Create `contract/schema.json` and `contract/validate.py`
    - `validate_contract` returns a list of failing fields (empty when valid)
    - _Requirements: 1.3, 1.4_

  - [ ] 2.2 Create `personas.yaml` and `contract/profiler.py`
    - Create `guide/contract/personas.yaml` shipping three Persona_Templates `amira`, `mateo`, `robert` (display names Amira, Mateo, Robert), transcribed from `data/context.md` section 3, as default starting points that the user can edit, extend, duplicate, or replace
    - Each shipped entry records the Persona_Facts age, occupation, risk level, horizon, family situation, experience, objective, preferences and constraints, and what the persona tests, each with the verbatim French excerpt
    - Each shipped entry records the Contract_Values horizon_years, max_volatility, max_drawdown, per_asset_cap, per_asset_class_caps, sector_caps, crypto_cap, esg_exclusions, speculative_limit, each with `basis` (`quoted` or `assumption`), `rationale`, and `excerpt` when quoted; start from the proposed values table in the design
    - Quoted values must match context.md: Amira high, 15+ years, 26; Mateo moderate, 8 to 12 years, 41; Robert low_to_moderate, 3 to 5 years, 59
    - Create `contract/personas.schema.json` (light schema: required fields, value types, ranges, basis enum) and `contract/personas.py` with a tolerant `load_personas` that returns every valid entry plus the `(persona id, field)` errors of excluded entries, accepts any number of entries and any ids, and raises `PersonaFileError` only for an unreadable or unparsable file
    - `build_contract_from_persona(persona)` copies Contract_Values only, sets `persona_quoted`, `persona_assumption`, or `user` provenance from the basis, and makes no Bedrock call; `build_contract_from_form(values, base=None)` gives `user` provenance to fields that differ from the base template and keeps the template provenance for unchanged fields, and uses form values and defaults only (`form`, `default` provenance) when no base is given; a horizon range sets `horizon_years` to the lower bound and keeps the range
    - `validate_contract_for_persona` checks the limits of 1.6 to 1.8 on unedited shipped templates only: Amira crypto and Information Technology caps below 1.0; Mateo at least one ESG exclusion and speculative limit below 1.0; Robert horizon 3 to 5 years and the lowest crypto cap; an edited contract is validated only against the generic schema
    - Model-based mapping of free text to form values is optional input only; validation is always schema-based
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6, 1.7, 1.8, 1.10, 1.11, 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8, 16.9, 16.10, 16.11, 16.12, 16.13, 16.14, 16.15_
  - [ ]* 2.3 Write property test for contract validity and provenance
    - **Property 1: Contract validity and provenance**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.5, 1.9, 1.10, 16.12, 16.13, 16.14**

  - [ ]* 2.4 Write property test for invalid contract rejection
    - **Property 2: Invalid contracts are rejected with failing fields**
    - **Validates: Requirements 1.4**

  - [ ] 2.5 Update `contract/schema.json` for the new risk level and provenance values (follow-up to 2.1)
    - `risk_level` enum adds `low_to_moderate`; `provenance` enum becomes `persona_quoted`, `persona_assumption`, `user`, `form`, `default`
    - _Requirements: 1.5, 1.9, 16.12_

  - [ ]* 2.6 Write `tests/test_personas.py` and `tests/fixtures/context_persona_facts.yaml`
    - Fixture transcribed by hand from context.md section 3 (age, occupation, risk level, horizon, family situation, experience, objective for each Persona)
    - Assert the shipped file contains `amira`, `mateo`, `robert`; every excerpt is a substring of `data/context.md`; every quoted Persona_Fact equals the fixture; every shipped Contract_Value has a basis and a non-empty rationale, and every quoted one has an excerpt
    - Assert Persona-specific limits of 1.6 to 1.8 on the unedited templates
    - Assert that a file with an added, duplicated, edited, or removed entry loads without error and that an invalid entry is reported per field
    - _Requirements: 1.6, 1.7, 1.8, 10.9, 16.1, 16.2, 16.5, 16.8, 16.9_
  - [ ]* 2.7 Write property test for tolerant Persona_File loading
    - **Property 36: Persona_File tolerant loading**
    - **Validates: Requirements 16.2, 16.3, 16.5, 16.6**
  - [ ]* 2.8 Write property test that persona contracts come only from the Persona_File and the form
    - **Property 37: Persona contracts come only from the Persona_File and the form**
    - **Validates: Requirements 1.5, 16.11, 16.12, 16.13, 16.15**
- [ ] 3. Implement Exhibits, alignment, and data-quality handling
  - [x] 3.1 Create `toolkit/exhibits.py` with frozen `Exhibit` and `ExhibitRegistry`
    - Sequential numbering, all required fields, read-only value and inputs
    - _Requirements: 2.2, 2.3_

  - [ ]* 3.2 Write property test for Exhibit completeness, sequencing, and immutability
    - Run after 3.7 so the snapshot fields are covered
    - **Property 3: Exhibit completeness, sequencing, and immutability**
    - **Validates: Requirements 2.2, 2.3**

  - [x] 3.3 Create `toolkit/align.py` and `data/quality.py`
    - As-of filtering for prices, FX, and macro; USD to CAD conversion with FX carry-forward notes
    - Date-intersection calendar alignment with method and observation count notes
    - Macro lag availability; CNQ.TO 2022-08-22 note; survivorship-bias text; unsupported-topic detection (ESG scores, news, fundamentals)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

  - [ ]* 3.4 Write property test for currency conversion and FX carry-forward
    - Include FX series that start after the first price date (no earlier rate)
    - **Property 7: Currency conversion and FX carry-forward**
    - **Validates: Requirements 3.1, 3.2, 3.12**

  - [ ]* 3.5 Write property test for calendar alignment
    - **Property 8: Calendar alignment is the date intersection**
    - **Validates: Requirements 3.3**

  - [ ]* 3.6 Write property test for macro publication lag
    - **Property 9: Macro publication lag**
    - **Validates: Requirements 3.4**

  - [ ] 3.7 Rework `toolkit/exhibits.py` to bind the pinned snapshot (follow-up to 3.1)
    - Add `snapshot_id` and `snapshot_retrieved_at` fields to `Exhibit` and `to_dict`
    - `ExhibitRegistry(snapshot: SnapshotInfo | None)` fills both fields on `add` and appends `quality.fallback_note(snapshot)` to every Exhibit when `served_from == "cache_fallback"`
    - `source_files` entries name table and snapshot (`prices_daily@{snapshot_id}`)
    - _Requirements: 2.2, 9.5, 17.11_

  - [ ] 3.8 Extend `toolkit/align.py` and `data/quality.py` for snapshots (follow-up to 3.3)
    - `filter_as_of` clamps to `min(as_of, coverage_end)` and returns the coverage-end note when `as_of` is later
    - `convert_to_cad` drops dates with no FX rate on or before them and lists them in the notes
    - `quality.py`: `fallback_note(snapshot)`, `snapshot_note(snapshot)`, `coverage_end_note(snapshot)` texts
    - _Requirements: 3.12, 17.11, 20.10_

- [ ] 4. Implement Toolkit metrics and Converse tool specs
  - [ ] 4.1 Create `toolkit/metrics.py`
    - `annualized_return`, `annualized_volatility`, `max_drawdown` (peak and trough dates), `correlation`, `drawdown_in_period`, `portfolio_metrics`
    - Pipeline: ticker check against the pinned snapshot's universe, as-of and coverage-end filter, FX, alignment, 20-observation check, adj_close returns (ratios only), CNQ note, register Exhibit
    - Read tables only through a `DataSource` (`PinnedSnapshot` or a test `LocalSource` adapter); no import of yfinance or the Athena module
    - Errors return `ToolError` and create no Exhibit
    - _Requirements: 2.1, 2.2, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.3, 3.6, 3.7, 3.12, 19.8, 20.5, 20.10_

  - [ ] 4.2 Create `toolkit/tools.py` with Bedrock Converse `toolSpec` definitions and a tool runner
    - Generate JSON input schemas; dispatch `toolUse`, return Exhibit number and value in `toolResult`
    - _Requirements: 2.8_

  - [ ]* 4.3 Write unit tests for each Toolkit function and the as-of rule
    - Fixed small price tables with hand-computed expected values; test fails if any observation after As_Of_Date is used; CNQ.TO note on 2022-08-22 period
    - _Requirements: 10.1, 10.2, 10.7_

  - [ ]* 4.4 Write property test for Toolkit determinism
    - **Property 4: Toolkit determinism**
    - **Validates: Requirements 2.4**

  - [ ]* 4.5 Write property test for Toolkit errors creating no Exhibit
    - **Property 5: Toolkit errors create no Exhibit**
    - **Validates: Requirements 2.6, 2.7**

  - [ ]* 4.6 Write property test for adj_close usage
    - **Property 6: Returns are computed from adj_close**
    - **Validates: Requirements 2.5**

  - [ ]* 4.7 Write property test for as-of exclusion
    - **Property 10: As-of exclusion (no look-ahead)**
    - **Validates: Requirements 3.6, 12.2**

  - [ ]* 4.8 Write property test for the CNQ.TO anomaly note
    - **Property 11: CNQ.TO anomaly note**
    - **Validates: Requirements 3.7**

  - [ ]* 4.9 Write property test for As_Of_Date after the coverage end
    - **Property 49: As-of beyond coverage end**
    - **Validates: Requirements 20.10**

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement Trace recorder and Bedrock agent base
  - [x] 6.1 Create `trace/recorder.py`
    - Events for agent calls, tool calls with Exhibit number, judge checks, guardrail blocks, removed claims; timestamp and sequence number; summaries only
    - JSON export; OpenTelemetry span emission for AgentCore Observability; `trace_chain(statement)` link chain
    - _Requirements: 8.3, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ] 6.2 Create `agents/base.py` Bedrock Converse wrapper
    - Tool-use loop, `guardrailConfig` on every call, guardrail-intervention handling mapped to the Challenge_Rule and recorded in Trace
    - Guardrail blocks of order, transfer, or brokerage or bank action instructions produce a message that the Guide_System only provides guidance
    - Throttling retry up to 3 times with exponential backoff and jitter, then `StageFailure(stage)`
    - Drop `reasoningContent` blocks from every response before the output reaches the Trace or the Ruling
    - _Requirements: 5.7, 5.8, 8.1, 8.2, 8.8, 9.6, 13.5, 13.6_

  - [ ]* 6.3 Write property test for throttling retry bound
    - **Property 19: Throttling retry bound**
    - **Validates: Requirements 8.8**

  - [ ]* 6.4 Write property test for Trace export round trip
    - Include `data_event` entries in generated Traces
    - **Property 21: Trace export round trip**
    - **Validates: Requirements 9.4**

  - [ ] 6.5 Extend `trace/recorder.py` with data events and a summary length cap (follow-up to 6.1)
    - `data_event(kind, snapshot_id, retrieved_at, cause)` for `snapshot_pinned`, `cache_fallback`, `ingestion_aborted`, included in JSON export and spans
    - Replace the fixed summary limit with `trace_summary_max_chars` from config
    - _Requirements: 9.6, 9.7, 17.10_

  - [ ] 6.6 Create `agents/instructions.py` (Instruction_Loader) and pass the System_Prompt and Instruction_Hash through `agents/base.py` and `trace/recorder.py` (follow-up to 6.1 and 6.2)
    - `load_system_prompt(agent, root)` composes the Instruction_File text followed by the listed Skill_File texts in the listed order, under a `# Skill: <name>` heading each; computes the SHA-256 `instruction_hash` of the UTF-8 text with LF line endings; `load_all(agents, root)`
    - `InstructionError(agent, missing_file)` when an Instruction_File is missing or lists a Skill_File that does not exist, and when a composed prompt lacks the `guidance_only` text
    - `agents/base.py` passes the composed text as the Converse `system` block; `TraceRecorder.agent_call` takes `instruction_hash` and stores it in the event and the OpenTelemetry span
    - _Requirements: 9.8, 21.4, 21.5, 21.6, 21.7, 21.8_

  - [ ] 6.7 Create the Instruction_Files and Skill_Files
    - `guide/agents/instructions/{advocate,investigator,judge}.md` (the Profiler and the Clerk are code and have no Instruction_File) with the sections Role, Goals, Allowed tools, Output JSON format, Forbidden behaviors, Citation rule, Guidance-only rule, Tone, and Included skills; stretch agents get their own file when built
    - `guide/agents/skills/{citing_exhibits,guidance_only,data_limits,plain_language,persona_handling}.md` with the content listed in the design; every Instruction_File lists `guidance_only`
    - No credentials or secrets; every file forbids instructions to place, route, prefill, or trigger an order, transfer, or brokerage or bank action
    - _Requirements: 21.1, 21.2, 21.3, 21.9, 21.11, 21.12, 21.13, 21.14_

  - [ ]* 6.8 Write property test for System_Prompt composition and Instruction_Hash
    - **Property 50: System_Prompt composition and Instruction_Hash**
    - **Validates: Requirements 21.4, 21.5, 21.6, 21.7**

  - [ ]* 6.9 Write tests for the Instruction_Files and Skill_Files
    - Every agent has an Instruction_File with all required sections; every listed Skill_File exists; every composed System_Prompt contains the guidance_only text; Skill_File statements of Requirements 21.11 to 21.14 are present
    - _Requirements: 10.16, 21.1, 21.2, 21.3, 21.6, 21.11, 21.12, 21.13, 21.14_

- [ ] 7. Implement Tribunal governance logic
  - [x] 7.1 Create `tribunal/request_parser.py`
    - Rule-based extraction of ticker and weight with model fallback; validate against universe; report missing asset or size
    - Expose `parse_request` for reuse by the Companion API
    - _Requirements: 7.21, 14.9_

  - [ ]* 7.2 Write property test for request parsing round trip
    - **Property 18: Request parsing round trip**
    - **Validates: Requirements 7.21**

  - [ ] 7.3 Create `tribunal/citations.py`
    - `Claim`, `validate_claim`, `enforce` with up to 2 revisions, then removal and Trace record
    - Number-versus-Exhibit check: equal after rounding the Exhibit value to the decimals stated in the claim
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.8_

  - [ ]* 7.4 Write property test for claim validation and revision bound
    - **Property 12: Claim validation and revision bound**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6**

  - [ ] 7.5 Create `tribunal/rules.py` with `evaluate_rules` and `decide`
    - Rules on the proposed portfolio: per-asset cap (equity and crypto only, not ETFs), asset-class caps, sector caps, crypto cap, max volatility, max drawdown, speculative limit (crypto plus assets above `speculative_volatility_threshold` 0.45), ESG exclusion from `data/esg_exclusions.csv` when the contract lists `fossil_fuel_screen`
    - Verdict: all pass gives accept; otherwise `max_weight_within_contract` (task 21.2, 0.5-point grid) gives accept with conditions; an ESG failure or no positive size gives reject; tension statement for low-to-moderate personas exceeding the per-asset cap
    - Log each rule check to the Trace; reproduce the expected Verdicts of the design table "Demo cases"
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.9, 5.10, 5.13, 5.14, 5.15, 32.3_

  - [ ]* 7.6 Write property test for Judge determinism and verdict consistency
    - **Property 13: Judge determinism and verdict consistency**
    - **Validates: Requirements 5.1, 5.2, 5.4, 5.9**

  - [ ]* 7.7 Write property test for numeric and sufficient conditions
    - **Property 14: Conditions are numeric and sufficient**
    - **Validates: Requirements 5.3**

  - [ ] 7.8 Create `tribunal/guidance_only.py`
    - `check_guidance_only(agent, statements)` returns `GuidanceFinding` list using a deterministic pattern list: imperative order or transfer instructions, simulated execution ("order submitted", "trade confirmed"), prefill or trigger language
    - `strip_violations(ruling, findings)` removes failing statements from the Ruling and returns Trace events for each removal
    - Record one pass or fail Trace event per checked agent output; produce the guidance-only message for the UI
    - _Requirements: 5.11, 5.12, 13.1, 13.6_

  - [ ] 7.9 Create `tribunal/sensitivity.py`
    - Vary position size (0.5-point grid, same as `max_weight_within_contract`) and each Investor_Contract value used by a failing rule over `sensitivity_ranges`, and the 2022 drawdown period; report threshold or "no change in tested range" (horizon is used by no rule, so report it as no change); store each result as an Exhibit
    - _Requirements: 6.5, 6.6, 6.7_

  - [ ]* 7.10 Write property test for sensitivity thresholds
    - **Property 17: Sensitivity thresholds flip the Verdict**
    - **Validates: Requirements 6.5, 6.6, 6.7**

  - [ ]* 7.11 Write property test for guidance-only enforcement
    - **Property 24: Guidance-only enforcement**
    - **Validates: Requirements 5.11, 5.12, 13.6**

- [ ] 8. Implement agents
  - [ ]* 8.1 (Superseded by 29.2 and 29.3; do not implement) Create `agents/investigator.py` and `agents/advocate.py`
    - Two role prompts over the shared Toolkit and Exhibit_Registry; structured JSON claims with citations and numbers
    - Advocate includes at least one claim citing an Exhibit computed at a position size smaller than the request; unsupported topics labeled as unsupported by Exhibits
    - Prompts come from the Instruction_Files and Skill_Files through the Instruction_Loader (6.6, 6.7), which forbid order, transfer, and brokerage or bank instructions
    - _Requirements: 3.9, 4.1, 4.2, 4.7, 4.8, 13.1, 21.8_

  - [ ]* 8.2 (Superseded by 29.4; do not implement) Create `agents/judge.py`
    - Use deterministic rule results; the model writes only the narrative
    - Evidence requests to Investigator or Advocate, at most 2 per session; remaining rules listed as unverified
    - Run `check_guidance_only` on every Investigator, Advocate, and Clerk output and record results in the Trace
    - _Requirements: 5.5, 5.6, 5.9, 5.11, 5.12_

  - [ ] 8.3 Create `agents/clerk.py` as a code template (no model call) for the Ruling
    - Sections Facts, Assumptions, Fictional scenarios, Limits, "What would change the verdict"
    - Code inserts disclaimers, survivorship-bias text, and unsupported-topic notice; Facts cite Exhibits; includes a factor besides volatility
    - Code builds the Assumptions section: period, currency, alignment, pinned Snapshot_Id with retrieval date, and each rule-relevant field with `persona_assumption` or `default` provenance, with its Persona_File rationale
    - Recommendation-like statements use template phrasing "You may wish to consider ... and decide personally"
    - _Requirements: 3.8, 3.9, 6.1, 6.2, 6.3, 6.4, 6.5, 6.8, 6.9, 13.7, 16.16_

  - [ ]* 8.4 Write property test for Ruling structure and citations
    - **Property 16: Ruling structure and citations**
    - **Validates: Requirements 3.8, 6.1, 6.2, 6.4, 6.8, 6.9**

  - [ ]* 8.5 (Superseded: the Judge makes no evidence requests) Write property test for bounded evidence requests
    - **Property 15: Evidence requests are bounded**
    - **Validates: Requirements 5.5, 5.6**

  - [ ]* 8.6 Write property test for guidance phrasing of recommendations
    - **Property 25: Guidance phrasing of recommendations**
    - **Validates: Requirements 13.7**

  - [ ]* 8.7 Write property test for the Assumptions section
    - **Property 38: Assumptions section lists snapshot and assumed contract values**
    - **Validates: Requirements 6.3, 16.16**

- [ ] 9. Implement orchestrator and memory
  - [ ] 9.1 Create `memory.py` (`MemoryStore`) wrapping AgentCore Memory
    - `save_contract`, `save_summary`, `load_contract`, keyed by profile identifier
    - _Requirements: 8.4_

  - [ ] 9.2 Create `tribunal/orchestrator.py`
    - Flow: load all Instruction_Files (`load_all`), pin snapshot (`SnapshotStore.pin()`), Profiler, schema validation gate, Investigator and Advocate, citation enforcement, Judge, guidance-only check and violation stripping, Clerk, memory save, Trace export
    - Create the `ExhibitRegistry` with the pinned `SnapshotInfo`; record `snapshot_pinned` or `cache_fallback` in the Trace; write `snapshot` and `data_notices` into the `SessionView`
    - Do not start a session on an invalid contract, a Persona_File load error, `DatasetUnavailable`, `DataConfigError`, or `DataIntegrityError`; surface the failing stage on error
    - Write each stage output (including plain-language summary and active agent) into the shared `SessionView` as the stage completes
    - _Requirements: 1.4, 4.1, 4.2, 5.1, 5.12, 6.1, 7.4, 7.20, 8.4, 9.4, 9.7, 13.6, 16.6, 17.2, 17.7, 17.10, 17.12, 17.13, 21.5_

  - [ ]* 9.3 Write property test for Trace completeness and link chain (mocked agents)
    - **Property 20: Trace completeness and link chain**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.5, 9.6, 9.7, 9.8**

  - [ ]* 9.4 Write scenario tests with mocked Bedrock
    - Robert "30% in TSLA" is not an unconditional accept; Amira crypto-heavy request applies the asset-class cap; Mateo Ruling reports absent ESG scores; Ruling numbers match cited Exhibits; sensitivity threshold flips the Verdict; tension statement for low-to-moderate risk; Advocate includes a reduced-size claim
    - _Requirements: 3.9, 4.7, 5.10, 10.3, 10.4, 10.5, 10.6, 10.8_

  - [ ]* 9.5 Write test that Guardrail and Judge block order-instructing outputs
    - Mocked Guardrail intervention and Judge check on outputs that instruct or trigger an order, transfer, or brokerage or bank action; assert block, Trace entry, and guidance-only message
    - _Requirements: 5.8, 13.6, 13.8_

  - [ ]* 9.6 Write property test for snapshot pinning and determinism
    - **Property 41: Snapshot pinning and determinism**
    - **Validates: Requirements 2.2, 2.4, 17.1, 17.2, 17.3**

  - [ ]* 9.7 Write property test for fallback classification and recording
    - **Property 43: Fallback classification and recording**
    - **Validates: Requirements 9.7, 17.8, 17.9, 17.10, 17.11, 17.12, 17.13**

  - [ ]* 9.8 Write fallback and cross-source scenario tests
    - `moto` bucket seeded with the baseline snapshot via `ingest/seed.py`; S3 raises `EndpointConnectionError` with a pre-filled cache: session completes, Trace has `cache_fallback`, every Exhibit has the note, `SessionView` has the notice
    - Same snapshot from `moto` S3 and from the cache gives identical Exhibit values
    - _Requirements: 10.10, 10.11, 17.8, 17.10, 17.11, 17.12_

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Implement the web UI (Friendly_Mode and Advanced_Mode) and the shared SessionView
  - [ ] 11.1 Create `tribunal/session_view.py` with the shared `SessionView` and `tribunal/session_view.schema.json`
    - Fields: session_id, status (`running`, `completed`, `failed`), contract, stage, stages_done, active_agent, exhibits, verdict, ruling, rule_results, sensitivity, trace, summaries, snapshot, data_notices, error; the browser mode and focus are not part of it
    - `session_view_to_json` and `session_view_from_json` validate against the JSON schema and raise an error naming the failing fields
    - Helper functions that build a SessionView update for a finished stage, for a data notice, and for a failure (failing stage and message)
    - _Requirements: 7.9, 7.14, 7.15, 7.16, 7.17, 7.22, 17.12, 22.15, 22.17_

  - [ ] 11.2 Create `tribunal/summaries.py`
    - Template-built plain-language summary per agent stage from structured output; truncate at a sentence boundary to at most 60 words; numbers come from Exhibits with Exhibit links
    - _Requirements: 7.11, 7.12_

  - [ ] 11.3 Create the `frontend/` project and `frontend/src/friendly/` Friendly_Mode components
    - Vite, React, and TypeScript project with Vitest, React Testing Library, fast-check, and the Amplify Auth library; an `npm run gen:types` script generates `src/model/sessionView.ts` types from `session_view.schema.json`
    - View store in `src/model/sessionView.ts` holding `view`, `mode` (default `friendly`), and `focus`; a mode switch changes only `mode` and never calls the API; `setFocus` for an Exhibit, rule, or Trace entry
    - Courtroom scene as an inline SVG component with Investigator, Advocate, Judge, and Clerk seats; highlight the seat of `view.active_agent`; show the summary
    - Verdict and "What would change the verdict" in plain language with `[Exhibit N]` links; a "See details" control sets `focus` and switches to Advanced_Mode
    - _Requirements: 7.9, 7.10, 7.11, 7.12, 7.14, 7.15, 7.16, 7.17_

  - [ ] 11.4 Create `frontend/src/advanced/` Advanced_Mode components
    - Exhibit list, per-rule pass or fail table with observed values and limits, Sensitivity_Analysis results, trace panel (agent calls with Instruction_Hash, tool calls, Exhibits, Judge checks, Guardrail blocks, data events), Trace JSON download
    - Open and scroll to the item in `focus`; Exhibit citations render as clickable elements opening Exhibit details, including Snapshot_Id
    - _Requirements: 7.6, 7.7, 7.13, 7.17_

  - [ ] 11.5 Create `frontend/src/App.tsx`, `src/api/client.ts`, and the sign-in gate
    - Sign-in through Amplify Auth against the Cognito user pool; show no session data before sign-in; the API client sends the access token and reads `config.json` for the API URL and Cognito identifiers
    - Persona picker (every valid Persona_Template and saved Custom_Profile from `GET /personas` and `GET /profiles`; disabled with the loading error shown when the Persona_File fails to load), custom-profile form pre-filled from a selected template, save as Custom_Profile, request box, mode switch
    - `POST /sessions`, then poll `GET /sessions/{id}` every 2 seconds until `completed` or `failed`; stage progress from `stage` and `stages_done`
    - Persistent simulation banner and guidance-only statement in both modes; data badge with Snapshot_Id, source, and retrieval timestamp; Cache_Fallback notice in both modes
    - Keep inputs in browser state on failure and show the failing stage; prompt for a missing asset or size
    - Only input, navigation, and download controls; no action controls; no AWS keys in the bundle
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.8, 7.9, 7.14, 7.18, 7.19, 7.20, 7.21, 7.22, 7.23, 16.5, 16.6, 17.12, 22.2, 22.13_

  - [ ]* 11.6 Write property test for summary length and numbers
    - **Property 27: Plain-language summary length and numbers**
    - **Validates: Requirements 7.11**

  - [ ]* 11.7 Write property test that both modes render the same data (fast-check)
    - **Property 28: Modes render the same data**
    - **Validates: Requirements 7.12, 7.15**

  - [ ]* 11.8 Write property test for mode switching preserving Session_State (fast-check)
    - **Property 29: Mode switching preserves Session_State**
    - **Validates: Requirements 7.14**

  - [ ]* 11.9 Write property test for focus links (fast-check)
    - **Property 30: Focus link opens the same item**
    - **Validates: Requirements 7.17**

  - [ ]* 11.10 Write front-end component tests (Vitest and React Testing Library)
    - Replace the former Streamlit AppTest tests: persona and Custom_Profile options and form fields; Friendly_Mode is the default; courtroom scene shows four agents and highlights the active one; simulation banner, guidance-only statement, and snapshot badge in both modes; Advanced_Mode shows Exhibits, rule table, sensitivity results, trace, and JSON download; failed SessionView keeps inputs and shows the stage; missing-field prompt; mode switch during a session keeps state; fallback notice in both modes; Persona_File load error disables the picker and keeps the form; unauthenticated user sees only the sign-in page
    - Fixtures are SessionViews that validate against `session_view.schema.json`
    - _Requirements: 7.1, 7.2, 7.3, 7.8, 7.10, 7.13, 7.14, 7.16, 7.18, 7.20, 7.21, 7.22, 10.19, 16.6, 17.12, 22.2_

  - [ ]* 11.11 Write test that the UI has no action controls
    - Render every view state and assert that only allowed interactive element kinds exist; assert that no handler calls a URL outside the Session_API and that `frontend/src` imports no brokerage or bank client
    - _Requirements: 7.19, 13.2, 13.4, 10.19_

  - [ ]* 11.12 Write property test for the SessionView round trip
    - **Property 52: SessionView round trip**
    - **Validates: Requirements 22.15, 22.16**

- [ ] 12. AWS configuration templates, data platform, guidance-only scan, and deliverable files
  - [ ] 12.1 Create `deploy/` templates for the Guardrail and least-privilege IAM policies
    - Implemented as CDK constructs in `infra/stacks/guardrail_stack.py` and a shared `infra/iam.py` helper; the synthesized CloudFormation templates are the deployment templates
    - Guardrail already exists: `verdict-guardrail` (ID in `config.yaml`, version DRAFT). Output-only denied topics RealTransactions and ReturnPredictions, HIGH prompt-attack filter on input. No personalized-advice topic: it blocked valid demo verdicts; the guidance-only check covers that wording. A template is optional
    - IAM helper builds the roles of the design table: Application_Role (Bedrock on model and Guardrail ARNs; `s3:GetObject`, `s3:GetObjectVersion` on snapshot, curated, and pointer keys only; Session_Store item actions by table name; AgentCore Memory on one resource; trace and metric write), Seed_Import_Job (S3 get/put on snapshot, curated, pointer prefixes; `glue:GetTable`, `glue:BatchCreatePartition`; Athena query permissions), Athena query (workgroup, Glue read, curated read, results bucket prefix)
    - No `s3:DeleteObject`, no `*` action or resource, no brokerage or bank permissions
    - _Requirements: 5.7, 8.2, 8.9, 8.10, 8.11, 8.12, 13.5, 25.1_

  - [ ] 12.2 Create `docs/data_sources.md`, `README.md`, technical doc, one-page summary, and demo script
    - Data-source entries (origin, retrieval date, processing including CSV to Parquet and snapshot layout, limitations, terms) for every starter file; the Yahoo Finance entry states the origin of the starter prices and corporate actions, the datathon permission recorded in `sources_metadata.csv`, that `data/build_dataset.py` (Baseline_Build_Script) built the starter files and stays unchanged, and that the team downloads no new Yahoo Finance data
    - README: dependencies, configuration, `make deploy`, `make seed`, `make destroy`, smoke test, deploy the stacks, seed the baseline snapshot, pre-fill the cache, run the Seed_Import_Job
    - Technical doc with worked example linking a conclusion to Exhibits, Trace entries (including Instruction_Hash), and the snapshot manifest; Persona_File quoted versus assumption values; AWS_Service_Map table copied from the design with MVP or stretch status; hosting decision and trade-off
    - Demo script with Robert and Amira against the real S3 Primary_Store, naming each MVP AWS service shown (Amplify and Cognito sign-in, Session_API and Agent_Runtime, Guardrail block, Trace and AgentCore Observability, S3 pinned snapshot, Glue tables, one Athena validation query, CloudWatch dashboard); any Cache_Fallback demonstration is a separate, labelled scenario
    - Simulation, no-advice, no-prediction statements in README and summary; state the Guidance_Only_Rule (the system only guides and never performs an action, holds no credentials) in the README, technical documentation, and one-page summary
    - _Requirements: 3.10, 3.11, 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10, 13.10, 20.4, 20.11, 26.7_

  - [x] 12.3 Create the static scanner `guide/guidance_scan.py`
    - Scan source and configuration text for brokerage or bank API client imports and credential patterns from a configured pattern list; return findings
    - _Requirements: 13.2, 13.3, 13.4, 13.9_

  - [ ]* 12.4 Write property test for the static scanner
    - **Property 26: Static scan detects credentials and brokerage or bank clients**
    - **Validates: Requirements 13.2, 13.3, 13.4, 13.9**

  - [ ]* 12.5 Write `tests/test_guidance_scan.py` repository scan and documentation check
    - Run the scanner over the repository source, configuration, `frontend/src`, `infra/`, Instruction_Files, and Skill_Files and assert no findings; assert README, technical documentation, and one-page summary contain the Guidance_Only_Rule statement
    - _Requirements: 13.9, 13.10, 21.10_

  - [ ]* 12.6 Write Guardrail integration test against real AWS
    - Guardrail blocks a trade instruction, an order, transfer, or brokerage or bank action, and a return prediction; it passes the Robert and Mateo demo verdict texts
    - _Requirements: 5.7, 5.8, 13.5_

  - [ ] 12.7 Create the CDK `DataStack` in `infra/stacks/data_stack.py` (S3, Glue, Athena)
    - Primary_Store bucket: versioning, SSE-S3, Block Public Access, TLS-only bucket policy, deny `s3:DeleteObject` and `s3:DeleteObjectVersion` on `snapshots/` and `curated/` for every principal; retain policy on destroy
    - Athena results bucket: SSE-S3, Block Public Access, 7-day expiration
    - Glue database `alphaforge_guide` and five tables with explicit columns generated from `TABLE_SCHEMAS`, Parquet SerDe, `snapshot_id` partition key, locations under `curated/{table}/`; no Glue crawler
    - Athena workgroup with enforced configuration, result location, encryption, and `BytesScannedCutoffPerQuery`
    - Seed_Import_Job role and Athena query role from the IAM helper of 12.1
    - _Requirements: 8.13, 8.14, 18.4, 18.7, 19.1, 24.7, 26.1_

  - [ ] 12.8 Create `ingest/validate.py`
    - Python validation checks mirroring the checks of `data/build_dataset.py`: duplicate (date, ticker), missing tickers, currency mismatch with the universe, non-positive adj_close
    - `restrict_universe(requested, universe, additions, data_sources_doc)`: accept universe tickers and documented additions only, name rejected tickers
    - _Requirements: 20.2, 20.3, 20.6, 20.7, 20.8_

  - [ ]* 12.9 Write property test for seed validation
    - **Property 45: Seed validation detects exactly the injected violations**
    - **Validates: Requirements 20.6, 20.7**

  - [ ]* 12.11 Write property test for universe restriction
    - **Property 47: Universe restriction**
    - **Validates: Requirements 20.2, 20.3, 20.8**

  - [ ] 12.12 Create `data/catalog.py` for Glue partition registration
    - `register_partitions(glue, database, bucket, prefix, snapshot_id)` calls `BatchCreatePartition` for the five tables; `AlreadyExistsException` counts as success
    - _Requirements: 18.5_

  - [ ] 12.13 Create `athena/queries.py` and saved queries in `athena/sql/`
    - `build_query(name, snapshot_id)` rejects ids not matching `SNAPSHOT_ID_RE` and uses `snapshot_id = ?` with `ExecutionParameters`; never concatenates the id into SQL
    - `validation_queries(snapshot_id)`: row counts per table, duplicates, ticker set equality, adj_close <= 0, currency mismatch; `run_query` with the configured workgroup and a timeout
    - At least one saved exploration query per Dataset table, each filtered by `snapshot_id`
    - _Requirements: 19.2, 19.5, 19.6, 19.7_

  - [ ]* 12.14 Write property test for the Athena query builder
    - **Property 48: Athena queries are snapshot-scoped and injection-safe**
    - **Validates: Requirements 19.6, 19.7**

  - [ ] 12.15 Create `ingest/writer.py` (Snapshot_Writer, Tier 2 lean)
    - `write_snapshot(draft, s3, glue, athena, config)` in order: Python validation, raw CSV and Parquet (collect SHA-256), Glue partitions, Athena row-count and duplicate queries (recorded as `skipped` if Athena is unavailable), manifest, then pointer last
    - Refuse to write when the Snapshot_Id prefix already exists (one `ListObjectsV2` check)
    - Return `WriteResult` with status, failed step, and violations; the pointer changes only at the last step
    - The full version (`IfNoneMatch`, `IfMatch` on the pointer, VersionId capture, Athena and Python disagreement gate) is task 12.25
    - _Requirements: 18.1, 18.5, 18.6, 19.2, 20.6, 20.7_

  - [ ]* 12.16 Write property test for commit gating and snapshot immutability
    - Use `moto` for S3 and Glue and `Stubber` for Athena; inject failures at each step of the Seed_Import_Job
    - **Property 44: Commit gating and snapshot immutability**
    - **Validates: Requirements 18.6, 18.10, 19.3, 19.4, 20.7**

  - [ ] 12.17 Create `ingest/seed.py` (Seed_Import_Job library and CLI)
    - `seed_snapshot(config, s3, glue, athena, input_dir, label, retrieved_at, additions, dry_run, prefill_cache)` returns `SeedResult`; reads the five CSV files from `input_dir` (default `seed_dir`), applies `restrict_universe`, carries over unchanged tables and records `carried_over`, validates, stops with `exists` when the Snapshot_Id is present, then calls `write_snapshot`
    - Baseline run: `/workshop/Agent52/data`, label `starter`, retrieval date 2026-11-13 from `sources_metadata.csv`, Snapshot_Id `20261113T000000Z-starter`
    - CLI `python -m guide.ingest.seed` with `--input-dir`, `--label`, `--retrieved-at`, `--dry-run`, `--prefill-cache`; `--prefill-cache` copies the pointer, manifest, and Parquet objects into the Local_Cache; no network download of any kind and no yfinance import
    - Create `ingest/universe_additions.yaml` (empty by default)
    - _Requirements: 17.4, 18.8, 20.1, 20.2, 20.3, 20.6, 20.7, 20.8, 20.9_

  - [ ]* 12.20 Write static tests for the deployment templates
    - Run `cdk synth` and use `aws_cdk.assertions` plus `cfn-lint`; parse the templates and assert the exact actions and resources per role, no `*` action or resource, no `s3:DeleteObject`, delete-deny bucket policy, versioning, encryption, and public access block, Glue columns equal `TABLE_SCHEMAS` with `snapshot_id` partition key, no `AWS::Glue::Crawler`, workgroup enforcement settings, and the Guardrail denied topics
    - _Requirements: 8.10, 8.11, 8.12, 8.13, 8.14, 10.15, 18.4, 18.7, 19.1, 24.7_

  - [ ]* 12.21 Write integration tests against real AWS for the data platform
    - Seed the baseline snapshot into a test prefix, pin it from S3, and assert that Athena row counts per table equal the Data_Loader counts and that the validation queries pass
    - _Requirements: 10.14, 17.1, 18.5, 19.2_

  - [ ]* 12.22 Write static checks for data boundaries and documentation
    - `guide/toolkit` imports neither `yfinance` nor `guide.athena`; the guide package, `data/build_dataset_s3.py` when present, and `requirements.txt` contain no yfinance import, dependency, or Yahoo Finance download call; `data/build_dataset.py` is unchanged against its committed hash and no test, job, or deployment step runs it; `docs/data_sources.md` contains the statements of Requirement 20.4; each Dataset table has a saved query in `athena/sql/`
    - _Requirements: 10.17, 19.5, 19.8, 20.4, 20.5, 20.11_

  - [ ]* 12.23 Create `data/build_dataset_s3.py` (S3_Build_Script, optional future improvement)
    - Future improvement, ready to implement once the S3-first storage tasks (1.8, 12.7, 12.15, 12.17) exist; thin command-line wrapper that calls `seed_snapshot` and adds no logic of its own
    - Options `--input-dir` (default `seed_dir`; may be the output directory of `data/build_dataset.py`), `--label`, `--retrieved-at`, `--dry-run`, `--prefill-cache`; builds or rebuilds a dated Dataset_Snapshot (raw CSV, Parquet, manifest, pointer) in S3 and registers it in Glue
    - Does not modify, import, or run `data/build_dataset.py`; contains no download call and no option that downloads data from Yahoo Finance, the Bank of Canada, FRED, or anywhere else; imports no `yfinance`
    - Document the script in the README and `docs/data_sources.md`
    - _Requirements: 27.1, 27.2, 27.3, 27.4, 27.5, 27.6, 27.7, 27.10_

  - [ ]* 12.24 Write tests for the S3_Build_Script
    - **Property 54: Deterministic and idempotent seed build**
    - **Validates: Requirements 27.7, 27.8, 27.9**
    - Unit tests with `moto`: `--dry-run` writes nothing and prints the planned keys; an existing Snapshot_Id writes nothing; the script file contains no `yfinance` or `build_dataset` import and no network call
    - _Requirements: 10.20, 27.4, 27.5, 27.7, 27.8, 27.9_

- [ ] 14. Alerts (optional stretch)
  - [ ]* 14.1 Create `alerts/engine.py` with `MarketEvent` and `detect_market_events`
    - Pure function using only observations on or before `as_of`; single-day move and portfolio drawdown thresholds read from `config.yaml`
    - _Requirements: 15.1, 15.5_

  - [ ]* 14.2 Implement `Alert` and `build_alerts` in `alerts/engine.py`
    - Keep only events affecting held assets of the Simulated_Portfolio; create the quantifying Exhibit; add guidance, simulation, and not-personalized-advice labels, the Dataset_Snapshot basis statement with Snapshot_Id and retrieval date, and a Tribunal_Session link; record each Alert in the Trace with its Exhibit number
    - Build summaries from a template with no buy, sell, or transfer instruction and pass them through `check_guidance_only`
    - _Requirements: 15.2, 15.3, 15.6, 15.7, 15.8, 15.9, 15.10_

  - [ ]* 14.3 Write property test for Market_Event detection
    - **Property 33: Market_Event detection by threshold and as-of**
    - **Validates: Requirements 15.1, 15.5**

  - [ ]* 14.4 Write property test for Alert construction
    - **Property 34: Alert construction**
    - **Validates: Requirements 15.2, 15.3, 15.6, 15.8, 15.9, 15.10**

  - [ ]* 14.5 Write property test that Alerts contain no action instruction
    - **Property 35: Alerts contain no action instruction**
    - **Validates: Requirements 15.7**

  - [ ]* 14.6 Add Alert notifications to the UI
    - Add an `alerts` list to the SessionView schema and render it in `frontend/src`
    - Friendly_Mode shows the plain-language summary as a notification; Advanced_Mode shows the underlying Exhibits; each Alert links to a Tribunal_Session for the position
    - _Requirements: 15.4, 15.6_

  - [ ]* 14.7 Write Alerts unit tests
    - Fixed price table with a known 15 percent single-day drop gives one Alert for a held asset and none for an unheld asset; Friendly_Mode shows the summary and Advanced_Mode shows the Exhibit
    - _Requirements: 15.2, 15.4, 15.9_

- [ ] 15. Flight Simulator (optional stretch)
  - [ ]* 15.1 Create `toolkit/flight_tools.py` with `portfolio_value`, `market_snapshot`, `detect_stress_events`
    - All functions accept `as_of` and use only data available on that date; register as Converse tools
    - _Requirements: 12.2, 12.3_

  - [ ]* 15.2 Write property test for stress-event detection
    - **Property 22: Stress-event detection**
    - **Validates: Requirements 12.3**

  - [ ]* 15.3 Create `flight/engine.py` and Flight_Director agent
    - Weekly replay from 2021-11-12 with a fictional portfolio; pause at Stress_Events
    - _Requirements: 12.1, 12.3_

  - [ ]* 15.4 Create Copilot and Behavior_Analyst agents
    - Copilot explains stress events with as-of Exhibits and asks hold, sell, or buy more; Analyst logs decisions with date and drawdown, compares to contract `max_drawdown`, proposes an update
    - _Requirements: 12.4, 12.5, 12.6_

  - [ ]* 15.5 Write property test for revealed drawdown comparison
    - **Property 23: Revealed drawdown comparison**
    - **Validates: Requirements 12.6, 12.8**

  - [ ]* 15.6 Wire the simulator into the UI and memory
    - Replay view, decision buttons, approval step before replacing the stored contract, store revealed-tolerance result in AgentCore Memory
    - _Requirements: 12.7, 12.8_

- [ ] 16. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Session_API, Session_Store, and Agent_Runtime packaging (Req. 22, 23)
  - [ ] 17.1 Create `tribunal/entrypoint.py` with `run_session` and the local runner `guide/run_session.py`
    - `run_session(request, sink)` is the single entry point: load all Instruction_Files, pin the snapshot, run the orchestrator, publish SessionViews to the `SessionSink`; the Agent_Runtime, the tests, and `python -m guide.run_session` all call it
    - The local runner uses the in-memory sink and prints the final SessionView JSON
    - _Requirements: 22.6, 22.14_

  - [ ] 17.2 Create `session/store.py` (`SessionStore` and the `SessionSink` protocol)
    - DynamoDB implementation: partition key `owner`, sort key `session#<id>` or `profile#<id>`, `view`, `status`, `updated_at`, `ttl` (creation plus 7 days, sessions only); `put_view`, `get_view(owner, id)`, `put_profile`, `list_profiles`; an in-memory implementation with the same interface
    - Reads always take the owner from the caller, so a foreign session identifier finds no item
    - _Requirements: 7.23, 22.5, 22.6, 22.7, 22.8, 22.12_

  - [ ] 17.3 Extend `tribunal/orchestrator.py` to publish the SessionView to a `SessionSink` (follow-up to 9.2)
    - Write the SessionView after each stage and on failure (`status=failed`, failing stage, message); call `load_all` for the Instruction_Files before the pin step
    - _Requirements: 21.5, 22.6, 22.17, 7.20_

  - [ ] 17.4 Create `runtime/app.py` and `runtime/Dockerfile` (AgentCore Runtime entry point)
    - Entry point from the AgentCore Python SDK; validate the payload `{session_id, owner, profile, request_text}`; start `run_session` as a background task with the DynamoDB sink; return an acknowledgement before the Verdict exists; confirm the SDK's async task API names against the pinned version
    - Emit OpenTelemetry spans (agent call, tool call, Judge check) with Snapshot_Id, and EMF metrics `SessionsStarted`, `SessionsFailed`, `GuardrailInterventions`, `BedrockThrottles`, `CacheFallbacks`
    - Dockerfile for the container image; the image holds the guide package and the Instruction_Files and Skill_Files
    - _Requirements: 23.1, 23.2, 23.3, 23.5, 25.4_

  - [ ] 17.5 Create `api/handler.py` (Session_API Lambda handlers)
    - Routes: `GET /personas`, `GET /profiles`, `PUT /profiles/{id}`, `POST /sessions`, `GET /sessions/{id}`, `GET /sessions/{id}/trace`, and nothing else
    - Owner comes from the validated token claim `sub`; `POST /sessions` parses the request with `parse_request`, validates the contract, writes the `running` item, invokes the Agent_Runtime, and returns the identifier; a runtime failure writes `failed` with stage `runtime` and returns 503; every response validates against `session_view.schema.json`; CORS limited to the configured origin
    - _Requirements: 7.1, 7.13, 7.21, 7.23, 22.3, 22.4, 22.5, 22.7, 22.8, 22.9, 22.10, 22.11, 23.6_

  - [ ] 17.6 Extend `memory.py` to key entries by user and profile (follow-up to 9.1)
    - `MemoryStore` takes the Cognito user identifier; keys are `{user_id}/{profile_id}`; reads return only the caller's entries
    - _Requirements: 8.4, 23.4_

  - [ ]* 17.7 Write property test for session and memory ownership isolation
    - Use the in-memory store and a fake Memory client
    - **Property 51: Session and memory ownership isolation**
    - **Validates: Requirements 22.7, 22.8, 23.4**

  - [ ]* 17.8 Write Session_API tests
    - Handlers against `moto` DynamoDB and a fake runtime client: 401 without a token context, 404 for a foreign session, `POST /sessions` writes a `running` item and returns an identifier, runtime error gives `failed` and 503, responses validate against the schema, route table equals the allowed list
    - _Requirements: 10.18, 22.4, 22.8, 22.9, 22.10, 23.6_

  - [ ]* 17.9 Create `gateway/tools_lambda.py` exposing the Toolkit as MCP tools (AgentCore Gateway, stretch)
    - Lambda target that publishes each read-only Toolkit function with the same JSON input schema as its Converse tool spec; each call opens an Exhibit_Registry for the supplied session id and pinned snapshot
    - _Requirements: 23.7, 23.8_

  - [ ]* 17.10 Write property test for Gateway and in-process parity (stretch)
    - **Property 53: Gateway and in-process parity (stretch)**
    - **Validates: Requirements 23.7, 23.8**

- [ ] 18. Infrastructure as code (CDK Python) and one-command deployment (Req. 25, 26)
  - [ ] 18.1 Create the CDK app skeleton `infra/app.py`, `infra/cdk.json`, `infra/requirements.txt`, and the `Makefile`
    - Context keys: region, bucket suffix, model id, budget amount, budget email, and the flags `enable_waf`, `enable_kms`, `enable_cloudtrail`, `enable_object_lock`, `enable_gateway`, `enable_identity`, `enable_pipeline`; no credentials
    - Pin an `aws-cdk-lib` version that contains the `aws_bedrockagentcore` constructs; if a resource type is missing, document the AWS CLI step that creates it and passes its ARN as context
    - `Makefile` targets `deploy`, `seed`, and `destroy` call scripts under `scripts/`
    - _Requirements: 26.1, 26.2, 26.3, 26.4_

  - [ ] 18.2 Create `infra/stacks/auth_stack.py` (Cognito user pool and app client)
    - Authorization code with PKCE, no client secret, password policy, email sign-in; outputs the user pool and client identifiers
    - _Requirements: 22.2, 22.3_

  - [ ] 18.3 Create `infra/stacks/runtime_stack.py` (AgentCore Runtime, Memory, Application_Role)
    - ECR image asset from `runtime/Dockerfile`; AgentCore Runtime and Memory resources; Application_Role from the IAM helper; the Session_Store table name is a config value, so ARNs are built from names and the stacks have no cycle
    - When `enable_identity` is set, add the JWT inbound authorizer with the Cognito user pool
    - _Requirements: 8.9, 8.10, 23.1, 23.3, 23.9, 25.1_

  - [ ] 18.4 Create `infra/stacks/api_stack.py` (Session_Store, Lambdas, REST API)
    - DynamoDB on-demand table with `ttl`; Python Lambda functions with X-Ray active tracing and the scoped Session_API role; REST API with the Cognito authorizer on every method, only the routes of 17.5, CORS limited to the Amplify origin
    - _Requirements: 22.3, 22.9, 22.10, 22.11, 22.12, 25.2, 25.8_

  - [ ] 18.5 Create `infra/stacks/frontend_stack.py` and `scripts/publish_frontend.sh`
    - Amplify Hosting app and branch for manual deployment; the script builds `frontend/`, writes `config.json` from the stack outputs, zips `dist/`, and runs `aws amplify create-deployment` and `start-deployment`
    - _Requirements: 22.1, 26.2_

  - [ ] 18.6 Create `infra/stacks/ops_stack.py` (Tier 2 lean)
    - Log groups with 30-day retention for the Session_API and the Agent_Runtime; Bedrock model invocation logging to a CloudWatch log group through an AWS-SDK custom resource
    - Dashboard, alarms, SNS topic, and AWS Budgets are task 18.12
    - _Requirements: 25.3, 25.6_

  - [ ] 18.7 Wire all MVP stacks in `infra/app.py`, add outputs, and complete `make deploy`, `make seed`, `make destroy`
    - Outputs: UI URL, Session_API URL, Cognito identifiers, Agent_Runtime ARN, Primary_Store bucket, Athena_Workgroup; `make deploy` builds the front end, runs `cdk deploy --all`, publishes the front end, and prints the UI URL; `make seed` runs `python -m guide.ingest.seed` against the new bucket; `make destroy` removes everything except the Primary_Store bucket
    - _Requirements: 26.2, 26.3, 26.5, 26.6_

  - [ ]* 18.8 Create `infra/stacks/edge_stack.py` (AWS WAF, stretch)
    - Web ACL with the AWS managed common rule group and a rate-based rule, associated with the API stage and the Amplify app
    - _Requirements: 25.9_

  - [ ]* 18.9 Add the optional KMS key, CloudTrail data events, and S3 Object Lock flags (stretch)
    - `enable_kms`: one key with rotation for the Primary_Store, the Session_Store, and the log groups; `enable_cloudtrail`: S3 data events of the Primary_Store; `enable_object_lock`: Primary_Store created with governance-mode Object Lock and 30-day default retention
    - _Requirements: 25.10, 25.11, 25.12_

  - [ ]* 18.10 Write CDK assertion tests for the Auth, Runtime, Api, Frontend, and Ops stacks
    - Cognito authorizer on every method, only the allowed routes, TTL attribute, X-Ray active on every Lambda, 30-day log retention, five dashboard metrics, three alarms with the SNS action, budget notifications, stack outputs, Application_Role and Session_API role scopes
    - _Requirements: 10.15, 10.18, 22.9, 25.1, 25.2, 25.3, 25.4, 25.5, 25.7, 25.8, 26.5_

  - [ ]* 18.11 Create the post-deploy smoke test `scripts/smoke_test.py`
    - Sign in a test Cognito user, post a session for Robert, poll until `completed`, validate the SessionView against the schema, and check that a second user receives 404 for the same session
    - _Requirements: 22.3, 22.5, 22.7, 22.8, 26.7_

  - [ ]* 18.12 Dashboard, alarms, SNS, X-Ray, and AWS Budgets (Tier 3)
    - _Requirements: 25.4, 25.5, 25.7, 25.8_

- [ ] 19. Snapshot_Pipeline (optional stretch, Req. 24)
  - [ ]* 19.1 Create `pipeline/handlers.py` (validate, write, athena_validate, commit Lambdas)
    - Each handler calls the `seed_snapshot` library functions; applies Requirements 20.2, 20.3, and 20.8 before any write; any failure returns the failing step and leaves the pointer unchanged
    - _Requirements: 24.2, 24.3, 24.4_

  - [ ]* 19.2 Create `infra/stacks/pipeline_stack.py` (EventBridge rule and Step Functions state machine)
    - Rule on S3 `Object Created` for keys `incoming/*/_READY`; state machine with the four steps and failure handling; Lambda container images with `pyarrow`; Pipeline role scoped per the design
    - _Requirements: 24.1, 24.2, 24.3, 25.1_

  - [ ]* 19.3 Create `pipeline/glue_job.py` and its CDK resource (Glue ETL variant)
    - Convert each CSV table to Parquet with `TABLE_SCHEMAS`
    - _Requirements: 24.5_

  - [ ]* 19.4 Write parity test between the Glue ETL output and `csv_to_parquet`
    - Same column names, row count, and values for every Dataset table
    - _Requirements: 24.6_

  - [ ]* 12.25 Full Snapshot_Writer (Tier 3): `IfNoneMatch="*"` writes, `IfMatch` pointer commit, VersionId capture, Athena and Python disagreement gate
    - _Requirements: 18.10, 19.3, 19.4_

- [ ] 20. Final deployment checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 21. Base portfolios and risk evidence (Req. 28)
  - [ ] 21.1 Add `base_portfolio` to the three Persona_Templates, `personas.schema.json`, and `contract/portfolio.py::propose(base, asset, weight)`
    - Values from the design table "Proposed Contract_Values": Robert XBB.TO 0.40, ZST.TO 0.15, XIU.TO 0.15, SPY 0.15, JNJ 0.08, RY.TO 0.07; Amira QQQ 0.25, SPY 0.20, XIU.TO 0.15, NVDA 0.10, MSFT 0.10, BTC-USD 0.10, SHOP.TO 0.05, XBB.TO 0.05; Mateo XIU.TO 0.25, XBB.TO 0.25, SPY 0.15, ESGV 0.15, RY.TO 0.10, MSFT 0.05, AGG 0.05; basis `assumption` with rationale
    - Mateo `esg_exclusions: ["fossil_fuel_screen"]` with basis `assumption` and the rationale of the design table
    - _Requirements: 28.1, 28.2, 28.7, 32.3_

  - [ ] 21.2 Add `risk_contribution`, `portfolio_comparison`, and `max_weight_within_contract` to `toolkit/metrics.py` with Converse tool specs
    - `max_weight_within_contract` steps by 0.5 percentage points and becomes the source of numeric conditions in `rules.decide`
    - _Requirements: 28.3, 28.4, 28.5, 5.3_
  - [ ] 21.3 Write the Robert oracle test on the starter data
    - Base max drawdown -10.4 %, +30 % TSLA max drawdown -30.1 % (tolerance 0.3 points), TSLA share of variance 86.7 % (tolerance 1 point)
    - _Requirements: 28.6_

- [ ] 22. Soft preferences decided through the debate (Req. 29)
  - [ ] 22.1 Add `soft_preferences` to the contract schema and to the three Persona_Templates with verbatim excerpts
    - _Requirements: 29.1_
  - [ ]* 22.2 (Superseded by 29.4; do not implement) Extend `agents/judge.py` and `rules.decide`
    - Party A and Party B in an order seeded by the session id, role words stripped, equal claim count; per-preference JSON validated by schema; role mapped back by code; `not_satisfied` turns accept into accept with conditions; code forbids any upgrade; Trace records the order
    - _Requirements: 29.2, 29.3, 29.4, 29.5, 5.9_
  - [ ]* 22.3 Write property test: no Soft_Preference assessment upgrades a Verdict, and the Hard_Rule result always wins
    - _Requirements: 29.4, 5.9_

- [ ] 23. Documented ESG exclusion list (Req. 32)
  - [x] 23.1 Create `data/esg_exclusions.csv` (31 rows) and its entry in `docs/data_sources.md`; list it in the Snapshot_Manifest
    - _Requirements: 32.1, 32.2, 32.5_
  - [ ] 23.2 Add the `esg_exclusion` Hard_Rule and the `exclusion_cost` Exhibit
    - _Requirements: 32.3, 32.4, 10.6_

- [ ] 24. Ruling answers and demo cases (Req. 33)
  - [ ] 24.1 Extend `agents/clerk.py` and the SessionView with the four answers built by code
    - _Requirements: 33.1, 33.4_
  - [ ] 24.2 Create `demo/cases.yaml` with the five cases, the `canadian_heavy` Custom_Profile, the Robert Appeal, and the expected Verdicts and maximum weights of the design table "Demo cases"; add a code-only test of every expected Verdict; add the four-answers card to Friendly_Mode
    - _Requirements: 33.2, 33.3, 33.4_

- [ ] 25. Precedents (Req. 31)
  - [ ] 25.1 Create `tribunal/precedents.py` (`put_precedent`, `closest`) on the Session_Store partition `precedent`, with an in-memory implementation for tests
    - _Requirements: 31.1, 31.3_
  - [ ] 25.2 Pass the closest Precedent to the Judge; check in code that a named differing field exists; create `scripts/seed_precedents.py`
    - _Requirements: 31.2, 31.4_

- [ ] 26. Appeal (Req. 30)
  - [ ] 26.1 Accept `appeal_of` and `change` (position size, period, or one Investor_Contract value) in `POST /sessions`; create `tribunal/appeal.py::diff_sessions`
    - _Requirements: 30.2, 30.3, 30.4_
  - [ ] 26.2 Add the Appeal control and the side-by-side `AppealView` to the UI
    - _Requirements: 30.1, 30.3_

- [ ] 27. Benchmark (Req. 34)
  - [ ] 27.1 Create `guide/bench/` (`baseline.py`, `run.py`, Wilson intervals, Confidence_Labels, call-count guard)
    - _Requirements: 34.1, 34.2, 34.3, 34.5_
  - [ ] 27.2 Write `bench/cases.yaml` (at least five extra cases), run N=5 on AWS before Sunday 16:00, commit `docs/benchmark.md` and `docs/benchmark.json`
    - _Requirements: 34.1, 34.4_

- [ ] 28. Demo resilience and jury access (Req. 35)
  - [ ] 28.1 Create `scripts/create_demo_user.sh` and document the jury credentials step in the README (password from the environment, never committed)
    - _Requirements: 35.1_
  - [ ] 28.2 Add the `?replay=1` route and `npm run build:replay` with the "Replay of a recorded session" label
    - _Requirements: 35.3, 35.4, 35.5_
  - [ ] 28.3 Create `scripts/export_demo.py`; export every demo and Benchmark session to `demo/sessions/` before Sunday 23:59
    - _Requirements: 35.2_


- [ ] 29. Agent flow Advocate, Investigator, Judge (Req. 4, 29, 36; replaces the debate wording of 8.1, 8.2, 22.2)
  - [ ] 29.1 Create `toolkit/risk_panel.py::risk_panel(option, contract)` returning the fixed Exhibit set of the Risk_Panel (uses 21.2) and `currency_exposure`, `sector_weights`, `correlation_with_base`
    - _Requirements: 4.3, 28.3, 28.4, 28.5_
  - [ ] 29.2 Create `agents/advocate.py` and `instructions/advocate.md`: goal plus at most 3 Options as JSON; `advocate_scope` from config; no buy or sell wording
    - _Requirements: 4.1, 4.2, 4.8, 4.9_
  - [ ] 29.3 Create `agents/investigator.py` and `instructions/investigator.md`: material risks per Option with Exhibit and contract field; code check that each named field exists
    - _Requirements: 4.4, 4.5_
  - [ ] 29.4 Rework `agents/judge.py` and `instructions/judge.md`: Soft_Preference assessments per Option, comparison, narrative; code forbids any upgrade; remove evidence requests
    - _Requirements: 5.5, 5.6, 29.2, 29.3, 29.4, 29.5_
  - [ ] 29.5 Rework `tribunal/orchestrator.py` to the fixed order with 3 agent calls, schema validation, timeouts, and the fallbacks of Req. 36; turn the Clerk into a code template
    - _Requirements: 36.1 to 36.8, 6.1_
  - [ ] 29.6 Write tests: at most 3 agent calls; each agent failure still produces a valid Ruling; no output upgrades a Verdict
    - _Requirements: 36.3, 36.5, 36.6, 36.7, 29.4_
  - [ ]* 29.7 Add the ablation runs to `guide/bench`
    - _Requirements: 34.6, 34.7_

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP. All Alerts (14.x) and Flight Simulator (15.x) sub-tasks are optional, as are the stretch tasks 17.9, 17.10, 18.8, 18.9, 19.x and the future S3_Build_Script tasks 12.23 and 12.24; the top-level tasks 14, 15, and 19 are groupings only.
- Removed from the plan: task 13 (Companion_Extension, Requirement 14 removed), 11.12 (data refresh control, replaced by the SessionView round-trip test), 12.10 (coverage-end property, removed with the yfinance job), 12.18 and 12.19 (yfinance Ingestion_Job and its tests, removed because the team downloads no new Yahoo Finance data). Their numbers are not reused, except 11.12. Property numbers 31, 32, and 46 are unused.
- Reworked because the UI is now a React app on Amplify Hosting: group 11 (the former Streamlit tasks were not started). Tasks 12.1 and 12.7 now produce CDK stacks whose synthesized CloudFormation templates are the deployment templates. Task 12.17 is the Seed_Import_Job, the single import concept; the optional 12.23 is a thin wrapper around it.
- Parent tasks 1 and 3 were unchecked because they gained new sub-tasks; their completed sub-tasks 1.1, 3.1, and 3.3 keep their `[x]` status.
- Task 16 closes the core and UI work; tasks 17 to 19 add the AWS delivery layer, and task 20 is the final deployment checkpoint.
- Property 15 is tested in 8.5 because it needs the Judge agent. Property 25 is tested in 8.6 because it needs the Clerk template. Properties 41 and 43 are tested in 9.6 and 9.7 because they need the orchestrator, registry, and SessionView together. Properties 28 to 30 run in the front end with fast-check.
- The guidance-only constraint is covered in four layers: Guardrail denied topics (6.2, 12.1, 12.6), the Judge check (7.8, 8.2, 9.5), the static scan (12.3 to 12.5), and the UI and API without action controls (11.5, 11.11, 17.5, 17.8).
- Persona test (Req. 10.9) is task 2.6; it checks the shipped `personas.yaml` against `data/context.md` and a hand-transcribed fixture.
- The Instruction_Loader and files are tasks 6.6 and 6.7, the tests of Req. 10.16 are task 6.9, and Property 50 is task 6.8.
- No unit or property test calls Yahoo Finance or real AWS; 12.6, 12.21, and 18.11 are the only real-AWS tests.
- `data/build_dataset.py` is the unchanged reference script that built the starter CSV files; no task modifies or runs it.
- Each task references specific requirements for traceability.
- Property tests validate universal correctness properties; unit and scenario tests cover specific examples.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "7.1"] },
    { "id": 1, "tasks": ["1.3", "1.4", "1.6", "2.1", "3.1", "3.3", "6.1", "7.2", "12.3", "23.1", "1.11"] },
    { "id": 2, "tasks": ["1.5", "1.7", "1.8", "2.4", "2.5", "3.4", "3.5", "3.6", "3.7", "3.8", "6.2", "6.5", "7.3", "7.8", "9.1", "12.4", "12.8", "12.12", "12.13", "18.1"] },
    { "id": 3, "tasks": ["1.2", "1.9", "2.2", "3.2", "4.1", "6.3", "6.4", "6.6", "7.4", "7.11", "12.1", "12.7", "12.9", "12.11", "12.14", "12.15", "17.6", "18.2"] },
    { "id": 4, "tasks": ["2.3", "2.6", "2.7", "2.8", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "6.7", "6.8", "7.5", "12.6", "12.17", "14.1", "15.1", "19.3", "21.1", "22.1", "28.1"] },
    { "id": 5, "tasks": ["6.9", "7.6", "7.7", "7.9", "8.1", "8.2", "12.16", "12.21", "12.23", "14.2", "14.3", "15.2", "17.9", "19.1", "19.4", "21.2", "23.2"] },
    { "id": 6, "tasks": ["7.10", "8.3", "8.5", "12.24", "14.4", "14.5", "15.3", "17.10", "21.3", "22.2", "29.1"] },
    { "id": 7, "tasks": ["8.4", "8.6", "8.7", "11.1", "11.2", "15.4", "24.1", "22.3", "29.2", "29.3"] },
    { "id": 8, "tasks": ["9.2", "11.3", "11.6", "11.12", "15.5", "17.2", "29.4"] },
    { "id": 9, "tasks": ["9.3", "9.4", "9.5", "9.6", "9.7", "9.8", "11.4", "17.3", "17.5", "17.7", "24.2", "25.1", "27.1", "29.5"] },
    { "id": 10, "tasks": ["11.5", "11.7", "11.8", "11.9", "17.1", "17.8", "25.2", "26.1", "29.6"] },
    { "id": 11, "tasks": ["11.10", "11.11", "14.6", "15.6", "17.4", "26.2", "28.2"] },
    { "id": 12, "tasks": ["14.7", "18.3"] },
    { "id": 13, "tasks": ["12.20", "18.4"] },
    { "id": 14, "tasks": ["18.5", "18.6"] },
    { "id": 15, "tasks": ["18.7", "18.8", "18.9", "18.10"] },
    { "id": 16, "tasks": ["12.2", "18.11", "19.2", "27.2", "28.3", "29.7"] },
    { "id": 17, "tasks": ["12.5", "12.22", "1.10", "12.25", "18.12"] }
  ]
}
```