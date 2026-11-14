# Implementation Plan: Agentic Investment Guide

## Overview

Implementation language: Python 3.11 (Streamlit, boto3, pandas, jsonschema, pytest, hypothesis). The plan builds the deterministic core first (config, data, contract, Exhibits, Toolkit), then governance logic (citations, rules, guidance-only check, sensitivity), then the agents, orchestrator, and the two-mode UI (Friendly_Mode and Advanced_Mode over one shared SessionView). The guidance-only constraint is enforced in four layers: Guardrail denied topics, the Judge-side check, a static scan test, and a UI without action controls. The Companion_Extension (Requirement 14), Alerts (Requirement 15), and the Flight Simulator (Requirement 12) are optional stretch work: their sub-tasks are marked with `*` and the MVP works without them.

## Tasks

- [x] 1. Set up project structure, configuration, and data access
  - [x] 1.1 Create the `guide/` package layout, `tests/`, `pyproject.toml`/`requirements.txt`, `config.py`, and `data/loader.py`
    - Config loads from environment and `config.yaml`: region, model id, guardrail id and version, S3 bucket, data location, data dir, macro publication lags. No credential fields.
    - Implement `DataSource` protocol with `LocalSource` (/workshop/Agent52/data) and `S3Source`
    - Add a log filter that redacts AWS key patterns
    - _Requirements: 3.5, 8.5, 8.6, 8.7_

  - [ ]* 1.2 Write unit tests for config and loader
    - Local and S3 (mocked) reads return the same frames; no credential fields; log redaction works
    - _Requirements: 8.5, 8.6, 8.7_

- [ ] 2. Implement Investor_Contract, schema validation, and Profiler
  - [~] 2.1 Create `contract/schema.json` and `contract/validate.py`
    - `validate_contract` returns a list of failing fields (empty when valid)
    - _Requirements: 1.3, 1.4_

  - [ ] 2.2 Create `personas.yaml` and `contract/profiler.py`
    - `build_contract_from_persona` and `build_contract_from_form` with provenance (persona, form, default)
    - Amira: per-asset-class cap and diversification rule; Mateo: ESG exclusions and speculative limit; Robert: horizon 3 to 5 years, low crypto cap
    - Model-based mapping of free text to form values is optional input only; validation is always schema-based
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6, 1.7, 1.8_

  - [ ]* 2.3 Write property test for contract validity and provenance
    - **Property 1: Contract validity and provenance**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.5**

  - [ ]* 2.4 Write property test for invalid contract rejection
    - **Property 2: Invalid contracts are rejected with failing fields**
    - **Validates: Requirements 1.4**

- [x] 3. Implement Exhibits, alignment, and data-quality handling
  - [x] 3.1 Create `toolkit/exhibits.py` with frozen `Exhibit` and `ExhibitRegistry`
    - Sequential numbering, all required fields, read-only value and inputs
    - _Requirements: 2.2, 2.3_

  - [ ]* 3.2 Write property test for Exhibit completeness, sequencing, and immutability
    - **Property 3: Exhibit completeness, sequencing, and immutability**
    - **Validates: Requirements 2.2, 2.3**

  - [x] 3.3 Create `toolkit/align.py` and `data/quality.py`
    - As-of filtering for prices, FX, and macro; USD to CAD conversion with FX carry-forward notes
    - Date-intersection calendar alignment with method and observation count notes
    - Macro lag availability; CNQ.TO 2022-08-22 note; survivorship-bias text; unsupported-topic detection (ESG scores, news, fundamentals)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

  - [ ]* 3.4 Write property test for currency conversion and FX carry-forward
    - **Property 7: Currency conversion and FX carry-forward**
    - **Validates: Requirements 3.1, 3.2**

  - [ ]* 3.5 Write property test for calendar alignment
    - **Property 8: Calendar alignment is the date intersection**
    - **Validates: Requirements 3.3**

  - [ ]* 3.6 Write property test for macro publication lag
    - **Property 9: Macro publication lag**
    - **Validates: Requirements 3.4**

- [ ] 4. Implement Toolkit metrics and Converse tool specs
  - [ ] 4.1 Create `toolkit/metrics.py`
    - `annualized_return`, `annualized_volatility`, `max_drawdown` (peak and trough dates), `correlation`, `drawdown_in_period`, `portfolio_metrics`
    - Pipeline: ticker check, as-of filter, FX, alignment, 20-observation check, adj_close returns, CNQ note, register Exhibit
    - Errors return `ToolError` and create no Exhibit
    - _Requirements: 2.1, 2.2, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 3.3, 3.6, 3.7_

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
    - _Requirements: 5.7, 5.8, 8.1, 8.2, 8.8, 13.5, 13.6_

  - [ ]* 6.3 Write property test for throttling retry bound
    - **Property 19: Throttling retry bound**
    - **Validates: Requirements 8.8**

  - [ ]* 6.4 Write property test for Trace export round trip
    - **Property 21: Trace export round trip**
    - **Validates: Requirements 9.4**

- [ ] 7. Implement Tribunal governance logic
  - [x] 7.1 Create `tribunal/request_parser.py`
    - Rule-based extraction of ticker and weight with model fallback; validate against universe; report missing asset or size
    - Expose `parse_request` for reuse by the Companion API
    - _Requirements: 7.21, 14.9_

  - [ ]* 7.2 Write property test for request parsing round trip
    - **Property 18: Request parsing round trip**
    - **Validates: Requirements 7.21, 14.9**

  - [ ] 7.3 Create `tribunal/citations.py`
    - `Claim`, `validate_claim`, `enforce` with up to 2 revisions, then removal and Trace record
    - Number-versus-Exhibit check with rounding tolerance
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.8_

  - [ ]* 7.4 Write property test for claim validation and revision bound
    - **Property 12: Claim validation and revision bound**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6**

  - [ ] 7.5 Create `tribunal/rules.py` with `evaluate_rules` and `decide`
    - Rules: per-asset cap, asset-class cap, crypto cap, sector cap, max volatility, max drawdown, ESG (unverified when scores absent), speculative limit
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
    - Vary position size, horizon, and the 2022 drawdown period; report threshold or "no change in tested range"; store each result as an Exhibit
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
    - Defense considers reduced position size; unsupported topics labeled as unsupported by Exhibits
    - Prompts forbid order, transfer, and brokerage or bank instructions
    - _Requirements: 3.9, 4.1, 4.2, 4.7, 4.8, 13.1_

  - [ ] 8.2 Create `agents/judge.py`
    - Use deterministic rule results; the model writes only the narrative
    - Evidence requests to Prosecutor or Defense, at most 2 per session; remaining rules listed as unverified
    - Run `check_guidance_only` on every Prosecutor, Defense, and Clerk output and record results in the Trace
    - _Requirements: 5.5, 5.6, 5.9, 5.11, 5.12_

  - [ ] 8.3 Create `agents/clerk.py` with a Ruling template
    - Sections Facts, Assumptions, Fictional scenarios, Limits, "What would change the verdict"
    - Code inserts disclaimers, survivorship-bias text, and unsupported-topic notice; Facts cite Exhibits; includes a factor besides volatility
    - Recommendation-like statements use template phrasing "You may wish to consider ... and decide personally"
    - _Requirements: 3.8, 3.9, 6.1, 6.2, 6.3, 6.4, 6.5, 6.8, 6.9, 13.7_

  - [ ]* 8.4 Write property test for Ruling structure and citations
    - **Property 16: Ruling structure and citations**
    - **Validates: Requirements 3.8, 6.1, 6.2, 6.4, 6.8, 6.9**

  - [ ]* 8.5 Write property test for bounded evidence requests
    - **Property 15: Evidence requests are bounded**
    - **Validates: Requirements 5.5, 5.6**

  - [ ]* 8.6 Write property test for guidance phrasing of recommendations
    - **Property 25: Guidance phrasing of recommendations**
    - **Validates: Requirements 13.7**

- [ ] 9. Implement orchestrator and memory
  - [ ] 9.1 Create `memory.py` (`MemoryStore`) wrapping AgentCore Memory
    - `save_contract`, `save_summary`, `load_contract`, keyed by profile identifier
    - _Requirements: 8.4_

  - [ ] 9.2 Create `tribunal/orchestrator.py`
    - Flow: Profiler, schema validation gate, Prosecutor and Defense, citation enforcement, Judge, guidance-only check and violation stripping, Clerk, memory save, Trace export
    - Write each stage output (including plain-language summary and active agent) into the shared `SessionView` as the stage completes
    - Do not start a session on an invalid contract; surface the failing stage on error
    - _Requirements: 1.4, 4.1, 4.2, 5.1, 5.12, 6.1, 7.4, 7.20, 8.4, 9.4, 13.6_

  - [ ]* 9.3 Write property test for Trace completeness and link chain (mocked agents)
    - **Property 20: Trace completeness and link chain**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.5**

  - [ ]* 9.4 Write scenario tests with mocked Bedrock
    - Robert "30% in TSLA" is not an unconditional accept; Amira crypto-heavy request applies the asset-class cap; Mateo Ruling reports absent ESG scores; Ruling numbers match cited Exhibits; sensitivity threshold flips the Verdict; tension statement for low-to-moderate risk
    - _Requirements: 3.9, 5.10, 10.3, 10.4, 10.5, 10.6, 10.8_

  - [ ]* 9.5 Write test that Guardrail and Judge block order-instructing outputs
    - Mocked Guardrail intervention and Judge check on outputs that instruct or trigger an order, transfer, or brokerage or bank action; assert block, Trace entry, and guidance-only message
    - _Requirements: 5.8, 13.6, 13.8_

- [ ] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Implement Streamlit UI (Friendly_Mode and Advanced_Mode)
  - [ ] 11.1 Create `ui/view_model.py` with the shared `SessionView`
    - Fields: mode (default "friendly"), contract, stage, active_agent, exhibits, verdict, ruling, rule_results, sensitivity, trace, summaries, focus
    - Store in `st.session_state["view"]`; a mode switch changes only `view.mode` and never calls the orchestrator
    - `set_focus` for exhibit, rule, or trace entry
    - _Requirements: 7.9, 7.14, 7.15, 7.16, 7.17_

  - [ ] 11.2 Create `tribunal/summaries.py`
    - Template-built plain-language summary per agent stage from structured output; truncate at a sentence boundary to at most 60 words; numbers come from Exhibits with Exhibit links
    - _Requirements: 7.11, 7.12_

  - [ ] 11.3 Create `ui/friendly.py`
    - Courtroom scene (SVG or HTML) with Prosecutor, Defense, Judge, Clerk seats; highlight `view.active_agent`; show the summary
    - Verdict and "What would change the verdict" in plain language with `[Exhibit N]` links
    - "See details" control sets `view.focus` and switches to Advanced_Mode
    - _Requirements: 7.10, 7.11, 7.12, 7.17_

  - [ ] 11.4 Create `ui/advanced.py`
    - Exhibit list, per-rule pass or fail table with observed values and limits, Sensitivity_Analysis results, trace panel (agent calls, tool calls, Exhibits, Judge checks, Guardrail blocks), Trace JSON download
    - Open and scroll to the item in `view.focus`; Exhibit citations render as clickable elements opening Exhibit details
    - _Requirements: 7.6, 7.7, 7.13, 7.17_

  - [ ] 11.5 Create `ui/app.py`
    - Persona picker (Amira, Mateo, Robert), custom-profile form (risk level, horizon, max volatility, max drawdown, per-asset cap, crypto cap, ESG exclusions), request box, mode switch
    - Persistent simulation banner and guidance-only statement in both modes; stage progress with `st.status`; Verdict, Ruling, and rule table on completion
    - Keep inputs in `st.session_state` on failure and show the failing stage; prompt for missing asset or size
    - Only input, navigation, and download widgets; no action controls
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.8, 7.9, 7.14, 7.18, 7.19, 7.20, 7.21_

  - [ ]* 11.6 Write property test for summary length and highlight
    - **Property 27: Plain-language summary length and highlight**
    - **Validates: Requirements 7.11**

  - [ ]* 11.7 Write property test that both modes render the same data
    - **Property 28: Modes render the same data**
    - **Validates: Requirements 7.12, 7.15**

  - [ ]* 11.8 Write property test for mode switching preserving Session_State
    - **Property 29: Mode switching preserves Session_State**
    - **Validates: Requirements 7.14**

  - [ ]* 11.9 Write property test for focus links
    - **Property 30: Focus link opens the same item**
    - **Validates: Requirements 7.17**

  - [ ]* 11.10 Write Streamlit AppTest tests
    - Persona options and custom form fields; Friendly_Mode is the default; courtroom scene shows four agents; simulation banner and guidance-only statement in both modes; Advanced_Mode shows Exhibits, rule table, sensitivity results, trace, and JSON export; error keeps inputs; missing-field prompt; mode switch during a session keeps state
    - _Requirements: 7.1, 7.2, 7.3, 7.8, 7.10, 7.13, 7.14, 7.16, 7.18, 7.20, 7.21_

  - [ ]* 11.11 Write test that the UI has no action controls
    - Walk the AppTest element tree and assert only allowed widget kinds exist; assert UI modules import no brokerage or bank client and no callback creates an order object
    - _Requirements: 7.19, 13.2, 13.4_

- [ ] 12. AWS configuration templates, guidance-only scan, and deliverable files
  - [ ] 12.1 Create `deploy/` templates for the Guardrail and least-privilege IAM policies
    - Guardrail denied topics: real-trade instructions, instructions or simulated execution of any order, transfer, or brokerage or bank action, personalized financial advice, return predictions
    - IAM: `bedrock:InvokeModel` and `bedrock:ApplyGuardrail` scoped to ARNs; `s3:GetObject` on the data prefix; AgentCore Memory on one resource; trace write; no brokerage or bank permissions
    - _Requirements: 5.7, 8.2, 8.9, 13.5_

  - [ ] 12.2 Create `docs/data_sources.md`, `README.md`, technical doc, one-page summary, and demo script
    - Data-source entries (origin, retrieval date, processing, limitations, terms); dependencies, configuration, run and reproduction steps
    - Technical doc with worked example linking a conclusion to Exhibits and Trace entries; demo script with Robert and Amira; simulation, no-advice, no-prediction statements in README and summary
    - State the Guidance_Only_Rule (the system only guides and never performs an action, holds no credentials) in the README, technical documentation, and one-page summary
    - _Requirements: 3.10, 3.11, 11.1, 11.2, 11.3, 11.4, 11.5, 13.10_

  - [ ] 12.3 Create the static scanner `guide/guidance_scan.py`
    - Scan source and configuration text for brokerage or bank API client imports and credential patterns from a configured pattern list; return findings
    - _Requirements: 13.2, 13.3, 13.4, 13.9_

  - [ ]* 12.4 Write property test for the static scanner
    - **Property 26: Static scan detects credentials and brokerage or bank clients**
    - **Validates: Requirements 13.2, 13.3, 13.4, 13.9**

  - [ ]* 12.5 Write `tests/test_guidance_scan.py` repository scan and documentation check
    - Run the scanner over the repository source and configuration and assert no findings; assert README, technical documentation, and one-page summary contain the Guidance_Only_Rule statement
    - _Requirements: 13.9, 13.10_

  - [ ]* 12.6 Write Guardrail integration test against real AWS
    - Guardrail blocks a trade instruction, an order, transfer, or brokerage or bank action, a return prediction, and personalized advice
    - _Requirements: 5.7, 5.8, 13.5_

- [ ] 13. Companion_Extension (optional stretch)
  - [ ]* 13.1 Create `companion/sim_brokerage/` simulated brokerage page
    - Static local page with a ticker field and a position-size field and an inert mock order area; no account data, credentials, or real institution link
    - _Requirements: 14.4, 14.6_

  - [ ]* 13.2 Create `companion/extension/` manifest, content script, and side panel
    - Manifest `matches` lists only the simulated page origin; script reads only the ticker and size input values by element id, never other fields, cookies, or storage, and never modifies the page DOM outside its own side panel
    - Side panel shows the Verdict, plain-language summary, link to the full Tribunal_Session, and the simulation and user-acts-personally banner; shows a message naming a missing value and sends no request
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9_

  - [ ]* 13.3 Create `companion/api.py` local FastAPI app
    - Bind to `127.0.0.1`; `POST /guidance` with `GuidanceRequest` (ticker, size; extra fields rejected) and `GuidanceResponse` (verdict, summary of at most 60 words, session_url, banner); CORS limited to the simulated page origin
    - `parse_companion_input` reuses `parse_request`; return HTTP 422 naming missing values and run no session
    - _Requirements: 14.2, 14.3, 14.6, 14.7, 14.8, 14.9_

  - [ ]* 13.4 Write property test for companion input limits
    - **Property 31: Companion input is limited to ticker and size**
    - **Validates: Requirements 14.2, 14.6**

  - [ ]* 13.5 Write property test for companion response completeness
    - **Property 32: Companion response completeness**
    - **Validates: Requirements 14.3, 14.7, 14.8**

  - [ ]* 13.6 Write companion unit and browser tests
    - Manifest `matches` contains only the simulated origin; API returns 422 and runs no session for a missing size; simulated page DOM outside the side panel is identical before and after the extension runs (headless browser)
    - _Requirements: 14.4, 14.5, 14.9_

- [ ] 14. Alerts (optional stretch)
  - [ ]* 14.1 Create `alerts/engine.py` with `MarketEvent` and `detect_market_events`
    - Pure function using only observations on or before `as_of`; single-day move and portfolio drawdown thresholds read from `config.yaml`
    - _Requirements: 15.1, 15.5_

  - [ ]* 14.2 Implement `Alert` and `build_alerts` in `alerts/engine.py`
    - Keep only events affecting held assets of the Simulated_Portfolio; create the quantifying Exhibit; add guidance, simulation, and not-personalized-advice labels, the Dataset-basis statement, and a Tribunal_Session link; record each Alert in the Trace with its Exhibit number
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

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP. All Companion_Extension (13.x), Alerts (14.x), and Flight Simulator (15.x) sub-tasks are optional; the top-level tasks 13, 14, and 15 are groupings only.
- Property 15 is tested in 8.5 because it needs the Judge agent. Property 25 is tested in 8.6 because it needs the Clerk template.
- The guidance-only constraint is covered in four layers: Guardrail denied topics (6.2, 12.1, 12.6), the Judge check (7.8, 8.2, 9.5), the static scan (12.3 to 12.5), and the UI without action controls (11.5, 11.11).
- Each task references specific requirements for traceability.
- Property tests validate universal correctness properties; unit and scenario tests cover specific examples.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1", "3.1", "3.3", "6.1", "7.1", "7.8", "9.1", "12.1", "12.3"] },
    { "id": 2, "tasks": ["2.2", "2.4", "3.2", "3.4", "3.5", "3.6", "4.1", "6.2", "6.4", "7.2", "7.3", "7.11", "12.4"] },
    { "id": 3, "tasks": ["2.3", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "6.3", "7.4", "7.5", "14.1"] },
    { "id": 4, "tasks": ["7.6", "7.7", "7.9", "8.1", "8.2", "13.1", "14.2", "14.3"] },
    { "id": 5, "tasks": ["7.10", "8.3", "8.5", "11.1", "11.2", "13.2", "14.4", "14.5"] },
    { "id": 6, "tasks": ["8.4", "8.6", "9.2", "11.3", "11.4", "11.8"] },
    { "id": 7, "tasks": ["9.3", "9.4", "9.5", "11.5", "11.6", "11.7", "11.9", "13.3"] },
    { "id": 8, "tasks": ["11.10", "11.11", "12.2", "12.6", "13.4", "13.5", "13.6"] },
    { "id": 9, "tasks": ["14.6"] },
    { "id": 10, "tasks": ["12.5", "14.7"] },
    { "id": 11, "tasks": ["15.1"] },
    { "id": 12, "tasks": ["15.2", "15.3", "15.4"] },
    { "id": 13, "tasks": ["15.5", "15.6"] }
  ]
}
```
