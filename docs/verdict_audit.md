# VERDICT: product audit and compliance matrix (2026-11-15, evening)

Everything below is measured from the repository or from live sessions; where something was not measured or not done, it says so.

## 1. Submission flow and click count

The main form is: investor profile (remembered on the device) → **Stock or ETF** (searchable) → **Portfolio allocation (%)** → **Enter the Tribunal**. The selection is turned into the sentence the deterministic request parser reads (`guide/tribunal/request_parser.py`); no model call parses the request.

| Path, returning investor (profile remembered) | Clicks | How it was measured |
|---|---|---|
| Type "tes", click Tesla, type 30, click Enter the Tribunal | **2** | headless Chrome (Playwright) on the built app; also `App.test.tsx` |
| Type "royal", Enter, type 10, Enter (keyboard only) | **0** | headless Chrome, desktop 1280 px and phone 375 px |

The public site needs no account: a first-time visitor lands on this form with Robert preselected, so the same 2 clicks (or 0) apply on a first visit (measured in headless Chrome with empty storage). If no profile can be loaded the button stays disabled and the form says why; no limits are assumed.

## 2. Security coverage

| Question | Answer | Evidence |
|---|---|---|
| Searchable securities | 31 | `frontend/src/universe.ts`, kept equal to `data/assets_universe.csv` by `tests/test_frontend_universe.py` |
| Analysable securities | 31 (the same 31) | `docs/data_quality_report.md`: 31 of 31 pass every blocking check |
| Markets | TSX (13), NASDAQ (8), NYSE (4), NYSE Arca (3), Cboe BZX (1), crypto (2) | asset list |
| Asset classes | 20 stocks, 4 equity ETFs, 4 bond ETFs, 1 gold ETF, 2 crypto assets | asset list |
| Is the list hardcoded? | It is the organizers' starter dataset, pinned as a versioned snapshot; the web list is generated from it | `data/sources_metadata.csv` |
| Price provider | Yahoo Finance via yfinance (organizers' download), retrieved 2026-11-13 | `data/sources_metadata.csv` |
| Update frequency | None: one snapshot, 2021-11-12 to 2026-11-12 | snapshot `20261115T154221Z-esg` |

Searchable and analysable are deliberately the same set. A query outside it ("SpaceX", an index, any other ticker) returns no suggestion and a sentence explaining that a ruling needs validated price history. **Not done:** the universe was not widened. Adding securities means a new price download, a new snapshot and a re-run of the benchmark, which was not possible to verify before the deadline; widening search alone would have offered securities the toolkit cannot analyse.

Search matches names, tickers (with or without the exchange suffix), and a short alias list (e.g. "rbc", "google", "s&p 500"), case-insensitively, and shows name, ticker, exchange, currency and instrument type.

## 3. Financial data

Sources, processing, limits and terms for every table are in `docs/data_sources.md`. Summary:

| Data | Source | In the dataset | Used for |
|---|---|---|---|
| Daily prices, adjusted close | Yahoo Finance (yfinance) | yes | every return, volatility, drawdown and correlation |
| Dividends and splits | Yahoo Finance | yes | reference; returns use the adjusted close |
| USD/CAD | Bank of Canada Valet (FXUSDCAD) | yes | conversion of USD assets to CAD; last rate carried over non-business days |
| Policy rates, yields, CPI | Bank of Canada Valet, FRED | yes | context only, with a publication lag |
| ESG exclusions | fossil-fuel screen compiled for this project | yes (3 companies) | one Hard_Rule |
| Recent news | AgentCore Web Search | live, per session | context Exhibits only, never a calculation |
| Benchmarks, fundamentals, ESG scores | none | no | not offered; the toolkit says so when asked |

New in this change: `scripts/data_quality_audit.py`, a deterministic audit (missing or non-positive prices, duplicate dates, gaps, currency against the asset list, stale series, short history, one-day moves above 25%, USD days without a Bank of Canada rate). Result on the committed data: 31 of 31 pass, 0 duplicates, 0 bad prices, 0 gaps above 7 days, 0 moves above 25%. It runs in the test suite (`tests/test_data_quality_audit.py`) and exits non-zero on a blocking finding. **Limit:** it audits the files before ingestion; it is not yet called inside the runtime on each session.

Known limits already disclosed to the user in each ruling: survivorship bias (the 31 assets all exist today), a five-year window, the CNQ.TO adjusted-close anomaly of 2022-08-22.

Provenance per Exhibit (snapshot id, source files, period, currency, inputs, processing notes, retrieval time) is stored with the Exhibit and shown under "View technical details".

## 4. Tokens, calls and latency

Measured on live sessions with Bedrock `usage` recorded per call (PR #47) and prompt caching (PR #51):

| Measure | Value | Source |
|---|---|---|
| Model calls per hearing | 4 (Defense 2, Prosecutor 1, Judge 1) | trace of a Robert / 30% TSLA session, runtime v24 |
| Calls made by code instead of a model | request parsing, all metrics, all Hard_Rules, maximum lawful size, sensitivity, citation check, Clerk record | code |
| Tokens per hearing | 45,597 | same session |
| Read back from the prompt cache | 7,341 (Defense's second call) | same session |
| End-to-end latency | 73 s median (52 to 78) over 30 runs; 70 s and 57 s on tonight's two live runs | `docs/benchmark.md`; deployment log |
| Appeal | one more full hearing (57 s tonight) | deployment log |

**Not measured or not done:** tokens split per agent across the 30-case benchmark, dollar cost (the per-token price of the deployed model was not checked), and a before/after comparison of a leaner context. Evidence is recomputed on an appeal rather than reused. These are the next efficiency steps; none was shipped tonight because each needs a runtime redeployment and a benchmark re-run to prove verdicts are unchanged. Token efficiency is not one of the six published criteria; it supports criteria 2 and 5.

## 5. Reliability (unchanged by this work)

From `docs/benchmark.md` (30 live runs): 30/30 expected verdict classes, 30/30 decided by the Judge, 25/25 proposed sizes within the code-computed maximum, 0 numbers without evidence, verdict class stable across 5 runs per case. The runtime, rules and citation validator were not modified by this change.

## 6. Requirements matrix

Source for criteria and weights: the official brief, `data/context.md` (lines 117 to 122). The full grid is reserved for the jury, so "expected" below is our reading of the brief, not the jury's wording.

| Criterion (weight) | Expected | Status | Evidence | Remaining gap |
|---|---|---|---|---|
| 1. Quality, relevance, innovation (20%) | A useful, original answer to "should I make this investment" | Met | adversarial hearing, code-enforced contract, appeal; benchmark 30/30 vs 5/30 for a single agent | alternative assets for high-risk profiles (#4) |
| 2. Agentic intelligence and explainability (20%) | Several agents with distinct roles; conclusions traceable | Met | three model agents with separate tools, code Bailiff and Clerk, Exhibit registry, citation validator, downloadable trace | written explainability walk-through for the technical document (Monday) |
| 3. Data analysis and processing (20%) | Sound use of the dataset, sources documented | Met | `docs/data_sources.md`, data-quality report, provenance per Exhibit | universe limited to the 31 starter assets; audit not yet run inside the runtime |
| 4. UX/UI (10%) | Clear, pleasant interface | Met | two-click submission, light design system, courtroom, Exhibit cards, phone layout checked at 375 px | French labels (#23); full WCAG 2.2 AA audit not performed (contrast of the main text and focus rings checked only) |
| 5. AWS integration (15%, eligibility) | Real use of AWS services | Met | AgentCore Runtime, Memory and Web Search, Bedrock with Guardrails, Lambda and API Gateway, Cognito, Amplify, S3 snapshots, DynamoDB, Polly, CloudWatch dashboard and Transaction Search; `docs/deployment_log.md` | exported sessions for Replay before accounts close Monday 13:59 |
| 6. Presentation, business value (15%) | Video, technical document, one-pager | In progress | video script written | video, technical document and one-pager due Monday 14:00 |

Mandatory in the brief: AWS integration (eligibility), the deliverables and their deadlines, documented data sources, and that the tool gives guidance rather than executing transactions. Everything else in this table is our own target.

## 7. Design system

Tokens live at the top of `frontend/src/styles/theme.css`: warm ivory page (`#f6f2e9`), near-white surfaces, charcoal text (`#1f2421`), one green accent (`#1f5c45`), and three meaning colours (pass, warning, fail) each with a tint and a line. Type is IBM Plex Sans for text, IBM Plex Serif for the wordmark, page titles and the verdict, IBM Plex Mono for technical values; numerals are tabular everywhere. The courtroom is the only dark surface and has its own scoped tokens. Removed: background gradients, glows, blurred glass panels, gradient buttons, emoji icons beside headings. Role names on screen are Defense and Prosecutor; the runtime and trace keep `advocate` and `investigator`, and Advanced mode shows the raw text.
