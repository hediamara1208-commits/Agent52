# Implementation Plan: Agentic Investment Guide

## Overview

Implementation language: Python 3.11 for the backend, agents, data layer, API, and CDK app (boto3, pandas, pyarrow, jsonschema, pytest, hypothesis, moto, aws-cdk-lib), and TypeScript with React for the UI (Vite, Vitest, React Testing Library, fast-check). The plan builds the deterministic core first (config, S3-primary data layer with Local_Cache, tolerant Persona_File and contract, Exhibits, Toolkit). It then adds governance logic (citations, rules, guidance-only check, sensitivity), the Instruction_Loader with the Instruction_Files and Skill_Files, the agents, the orchestrator, and the web UI (Friendly_Mode and Advanced_Mode over one shared SessionView). The data platform follows: CDK stacks for S3, Glue, and Athena, the Snapshot_Writer, and the Seed_Import_Job. Tasks 17 to 19 add the AWS delivery layer: the Session_API, Session_Store, and Agent_Runtime packaging, the CDK stacks with one-command deployment, and the optional Snapshot_Pipeline. The guidance-only constraint is enforced in four layers: Guardrail denied topics, the Judge-side check, a static scan test, and a UI and API without action controls. Alerts (Requirement 15) and the Flight Simulator (Requirement 12) are optional stretch work: their sub-tasks are marked with `*` and the MVP works without them. The Companion_Extension (Requirement 14) was removed from the scope.

Hosting decision: the UI is a React single-page app on AWS Amplify Hosting with Cognito sign-in, calling a Session_API (API Gateway and Lambda) in front of the unchanged Python core on Amazon Bedrock AgentCore Runtime. Amplify Hosting cannot run a Streamlit server. The design records the options, the decision, and the trade-off, and the AWS service map marks each service as MVP or stretch.

Completed tasks 1.1, 3.1, 3.3, 6.1, and 7.1 keep their text and status. Where the S3-primary data architecture or the tolerant Persona_File changes their behavior, a follow-up task reworks them (1.3 and 1.8 for 1.1, 3.7 for 3.1, 3.8 for 3.3, 6.5 and 6.6 for 6.1, 2.5 for in-progress 2.1). Task 7.1 mentions a Companion API and Requirement 14.9: that reference is historical, because Requirement 14 was removed, and no task depends on it.

## Hackathon execution order (2026-11-14)

The Delivery Tiers in the requirements document decide what is built. Tasks marked `*` are optional and Kiro may skip them. Work in four parallel tracks, one owner per track and per folder. Pull before each task, push after each task.

| Track | Owner | Order |
| --- | --- | --- |
| A: data and toolkit | | 2.1, 2.5, 1.3, 1.4, 1.6, 1.8 (lean), 2.2, 21.1, 22.1, 23.1, 3.7, 3.8, 4.1, 21.2, 21.3, 23.2, 4.2, 4.3, 4.7 |
| B: agents and tribunal | | 6.2, 6.6, 6.7, 7.3, 7.4, 7.5, 7.6, 7.8, 7.9, 7.10, 8.1, 8.2, 22.2, 8.3, 24.1, 9.1, 9.2, 17.1, 9.4, then gate 1, then 17.3, 26.1, 25.1, 25.2, 27.1 |
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

  - [ ] 1.3 Rework `config.py` and `config.yaml` for the S3-primary data architecture (follow-up to 1.1)
    - Remove `data_location` and `data_dir`; `load_config` raises a clear error if `data_location` is present
    - Add `s3_bucket` (required), `s3_prefix`, `cache_dir`, `s3_connect_timeout_seconds`, `s3_read_timeout_seconds`, `s3_max_attempts`, `glue_database`, `athena_workgroup`, `athena_results_uri`, `athena_bytes_scanned_cutoff`, `seed_dir`, `persona_file`, `instruction_dir`, `sensitivity_ranges`, `speculative_volatility_threshold`, `trace_summary_max_chars`, `session_table`, `agent_runtime_arn`, `agentcore_memory_id`, `cors_origin`
    - Keep the redaction filter and the no-credentials rule unchanged; add `cache_dir` to `.gitignore`
    - _Requirements: 6.6, 8.5, 8.6, 8.7, 9.6, 17.8, 19.1, 22.11, 23.2_

  - [ ] 1.4 Create `data/snapshot.py` with Snapshot_Id, manifest, and pointer models
    - `SNAPSHOT_ID_RE`, `FileEntry`, `SnapshotManifest`, `SnapshotPointer`, `SnapshotInfo` (served_from `primary`, `cache`, or `cache_fallback`)
    - `data/manifest.schema.json` and `data/pointer.schema.json`; `manifest_to_json`/`manifest_from_json`, `pointer_to_json`/`pointer_from_json` with `ManifestError(fields)` on schema failure
    - _Requirements: 17.14, 17.15, 17.16, 20.2_

  - [ ]* 1.5 Write property test for manifest and pointer serialization round trip
    - **Property 39: Manifest and pointer serialization round trip**
    - **Validates: Requirements 17.14, 17.15, 17.16**

  - [ ] 1.6 Create `data/parquet_io.py`
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

- [ ] 2. Implement Investor_Contract, schema validation, and Profiler
  - [~] 2.1 Create `contract/schema.json` and `contract/validate.py`
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
    - `guide/agents/instructions/{profiler,prosecutor,defense,judge,clerk}.md` with the sections Role, Goals, Allowed tools, Output JSON format, Forbidden behaviors, Citation rule, Guidance-only rule, Tone, and Included skills; stretch agents get their own file when built
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
    - Rules: per-asset cap, asset-class cap, crypto cap, sector cap, max volatility, max drawdown, ESG (unverified when scores absent), speculative limit (crypto plus assets above `speculative_volatility_threshold`)
    - Bisection over position size for numeric conditions; reject when no positive size passes; tension statement for low-to-moderate risk personas exceeding the per-asset cap
    - Log each rule check to the Trace
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.9, 5.10_

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
    - Vary position size and horizon over `sensitivity_ranges` from config, and the 2022 drawdown period; report threshold or "no change in tested range"; store each result as an Exhibit
    - _Requirements: 6.5, 6.6, 6.7_

  - [ ]* 7.10 Write property test for sensitivity thresholds
    - **Property 17: Sensitivity thresholds flip the Verdict**
    - **Validates: Requirements 6.5, 6.6, 6.7**

  - [ ]* 7.11 Write property test for guidance-only enforcement
    - **Property 24: Guidance-only enforcement**
    - **Validates: Requirements 5.11, 5.12, 13.6**

- [ ] 8. Implement agents
  - [ ] 8.1 Create `agents/prosecutor.py` and `agents/defense.py`
    - Two role prompts over the shared Toolkit and Exhibit_Registry; structured JSON claims with citations and numbers
    - Defense includes at least one claim citing an Exhibit computed at a position size smaller than the request; unsupported topics labeled as unsupported by Exhibits
    - Prompts come from the Instruction_Files and Skill_Files through the Instruction_Loader (6.6, 6.7), which forbid order, transfer, and brokerage or bank instructions
    - _Requirements: 3.9, 4.1, 4.2, 4.7, 4.8, 13.1, 21.8_

  - [ ] 8.2 Create `agents/judge.py`
    - Use deterministic rule results; the model only writes the narrative
    - Evidence requests to Prosecutor or Defense, at most 2 per session; remaining rules listed as unverified
    - Run `check_guidance_only` on every Prosecutor, Defense, and Clerk output and record results in the Trace
    - _Requirements: 5.5, 5.6, 5.9, 5.11, 5.12_

  - [ ] 8.3 Create `agents/clerk.py` with a Ruling template
    - Sections Facts, Assumptions, Fictional scenarios, Limits, "What would change the verdict"
    - Code inserts disclaimers, survivorship-bias text, and unsupported-topic notice; Facts cite Exhibits; includes a factor besides volatility
    - Code builds the Assumptions section: period, currency, alignment, pinned Snapshot_Id with retrieval date, and each rule-relevant field with `persona_assumption` or `default` provenance, with its Persona_File rationale
    - Recommendation-like statements use template phrasing "You may wish to consider ... and decide personally"
    - _Requirements: 3.8, 3.9, 6.1, 6.2, 6.3, 6.4, 6.5, 6.8, 6.9, 13.7, 16.16_

  - [ ]* 8.4 Write property test for Ruling structure and citations
    - **Property 16: Ruling structure and citations**
    - **Validates: Requirements 3.8, 6.1, 6.2, 6.4, 6.8, 6.9**

  - [ ]* 8.5 Write property test for bounded evidence requests
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
    - Flow: load all Instruction_Files (`load_all`), pin snapshot (`SnapshotStore.pin()`), Profiler, schema validation gate, Prosecutor and Defense, citation enforcement, Judge, guidance-only check and violation stripping, Clerk, memory save, Trace export
    - Create the `ExhibitRegistry` with the pinned `SnapshotInfo`; record `snapshot_pinned` or `cache_fallback` in the Trace; write `snapshot` and `data_notices` into the `SessionView`
    - Do not start a session on an invalid contract, a Persona_File load error, `DatasetUnavailable`, `DataConfigError`, or `DataIntegrityError`; surface the failing stage on error
    - Write each stage output (including plain-language summary and active agent) into the shared `SessionView` as the stage completes
    - _Requirements: 1.4, 4.1, 4.2, 5.1, 5.12, 6.1, 7.4, 7.20, 8.4, 9.4, 9.7, 13.6, 16.6, 17.2, 17.7, 17.10, 17.12, 17.13, 21.5_

  - [ ]* 9.3 Write property test for Trace completeness and link chain (mocked agents)
    - **Property 20: Trace completeness and link chain**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.5, 9.6, 9.7, 9.8**

  - [ ]* 9.4 Write scenario tests with mocked Bedrock
    - Robert "30% in TSLA" is not an unconditional accept; Amira crypto-heavy request applies the asset-class cap; Mateo Ruling reports absent ESG scores; Ruling numbers match cited Exhibits; sensitivity threshold flips the Verdict; tension statement for low-to-moderate risk; Defense includes a reduced-size claim
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
    - `moto` bucket seeded with the baseline snapshot via `ingest/seed.py`; S3 raises `EndpointConnectionError` with a pre-filled cache: session completes, Trace has `cache_fallback`, every Exhibit has the note, `SessionView` has the 