# Requirements Document

## Introduction

The Agentic Investment Guide is a simulation-only, self-explaining multi-agent system built for the AlphaForge AI datathon 2026. It helps a fictional investor judge a concrete investment request (for example, Robert's "I want to put 30% in TSLA") against an explicit investor contract.

The MVP is the Decision Tribunal. Code builds the Investor_Contract, computes every number as a numbered Exhibit, and decides every Hard_Rule. Three agents then run once each, in a fixed order set by code: the Advocate Agent finds the goal behind the request and proposes up to three options, the Investigator Agent states which risks of each option are material for this investor, and the Judge Agent weighs the Soft_Preferences, compares the options, and writes the verdict narrative. A code template (the Clerk) assembles the Ruling and the answer to "What would change the verdict?" (Requirement 36).

The Guide_System is a guidance website. It only guides: it never performs an action directly or indirectly, never places, routes, prefills, or triggers orders, transfers, or brokerage or bank actions, and never holds brokerage or bank credentials. The MVP is a web application, a single-page UI hosted on AWS Amplify Hosting with Amazon Cognito sign-in, that calls a Session_API in front of the Python agents running on Amazon Bedrock AgentCore Runtime. It offers profile-based guidance in two modes: a Friendly_Mode with a visual courtroom scene and plain-language summaries, and an Advanced_Mode with full detail.

The Persona_File ships three Persona_Templates (Amira, Mateo, Robert) transcribed from the Context_Document. They are default starting points, not a closed list: the user can edit their values, extend or duplicate them, or replace them with a personal profile, and the loader accepts any number of entries that satisfy a light schema. Each shipped Contract_Value states whether it is quoted from the Context_Document or is a documented team assumption, and a value edited by the user is marked as such, so the Profiler never invents persona facts.

Data architecture: Amazon S3 is the system of record for the Dataset in every environment. The Dataset is stored as immutable, dated Dataset_Snapshots (raw CSV plus partitioned Parquet) with a Snapshot_Manifest, catalogued in AWS Glue and queryable with Amazon Athena. A Local_Cache avoids repeated downloads and serves as a recorded, visible fallback when S3 is unreachable. Dataset_Snapshots come only from the starter data provided by the organizers and from documented additions whose terms of use permit use in this project and redistribution within the project bucket; a source limited to personal use is never added. The starter prices originate from Yahoo Finance through the yfinance library and are used under the datathon permission recorded in sources_metadata.csv; the team downloads no new Yahoo Finance data. A Seed_Import_Job writes validated Dataset_Snapshots, and every Exhibit names the snapshot it used. The starter files were built locally by the Baseline_Build_Script `data/build_dataset.py`, which stays unchanged as the reference. An optional future S3_Build_Script `data/build_dataset_s3.py` wraps the Seed_Import_Job to rebuild a dated Dataset_Snapshot in S3 from the provided CSV files, and it downloads no data from the internet. Refreshing FX and macro series from the Bank of Canada or FRED is out of scope and remains a possible future improvement. The demo runs against the real S3 Primary_Store to show the AWS integration; a Cache_Fallback demonstration is optional and shown only as a clearly labelled scenario.

AWS architecture: users sign in with Amazon Cognito to the UI hosted on AWS Amplify Hosting. The UI calls the Session_API (Amazon API Gateway and AWS Lambda), which keeps Tribunal_Session state in Amazon DynamoDB and starts the Python orchestrator on Amazon Bedrock AgentCore Runtime. The agents call Amazon Bedrock through the Converse API with a Bedrock Guardrail, keep contracts in AgentCore Memory, and emit traces to AgentCore Observability. The Dataset stays in Amazon S3 with the AWS Glue Data Catalog and Amazon Athena. An AWS CDK (Python) application deploys the whole stack with one command, together with CloudWatch dashboards and alarms, Bedrock model invocation logging, X-Ray tracing, and an AWS Budgets cost alarm. AgentCore Gateway, AgentCore Identity, AWS WAF, a customer managed KMS key, CloudTrail data events, S3 Object Lock, and an automated snapshot pipeline (Amazon EventBridge and AWS Step Functions) are optional stretch items. The design document holds an AWS_Service_Map that marks every service as MVP or stretch.

Agent behavior is defined in versioned files: each agent has its own Instruction_File, and shared Skill_Files hold reusable rules (citing Exhibits, guidance only, data limits, plain language, persona handling). An Instruction_Loader composes the System_Prompt of each agent and computes an Instruction_Hash that the Trace records for every agent call, so an explanation can be tied to the exact instructions used.

The Flight Simulator (Flight Director, Co-pilot, Behavior Analyst) is an optional stretch. It replays history from 2021-11-12 and compares stated risk tolerance with revealed risk tolerance. One further optional stretch surface exists: Alerts that notify the user of Dataset-derived market events affecting the simulated portfolio. A browser-extension companion was considered and removed from the scope (Requirement 14 is marked Removed).

Evaluation of the ideaHedi.md concept, reflected in scope decisions:

- Strengths: separating what the investor says from what the system enforces (Investor_Contract); an Advocate that serves the investor's goal and an Investigator that names the risks material to this investor counter "yes-man AI" behavior and directly address the Robert persona; the "no exhibit, no argument" rule makes explanations verifiable; the sensitivity calculation ties explanation to computation; the AWS mapping (Bedrock Guardrails, AgentCore Memory, AgentCore Observability) covers the 15% AWS criterion.
- Risks: seven or eight agents increase cost, latency, and demo complexity, while the jury favors simple, focused, verifiable approaches. The Flight Simulator needs a replay engine, stress-event detection, and persistent memory, which is a large build. Replay requires strict look-ahead control. Language models may invent numbers unless figures come from tools. The 5-year window and the survivorship-biased universe limit the strength of any conclusion. The dataset has no ESG scores, news, or fundamentals.
- Scope decisions: the Tribunal is the MVP; the Flight Simulator is optional stretch; all numerical facts come from deterministic tools that emit numbered Exhibits; agents may only cite Exhibits; Advocate, Investigator, and Judge are three role prompts over a shared Toolkit called once each by a code orchestrator, not separate infrastructure. Data scope follows licensing: sources limited to personal use are excluded, and the persona list is a flexible template set rather than a fixed trio.

## Hackathon Delivery Tiers (scope decision, 2026-11-14)

Remaining build time is about 20 working hours: feature freeze Sunday 12:30, code and application deadline Sunday 23:59, AWS accounts closed Monday 13:59, finalist pitch Friday 2026-11-20 with no AWS account. The official grid weighs Solution 20 %, Agentic and explainability 20 %, Data 20 %, AWS 15 % (an eligibility condition: the integration must be real and each service justified; the brief explicitly discourages multiplying services to impress), Pitch 15 %, and UX 10 %. Requirements are delivered in three tiers. A Tier 3 item starts only after every Tier 1 and Tier 2 item works on the deployed URL.

| Tier | Purpose | Requirements and criteria |
| --- | --- | --- |
| Tier 1: demo-critical | What the jury sees; scores Solution, Agentic, Data, UX | 1 to 7, 9.1 to 9.6, 9.8, 10.1 to 10.9, 11, 13, 16, 21, 28 to 35 |
| Tier 2: AWS showcase, lean | Real, justified AWS integration that the demo shows | 8.1 to 8.9; 17.1 to 17.3 and 17.14 (one pinned snapshot read from S3, checksums in the manifest); 18.1 to 18.5, 18.7 to 18.9; 19.2 (row-count and duplicate checks), 19.5, 19.6, 19.8; 20.1, 20.4 to 20.7, 20.11; 22; 23.1 to 23.6; 25.3 and 25.6 (log retention and model invocation logging); 26.1 to 26.5, 26.7 |
| Tier 3: deferred | Not visible in a 5-minute demo or not scored | 8.10 to 8.14 as template assertions (least privilege itself stays, through CDK grant helpers); 9.7; 17.4 to 17.13, 17.15, 17.16 (ETag-conditional pointer, VersionId reads, Cache_Fallback); 18.6, 18.10; 19.1 scanned-bytes cutoff, 19.3, 19.4, 19.7; 20.2, 20.3, 20.8 to 20.10; 23.7 to 23.9; 24; 25.1, 25.2 as template assertions, 25.4, 25.5, 25.7 to 25.13; 26.6; 27; 10.10 to 10.20; 12; 15 |

Gates (local time, America/Montreal):

1. Saturday 23:00: `python -m guide.run_session` runs Robert "30% in TSLA" end to end on the local machine with real Bedrock calls and prints a SessionView that validates against the schema.
2. Sunday 09:00: hosting gate. IF the path Amplify, Cognito, Session_API, and Agent_Runtime does not complete one Tribunal_Session end to end, THEN the team switches to option (b) of the design (a Python UI in a container on AWS App Runner reading the same SessionView) and stops work on option (a).
3. Sunday 12:30: feature freeze. The five demo cases of Requirement 33 run on the deployed URL.
4. Sunday 20:00: the demo video is recorded on the deployed application.
5. Sunday 23:59: code, exported SessionViews, and Replay_Mode (Requirement 35) are pushed to GitHub.

## Glossary

- **Guide_System**: The complete Agentic Investment Guide application, including agents, tools, UI, and AWS integration.
- **Profiler_Agent**: The agent that converts a Persona_Template, an edited template, or a custom-profile form into an Investor_Contract. It reads templates and form values only and does not invent persona facts.
- **Investigator_Agent**: The agent that reads every option with its Risk_Panel and the Investor_Contract and states, with Exhibits, which risks are material for this investor and why. It computes nothing itself.
- **Advocate_Agent**: The agent that identifies the goal behind an Investment_Request and proposes up to three Options that serve it, citing Exhibits. It never decides whether an Option passes the Hard_Rules.
- **Judge_Agent**: The agent that weighs the Soft_Preferences, compares the verified Options using the Investigator_Agent findings, and writes the narrative of the Verdict decided by code.
- **Clerk**: The deterministic code template that writes the Ruling, the four answers of Requirement 33, and the sensitivity-based answer. It is not a language-model agent.
- **Option**: The original Investment_Request or a variant proposed by the Advocate_Agent (a position size, or another asset of the universe, as allowed by configuration), each with its Risk_Panel and Hard_Rule results computed by code.
- **Risk_Panel**: The fixed set of Exhibits that code computes for every Option: volatility, maximum drawdown, worst rolling 252-day return, 2022 return, share of variance per asset, currency exposure, sector weights, correlation of the added asset with the Base_Portfolio, and maximum weight within the contract.
- **Flight_Director_Agent**: (Stretch) The agent that runs the historical replay and pauses at Stress_Events.
- **Copilot_Agent**: (Stretch) The agent that explains a Stress_Event using only data available on the replay date.
- **Behavior_Analyst_Agent**: (Stretch) The agent that compares stated and revealed risk tolerance.
- **Investor_Contract**: A JSON document holding explicit, checkable investor rules: risk level, maximum volatility, maximum tolerated drawdown, per-asset cap, per-asset-class caps, sector caps, crypto cap, ESG exclusions, speculative-asset limit, and horizon in years, with a provenance per field.
- **Persona**: A fictional investor profile with an id, a display name, a risk level, a horizon, and Contract_Values, defined as an entry of the Persona_File. The three shipped reference Personas are Amira, Mateo, and Robert, as defined in section 3 of the Context_Document.
- **Context_Document**: The official challenge context file /workshop/Agent52/data/context.md (French); section 3 defines the three Personas.
- **Persona_File**: The file `personas.yaml` that ships the three Persona_Templates and may also hold any number of additional, edited, or duplicated Persona entries.
- **Persona_Template**: A Persona entry of the Persona_File used as a starting point. The three shipped Persona_Templates have the ids `amira`, `mateo`, and `robert` and may be edited, extended, duplicated, or replaced.
- **Custom_Profile**: A profile that the user saves after editing a Persona_Template in the form or after filling the blank form. It is identified by a profile identifier and kept in the Session_State or in AgentCore Memory.
- **Persona_Fact**: An optional fact about a Persona: age, occupation, family situation, investment experience, objective, preferences and constraints, or what the Persona tests. For the shipped Persona_Templates each Persona_Fact states the Context_Document value and a verbatim excerpt.
- **Contract_Value**: A value in a Persona entry from which the Profiler_Agent builds one Investor_Contract field.
- **Contract_Value_Basis**: The origin of a Contract_Value: `quoted` (stated in the Context_Document, with the verbatim excerpt), `assumption` (a documented team assumption, with a rationale), or `user` (a value edited or entered by the user). Basis, rationale, and excerpt are encouraged for every entry and required only in the shipped Persona_Templates.
- **Investment_Request**: A request such as "put 30% of the portfolio in TSLA", made by a Persona or custom profile.
- **Toolkit**: The set of deterministic local Python functions that read the Dataset and compute metrics.
- **Exhibit**: A numbered, immutable record produced by a Toolkit function. It contains the metric name, value, period, assets, currency, data files used, processing notes, and the Snapshot_Id and retrieval timestamp of the Dataset_Snapshot used.
- **Exhibit_Registry**: The store of all Exhibits created during one Tribunal_Session.
- **Dataset**: The tables assets_universe, prices_daily, corporate_actions, fx_usdcad_daily, and macro_rates, as stored in a Dataset_Snapshot. The baseline Dataset_Snapshot is the starter data in /workshop/Agent52/data (31 assets, 2021-11-12 to 2026-11-12), provided by the organizers: prices and corporate actions originate from Yahoo Finance through yfinance and are used under the datathon permission, and FX and macro series come from the Bank of Canada and FRED. Later Dataset_Snapshots come only from documented additions under Requirement 20.
- **Primary_Store**: The Amazon S3 bucket and prefix that is the system of record for all Dataset_Snapshots, Snapshot_Manifests, and the Current_Snapshot_Pointer.
- **Dataset_Snapshot**: An immutable, dated copy of the Dataset in the Primary_Store, identified by a Snapshot_Id and described by a Snapshot_Manifest.
- **Snapshot_Id**: The identifier of a Dataset_Snapshot, formed from the UTC retrieval timestamp and the source label (for example `20261113T000000Z-starter`).
- **Snapshot_Manifest**: The JSON document of a Dataset_Snapshot listing Snapshot_Id, source, retrieval timestamp, coverage start and end, tickers, files with S3 object version identifiers and SHA-256 checksums, row counts, carried-over tables, and validation results.
- **Current_Snapshot_Pointer**: The JSON object in the Primary_Store naming the Snapshot_Id that new Tribunal_Sessions use.
- **Local_Cache**: A local directory holding copies of Primary_Store objects, used to avoid repeated downloads and as the Cache_Fallback.
- **Cache_Fallback**: The event in which the Data_Loader serves a Dataset_Snapshot from the Local_Cache because the Primary_Store is unreachable.
- **Data_Loader**: The component that resolves, pins, downloads, verifies, caches, and reads Dataset_Snapshots for the Toolkit.
- **Snapshot_Writer**: The component that writes a Dataset_Snapshot (raw CSV, Parquet, Snapshot_Manifest) to the Primary_Store, registers it in the Data_Catalog, validates it, and updates the Current_Snapshot_Pointer.
- **Data_Catalog**: The AWS Glue Data Catalog database and tables that describe the Parquet files of all Dataset_Snapshots.
- **Athena_Workgroup**: The Amazon Athena workgroup used to query the Data_Catalog, with an enforced results location in a dedicated Athena results bucket.
- **Seed_Import_Job**: The job that writes a Dataset_Snapshot through the Snapshot_Writer from the starter files in the seed directory or from files of documented additions. Its library implementation is `guide/ingest/seed.py`. It is started from the command line, by the S3_Build_Script, or by the Snapshot_Pipeline, and it downloads no market data from the internet.
- **Universe_Additions_File**: A file listing tickers outside the starter assets_universe that the team has documented for import, with name, asset class, market, currency, sector, source name, and the CSV file holding their data.
- **Data_Source_Document**: The data-source document described in Requirement 3.10 and Requirement 20.
- **Tribunal_Session**: One run of the Profiler, the Advocate, the Investigator, the Judge, and the Clerk template on one Investment_Request.
- **Verdict**: The Judge_Agent outcome: reject, accept, or accept with conditions.
- **Ruling**: The Clerk's plain-language document with sections Facts, Assumptions, Fictional scenarios, and Limits.
- **Challenge_Rules**: The rules that all outputs be simulation only, contain no personalized financial advice, contain no return predictions, and comply with the Guidance_Only_Rule.
- **Guidance_Only_Rule**: The Datathon rule that the Guide_System may only guide and SHALL NOT perform any action directly or indirectly. Prohibited are placing, routing, prefilling, or triggering orders, transfers, or any brokerage or bank action, and holding brokerage or bank credentials.
- **Friendly_Mode**: The UI mode that shows a visual courtroom scene with the Advocate_Agent, Investigator_Agent, and Judge_Agent, the Options compared, and plain-language summaries.
- **Advanced_Mode**: The UI mode that shows full detail: Exhibits, per-rule table, Sensitivity_Analysis results, Trace, and JSON export.
- **Session_State**: The inputs, Investor_Contract, Tribunal_Session progress, Verdict, Ruling, Exhibits, and Trace of one Tribunal_Session, held in the Session_Store as a SessionView and mirrored in the browser view.
- **Alert**: (Stretch) A notification, labelled as guidance, that a Dataset-derived market event affects the simulated portfolio.
- **Market_Event**: (Stretch) An event detected from the Dataset, such as a Stress_Event or a single-day price move above a configured threshold.
- **Simulated_Portfolio**: A fictional portfolio defined by the user or Persona, used for the Flight Simulator and Alerts.
- **Sensitivity_Analysis**: A Toolkit computation that re-evaluates the Investor_Contract checks with one changed input (such as position size, horizon, or period) to find the threshold at which the Verdict changes.
- **Stress_Event**: (Stretch) A replay date on which a portfolio drawdown, rate change, or crypto decline exceeds a configured threshold.
- **Trace**: The recorded sequence of agent calls, tool calls, Exhibits, and Judge checks for a Tribunal_Session.
- **UI**: The single-page web application in the `frontend/` directory, hosted on AWS Amplify Hosting, that signs the user in through the Identity_Provider and renders the SessionView returned by the Session_API.
- **Guardrail**: An Amazon Bedrock Guardrails configuration enforcing the Challenge_Rules.
- **Instruction_File**: A Markdown file `guide/agents/instructions/<agent>.md` holding the system prompt of one agent: role, goals, allowed tools, output JSON format, forbidden behaviors, citation rule, guidance-only rule, tone, and the list of Skill_Files it includes.
- **Skill_File**: A shared, reusable Markdown file `guide/agents/skills/<skill>.md` that Instruction_Files include.
- **Instruction_Loader**: The component `agents/instructions.py` that composes the System_Prompt of an agent from its Instruction_File and the Skill_Files it lists.
- **System_Prompt**: The composed text of one Instruction_File followed by its Skill_Files, passed as the system prompt of the agent's Bedrock call.
- **Instruction_Hash**: The SHA-256 hash of the System_Prompt of an agent, recorded in the Trace for each agent call.
- **As_Of_Date**: The simulated date at which only information published on or before that date may be used.
- **SessionView**: The JSON document, validated against a JSON schema in the repository, that holds everything the UI renders for one Tribunal_Session. Friendly_Mode and Advanced_Mode read the same SessionView.
- **Session_API**: The Amazon API Gateway REST API with AWS Lambda handlers through which the UI lists Persona_Templates, saves and lists Custom_Profiles, creates and reads Tribunal_Sessions, and downloads Traces. It exposes no action operation.
- **Session_Store**: The Amazon DynamoDB table that holds the SessionView of each Tribunal_Session and each Custom_Profile, keyed by the Identity_Provider user identifier, with a time-to-live on Tribunal_Session records.
- **Agent_Runtime**: The Amazon Bedrock AgentCore Runtime deployment that runs the Tribunal_Orchestrator, the agents, and the Toolkit from one container image.
- **Application_Role**: The IAM role that the Agent_Runtime assumes, and that a developer assumes for local runs of the application.
- **Identity_Provider**: The Amazon Cognito user pool and app client that authenticate the users of the UI and issue JSON Web Tokens.
- **CDK_App**: The AWS CDK (Python) application in the repository that defines all AWS resources and synthesizes the deployment templates.
- **Snapshot_Pipeline**: (Stretch) The Amazon EventBridge rule and AWS Step Functions state machine that run the Seed_Import_Job steps when a Dataset candidate arrives under the `incoming/` prefix of the Primary_Store.
- **Baseline_Build_Script**: The existing script `/workshop/Agent52/data/build_dataset.py` that built the starter CSV files locally (prices and corporate actions through yfinance, FX from the Bank of Canada, macro series from the Bank of Canada and FRED). It stays unchanged as the reference.
- **S3_Build_Script**: (Optional, future) The new script `data/build_dataset_s3.py`, a command-line wrapper around the Seed_Import_Job that builds a dated Dataset_Snapshot in S3 from provided CSV files.
- **AWS_Service_Map**: The table in the design document that lists each AWS service, its role in the Guide_System, the requirement it serves, and whether it is MVP or stretch.

- **Base_Portfolio**: A fictional portfolio defined per Persona in the Persona_File, with weights summing to 1, into which an Investment_Request is inserted.
- **Hard_Rule**: An Investor_Contract rule with a numeric limit or an exclusion list, decided by deterministic code.
- **Soft_Preference**: A stated preference of the investor that cannot be reduced to a number (for example Robert's "entreprises établies, modèle d'affaires compréhensible"), weighed by the Judge_Agent using the Advocate_Agent goal analysis and the Investigator_Agent findings.
- **Appeal**: A rerun of a completed Tribunal_Session with exactly one changed input, displayed beside the original.
- **Precedent**: A stored summary of a completed Tribunal_Session (Persona, asset, position size, Verdict, deciding rules, Exhibit values) that later Tribunal_Sessions cite.
- **ESG_Exclusion_List**: The documented file `data/esg_exclusions.csv` that marks each universe asset as excluded or not under a cited public methodology. It is a proxy, not an ESG score.
- **Baseline_Agent**: A single Bedrock agent with one prompt, the same model and the same Investor_Contract, no Toolkit and no debate, used only as the control arm of the Benchmark.
- **Benchmark**: The repeatable evaluation of Requirement 34 that compares the Guide_System with the Baseline_Agent on fixed cases.
- **Confidence_Label**: One of `Measured` (repeated runs, automatic check), `Indicative` (measured, too few runs to prove the difference), or `Context` (no measurement), attached to each Benchmark result.
- **Replay_Mode**: A UI mode that renders exported SessionViews from static JSON files without calling the Session_API, Bedrock, or any AWS service.

## Requirements

### Requirement 1: Investor Contract Creation

**User Story:** As an investor, I want my goals translated into explicit rules, so that the system enforces what I need rather than only what I say.

#### Acceptance Criteria

1. WHEN a Persona_Template or Custom_Profile is selected, THE Profiler_Agent SHALL produce from its Contract_Values an Investor_Contract in JSON containing risk level, horizon in years, maximum volatility, maximum tolerated drawdown, per-asset cap, per-asset-class caps, crypto cap, sector caps, ESG exclusions, and speculative-asset limit.
2. WHEN a custom-profile form is submitted, THE Profiler_Agent SHALL produce an Investor_Contract from the submitted values, whether the form was pre-filled from a Persona_Template or filled from blank.
3. THE Guide_System SHALL validate each Investor_Contract against a JSON schema before any other agent uses the Investor_Contract.
4. IF an Investor_Contract fails schema validation, THEN THE Guide_System SHALL display the failing fields and withhold the Tribunal_Session from starting.
5. THE Profiler_Agent SHALL record for each contract field a provenance of `persona_quoted`, `persona_assumption`, `user`, `form`, or `default`.
6. WHERE the shipped Amira Persona_Template is used with its default values, THE Profiler_Agent SHALL set a crypto per-asset-class cap below 100 percent and an Information Technology sector cap below 100 percent of the portfolio.
7. WHERE the shipped Mateo Persona_Template is used with its default values, THE Profiler_Agent SHALL include at least one ESG exclusion and a speculative-asset limit below 100 percent of the portfolio in the Investor_Contract.
8. WHERE the shipped Robert Persona_Template is used with its default values, THE Profiler_Agent SHALL set a horizon between 3 and 5 years inclusive and a crypto cap lower than the crypto caps of the shipped Amira and Mateo Persona_Templates.
9. THE Investor_Contract SHALL express the risk level as one of `low`, `low_to_moderate`, `moderate`, or `high`.
10. WHERE a horizon is given as a range, THE Profiler_Agent SHALL set `horizon_years` to the lower bound of the range and SHALL keep the range in the Investor_Contract, and WHERE a horizon is given as a single value, THE Profiler_Agent SHALL use that value.
11. IF an Investor_Contract has been edited by the user, THEN THE Guide_System SHALL validate the edited Investor_Contract only against the generic JSON schema of Requirement 1.3 and SHALL apply no Persona-specific rule of Requirements 1.6 to 1.8.

### Requirement 2: Deterministic Toolkit and Exhibits

**User Story:** As a juror, I want every number traceable to a computation, so that I can verify what supports a conclusion.

#### Acceptance Criteria

1. THE Toolkit SHALL provide deterministic Python functions for annualized return, annualized volatility, maximum drawdown with peak and trough dates, correlation between two assets, drawdown during a named period, and portfolio-level metrics for a weighted position.
2. WHEN a Toolkit function is called, THE Guide_System SHALL create an Exhibit with a sequential number, metric name, value, period start, period end, assets, currency, source files, processing notes, Snapshot_Id, and snapshot retrieval timestamp, and store the Exhibit in the Exhibit_Registry.
3. THE Guide_System SHALL make each Exhibit immutable after creation.
4. WHEN the same Toolkit function is called with identical inputs on the same Dataset_Snapshot, THE Toolkit SHALL return an identical value, whether the Dataset_Snapshot was read from the Primary_Store or from the Local_Cache.
5. THE Toolkit SHALL compute returns from the adj_close column of the prices_daily table.
6. IF a Toolkit function is called with a ticker absent from the assets_universe table of the pinned Dataset_Snapshot, THEN THE Toolkit SHALL return an error naming the ticker and SHALL create no Exhibit.
7. IF a requested period contains fewer than 20 price observations for an asset, THEN THE Toolkit SHALL return an insufficient-data error and SHALL create no Exhibit.
8. THE Toolkit SHALL expose each function to the agents as a Bedrock Converse API tool with a JSON input schema.

### Requirement 3: Data Handling and Quality

**User Story:** As a data reviewer, I want the data used correctly and its limits stated, so that conclusions are not misleading.

#### Acceptance Criteria

1. WHEN a Toolkit function computes a metric for an asset quoted in USD, THE Toolkit SHALL convert the prices to CAD using the fx_usdcad_daily table of the pinned Dataset_Snapshot and SHALL record the conversion in the Exhibit processing notes.
2. IF an FX rate is missing for a date, THEN THE Toolkit SHALL use the most recent earlier rate and SHALL record the carry-forward in the Exhibit processing notes.
3. WHEN a Toolkit function compares assets with different trading calendars, THE Toolkit SHALL align them on the dates on which all compared assets have a price and SHALL record the alignment method and the resulting observation count in the Exhibit.
4. WHEN a Toolkit function uses a monthly macro series, THE Toolkit SHALL treat the value as available only after the reference month plus a configured publication lag in days.
5. THE Guide_System SHALL define the publication lag for each macro series in a configuration file.
6. WHEN a Toolkit function is called with an As_Of_Date, THE Toolkit SHALL exclude every price and macro observation dated after the As_Of_Date.
7. WHEN an Exhibit involves CNQ.TO and its period includes 2022-08-22, THE Guide_System SHALL attach a note stating that the 1.021 split factor likely reflects a special distribution and is unverified.
8. WHEN an Exhibit includes a result derived from the Dataset, THE Guide_System SHALL attach the survivorship-bias limitation to the Ruling.
9. IF a request depends on ESG scores, news, or company fundamentals, THEN THE Guide_System SHALL report that the Dataset does not contain this information and SHALL label any related argument as unsupported by Exhibits; the documented ESG_Exclusion_List of Requirement 32 is a cited proxy and is not an ESG score.
10. THE Guide_System SHALL maintain a Data_Source_Document listing, for each source, its origin, retrieval date, processing (including the CSV to Parquet conversion and the Dataset_Snapshot layout), limitations, terms of use, and whether the terms permit use in this project.
11. WHERE external data is added to the Dataset, THE Guide_System SHALL add an entry for that data to the Data_Source_Document before any Exhibit uses the data.
12. IF no FX rate exists on or before a date for which a USD price must be converted, THEN THE Toolkit SHALL exclude that date from the computation and SHALL record the excluded dates in the Exhibit processing notes.

### Requirement 4: Advocate Options and Investigator Findings

**User Story:** As an investor, I want my real goal served and the risks that matter to me named, so that I receive more than agreement or a plain refusal.

#### Acceptance Criteria

1. WHEN a Tribunal_Session starts and the Risk_Panel and Hard_Rule results of the Investment_Request exist, THE Advocate_Agent SHALL state the goal behind the request and propose at most three Options, at least one of which reduces the largest exposure shown in the Risk_Panel of the request.
2. THE Advocate_Agent SHALL propose Options only as requests the user may test and SHALL never phrase an Option as an instruction or recommendation to buy or sell.
3. WHEN the Advocate_Agent has proposed its Options, THE Guide_System SHALL compute the Risk_Panel and the Hard_Rule results of every Option with code and SHALL mark each Option that fails a Hard_Rule as rejected, keeping it visible.
4. WHEN the Risk_Panels of all Options exist, THE Investigator_Agent SHALL list, for each Option, the material risks for this investor, each with the cited Exhibit and the Investor_Contract field or Soft_Preference that makes it material.
5. THE Guide_System SHALL reject any Advocate_Agent or Investigator_Agent claim that cites no Exhibit, cites an Exhibit number absent from the Exhibit_Registry, or (for the Investigator_Agent) names no existing Investor_Contract field or Soft_Preference.
6. WHEN a claim is rejected, THE Guide_System SHALL return it to the originating agent for revision, up to 2 revision attempts, and THEN SHALL remove the claim and record the removal in the Trace.
7. THE Guide_System SHALL verify that every number in an agent output equals the value of the cited Exhibit after rounding the Exhibit value to the number of decimals stated in the output.
8. THE Advocate_Agent and THE Investigator_Agent SHALL use the same Toolkit and the same Exhibit_Registry, and each SHALL make at most 6 Toolkit calls per Tribunal_Session.
9. WHERE configuration sets `advocate_scope` to `size_only`, THE Advocate_Agent SHALL propose only smaller position sizes of the requested asset; WHERE it is `universe`, it MAY propose other assets of the assets_universe table.

### Requirement 5: Judge and Governance

**User Story:** As an investor, I want a governance check against my own contract and the challenge rules, so that results are consistent and safe.

#### Acceptance Criteria

1. WHEN the Investigator_Agent findings are complete, THE Judge_Agent SHALL evaluate the Investment_Request against each Investor_Contract rule using Exhibit values and SHALL record a pass or fail result per rule.
2. THE Judge_Agent SHALL issue a Verdict of reject, accept, or accept with conditions.
3. WHEN the Verdict is accept with conditions, THE Judge_Agent SHALL state each condition as a numeric limit, such as a maximum position size in percent.
4. IF any Investor_Contract rule fails and no numeric condition can satisfy every failed rule, THEN THE Judge_Agent SHALL issue a Verdict of reject.
5. THE Judge_Agent SHALL make no call to another agent; IF evidence for a rule is missing, THEN THE Guide_System SHALL compute it with the Toolkit before the Judge_Agent runs.
6. IF evidence for a rule cannot be computed, THEN THE Judge_Agent SHALL list the rule as unverified in the Verdict.
7. THE Guide_System SHALL apply a Guardrail to every model input and output that blocks real-trade instructions, personalized financial advice, return predictions, and any output that violates the Guidance_Only_Rule.
8. IF the Guardrail blocks a model output, THEN THE Guide_System SHALL record the block in the Trace and display a message stating which Challenge_Rule applied.
9. THE Judge_Agent SHALL compute the pass or fail result of each Hard_Rule with deterministic code. THE Judge_Agent SHALL use the language model only to weigh Soft_Preferences as specified in Requirement 29 and to write the narrative of the Verdict, and a Soft_Preference judgment SHALL never turn a failed Hard_Rule into a pass.
10. WHEN the Investor_Contract has a risk level of `low_to_moderate` and the Investment_Request exceeds a per-asset cap, THE Judge_Agent SHALL state the tension between the request and the Investor_Contract in the Verdict.
11. WHEN the Judge_Agent evaluates arguments, THE Guide_System SHALL check each Advocate_Agent, Investigator_Agent, and Judge_Agent output and the Clerk Ruling against the Guidance_Only_Rule and SHALL record a pass or fail result in the Trace.
12. IF an agent output fails the Guidance_Only_Rule check, THEN THE Judge_Agent SHALL remove the offending statement from the Ruling and SHALL record the removal in the Trace.

### Requirement 6: Clerk Ruling and Sensitivity

**User Story:** As an investor, I want a plain-language ruling that shows what would change the outcome, so that I understand the decision and its limits.

#### Acceptance Criteria

1. WHEN the Judge_Agent issues a Verdict, THE Clerk SHALL produce a Ruling with the sections Facts, Assumptions, Fictional scenarios, and Limits.
2. THE Clerk SHALL cite an Exhibit number for each statement in the Facts section.
3. THE Clerk SHALL list in the Assumptions section the period, currency, calendar alignment choice, pinned Snapshot_Id with its retrieval date, and each Investor_Contract field with `persona_assumption` or `default` provenance used by a rule check.
4. THE Clerk SHALL label each hypothetical item in the Fictional scenarios section as a simulation.
5. THE Ruling SHALL include a section titled "What would change the verdict" containing at least one Sensitivity_Analysis result.
6. WHEN the Ruling is produced, THE Toolkit SHALL run the Sensitivity_Analysis by re-evaluating the Investor_Contract rules with position size and horizon varied over the ranges and step sizes defined in configuration and with the 2022 drawdown period, and SHALL store each result as an Exhibit.
7. THE Ruling SHALL state the threshold value at which the Verdict changes for each varied input, or state that no change occurs within the tested range.
8. THE Ruling SHALL include the statements that the output is a simulation, is not personalized financial advice, and does not predict future returns.
9. THE Ruling SHALL present volatility as one risk indicator and SHALL reference at least one further factor from horizon, diversification, or stated preferences.

### Requirement 7: Web User Interface

**User Story:** As an investor or juror, I want an interface that is friendly to follow and detailed to verify, so that I can understand a Tribunal_Session at a glance and inspect the evidence in depth.

#### Acceptance Criteria

1. THE UI SHALL provide a persona picker that lists every valid Persona_Template read from the Persona_File, including the shipped Amira, Mateo, and Robert, and every saved Custom_Profile.
2. THE UI SHALL provide a custom-profile form with fields for risk level, horizon in years (a single value or a range), maximum volatility, maximum drawdown, per-asset cap, crypto cap, and ESG exclusions, and WHEN the user picks a Persona_Template, THE UI SHALL pre-fill the form from that Persona_Template so that the user can edit the values.
3. THE UI SHALL provide a request box that accepts a free-text Investment_Request.
4. WHEN the user submits an Investment_Request, THE UI SHALL start a Tribunal_Session through the Session_API and display progress for each agent stage as the Session_Store reports it.
5. WHEN a Tribunal_Session completes, THE UI SHALL display the Verdict, the Ruling, and the per-rule pass or fail table.
6. THE UI SHALL render each Exhibit citation in the Ruling and arguments as a clickable element that opens the Exhibit details.
7. THE UI SHALL provide a trace panel showing the ordered agent calls, tool calls, Exhibits created, Judge checks, and Guardrail blocks of the Tribunal_Session.
8. THE UI SHALL display a persistent banner stating that the output is a simulation and not financial advice.
9. THE UI SHALL provide a Friendly_Mode and an Advanced_Mode and SHALL offer a control to switch between them.
10. WHILE the UI is in Friendly_Mode, THE UI SHALL display a courtroom scene showing the Advocate_Agent, Investigator_Agent, and Judge_Agent, and a table of the Options with their Hard_Rule results and material risks.
11. WHILE the UI is in Friendly_Mode, WHEN an agent stage produces output, THE UI SHALL highlight that agent in the courtroom scene and display a plain-language summary of the output of at most 60 words.
12. WHILE the UI is in Friendly_Mode, THE UI SHALL display the Verdict and the answer to "What would change the verdict" in plain language, with each statement linked to its Exhibit.
13. WHILE the UI is in Advanced_Mode, THE UI SHALL display the Exhibits, the per-rule pass or fail table, the Sensitivity_Analysis results, the trace panel, and a control to export the Trace as JSON.
14. WHEN the user switches between Friendly_Mode and Advanced_Mode during a Tribunal_Session, THE UI SHALL preserve the Session_State, including a running Tribunal_Session, without restarting or discarding it.
15. THE UI SHALL use the same Exhibits, Verdict, and Ruling data in Friendly_Mode and Advanced_Mode.
16. THE UI SHALL set Friendly_Mode as the default mode at the start of a session.
17. THE UI SHALL provide in Friendly_Mode a control that opens the Advanced_Mode view of the same Exhibit, rule, or Trace entry.
18. THE UI SHALL display in both modes a statement that the Guide_System only provides guidance and that the user acts personally outside the Guide_System.
19. THE UI SHALL contain no control that places, routes, prefills, or triggers an order, transfer, or brokerage or bank action.
20. IF a Tribunal_Session fails, THEN THE UI SHALL display the failing stage and an error message and SHALL keep the previously entered inputs.
21. IF an Investment_Request cannot be parsed into an asset and a position size, THEN THE UI SHALL ask the user for the missing asset or position size.
22. THE UI SHALL display in Friendly_Mode and Advanced_Mode the pinned Snapshot_Id, its source, and its retrieval timestamp for the current Tribunal_Session.
23. WHEN the user saves the edited form as a Custom_Profile, THE UI SHALL keep the Custom_Profile in the Session_State and, WHERE AgentCore Memory is enabled, THE Guide_System SHALL store the Custom_Profile in AgentCore Memory keyed by its profile identifier, and THE UI SHALL list the Custom_Profile in the persona picker.

### Requirement 8: AWS Integration

**User Story:** As a datathon team, I want a solid AWS integration, so that the solution scores on the AWS criterion and runs in a deployable form.

#### Acceptance Criteria

1. THE Guide_System SHALL invoke every agent through the Amazon Bedrock Converse API with tool use.
2. THE Guide_System SHALL apply an Amazon Bedrock Guardrail configuration to model calls.
3. THE Guide_System SHALL emit Traces to AgentCore Observability for each Tribunal_Session.
4. THE Guide_System SHALL store the Investor_Contract and session summaries in AgentCore Memory, keyed by a profile identifier.
5. THE Guide_System SHALL use the Primary_Store (Amazon S3) as the system of record for the Dataset in every environment, local and deployed, as specified in Requirement 17.
6. THE Guide_System SHALL use the Local_Cache only to avoid repeated downloads of Primary_Store objects and as the Cache_Fallback specified in Requirement 17.
7. THE Guide_System SHALL read AWS region, model identifier, Guardrail identifier, Primary_Store bucket and prefix, Local_Cache directory, S3 timeout and retry count, Data_Catalog database name, Athena_Workgroup name, and Athena results location from configuration, and SHALL contain no credentials in source code or logs.
8. IF a Bedrock call fails with a throttling error, THEN THE Guide_System SHALL retry up to 3 times with exponential backoff before reporting a stage failure.
9. THE Guide_System SHALL grant each AWS component only the permissions needed for its function.
10. THE deployment templates SHALL grant the Application_Role only s3:GetObject and s3:GetObjectVersion on the Dataset prefixes and the Current_Snapshot_Pointer of the Primary_Store, and no S3 write permission.
11. THE deployment templates SHALL grant the Seed_Import_Job role only s3:GetObject, s3:GetObjectVersion, and s3:PutObject on the snapshot, curated, and pointer prefixes of the Primary_Store, glue:GetTable and glue:BatchCreatePartition on the Data_Catalog tables, and the Athena permissions of the Athena query role.
12. THE deployment templates SHALL grant the Athena query role only athena:StartQueryExecution, athena:GetQueryExecution, and athena:GetQueryResults on the Athena_Workgroup, glue:GetDatabase, glue:GetTable, and glue:GetPartitions on the Data_Catalog, s3:GetObject and s3:ListBucket on the curated prefix, and s3:GetObject, s3:PutObject, and s3:GetBucketLocation on the Athena results bucket prefix.
13. THE Primary_Store bucket policy SHALL deny s3:DeleteObject and s3:DeleteObjectVersion on the snapshot and curated prefixes to every principal.
14. THE deployment templates SHALL enable S3 versioning, default encryption, and public access blocking on the Primary_Store bucket, and default encryption and public access blocking on the Athena results bucket.

### Requirement 9: Observability and Explainability Traces

**User Story:** As a juror, I want an inspectable court record, so that I can verify that explanations match observed actions.

#### Acceptance Criteria

1. THE Guide_System SHALL record in the Trace each agent invocation, with agent name, input summary, output summary, and timestamp.
2. THE Guide_System SHALL record in the Trace each Toolkit call with its arguments and the resulting Exhibit number.
3. THE Guide_System SHALL record in the Trace each Judge rule check with its inputs and result.
4. WHEN a Tribunal_Session completes, THE Guide_System SHALL export the Trace as a JSON file.
5. THE Guide_System SHALL provide for each statement in the Ruling a link chain from statement to Exhibit to source data files in the Trace.
6. THE Guide_System SHALL exclude model reasoning content blocks returned by the Converse API from the Ruling and the Trace, and SHALL store in the Trace only input and output summaries of at most the configured character length.
7. THE Guide_System SHALL record in the Trace the pinned Snapshot_Id at the start of each Tribunal_Session and each Cache_Fallback event.
8. THE Guide_System SHALL record in the Trace event of each agent invocation the Instruction_Hash of the System_Prompt that the agent used, as specified in Requirement 21.

### Requirement 10: Validation and Testing

**User Story:** As a developer, I want automated checks, so that I can show that results and explanations are faithful to the data.

#### Acceptance Criteria

1. THE Guide_System SHALL include unit tests for each Toolkit function with fixed input data and expected outputs.
2. THE Guide_System SHALL include a test that fails if any Toolkit function returns a value using an observation dated after the As_Of_Date.
3. THE Guide_System SHALL include a test that verifies each number in a Ruling matches its cited Exhibit.
4. THE Guide_System SHALL include a test that runs a Tribunal_Session for Robert with the request "30% in TSLA" and verifies that the Verdict is not an unconditional accept.
5. THE Guide_System SHALL include a test that runs a Tribunal_Session for Amira with a crypto-heavy request and verifies that the Judge_Agent applies a per-asset-class cap.
6. THE Guide_System SHALL include a test that runs a Tribunal_Session for Mateo with the request "10% in XOM" and verifies that the ESG_Exclusion_List rule fails with its cited source, that the Ruling cites the exclusion-cost Exhibit, and that the Ruling reports the absence of ESG scores in the Dataset.
7. THE Guide_System SHALL include a test that verifies the CNQ.TO split-anomaly note is attached to any Exhibit whose period includes 2022-08-22.
8. THE Guide_System SHALL include a sensitivity test that verifies the reported threshold flips the Verdict when applied.
9. THE Guide_System SHALL include a test that verifies the shipped Persona_Templates exist for amira, mateo, and robert, that every source excerpt of the shipped Persona_Templates occurs verbatim in the Context_Document, and that the quoted Persona_Facts of the shipped Persona_Templates equal a fixture transcribed from section 3 of the Context_Document, and a test that verifies that a Persona_File with an added, duplicated, edited, or removed Persona entry loads without error and that an invalid entry is reported per field.
10. THE Guide_System SHALL include a test that simulates an unreachable Primary_Store and verifies that the Tribunal_Session uses the Local_Cache, the Trace records the Cache_Fallback, every Exhibit carries the fallback note, and the UI shows the fallback notice.
11. THE Guide_System SHALL include a test that verifies identical Exhibit values for the same Dataset_Snapshot read from the Primary_Store and from the Local_Cache.
12. THE Guide_System SHALL include a test that verifies the CSV to Parquet round trip for every Dataset table.
13. THE Guide_System SHALL include a test that verifies that a Seed_Import_Job validation failure or write failure leaves the Current_Snapshot_Pointer unchanged and names the failing check.
14. THE Guide_System SHALL include an integration test that verifies that Athena row counts per table for a Dataset_Snapshot equal the row counts read by the Data_Loader.
15. THE Guide_System SHALL include a test that synthesizes the CDK_App and checks the resulting deployment templates for the IAM scopes of Requirements 8.10 to 8.13 and 25.2.
16. THE Guide_System SHALL include tests that verify that every agent has an Instruction_File, that every Skill_File referenced by an Instruction_File exists, that the composed System_Prompt of every agent contains the guidance_only Skill_File, and that the Instruction_Hash appears in the Trace of a Tribunal_Session.
17. THE Guide_System SHALL include a test that verifies that the guide package, `data/build_dataset_s3.py` when present, and requirements.txt contain no yfinance import or dependency and no Yahoo Finance download call, and that the Data_Source_Document contains the statements required by Requirement 20.4.
18. THE Guide_System SHALL include tests that verify that the Session_API returns a Tribunal_Session only to its owner, rejects requests without a valid token, validates each response against the SessionView schema, and exposes no operation of the kind prohibited by Requirement 22.10.
19. THE Guide_System SHALL include front-end component tests that verify that the UI renders Friendly_Mode and Advanced_Mode from one SessionView, contains no action control, and shows the guidance-only statement and the snapshot badge in both modes.
20. WHERE the S3_Build_Script is implemented, THE Guide_System SHALL include tests that verify that a dry run writes nothing to the Primary_Store, that a repeated run on identical input produces identical checksums, and that the script contains no download call.

### Requirement 11: Deliverables and Documentation

**User Story:** As a datathon team, I want all required deliverables prepared, so that the submission is complete.

#### Acceptance Criteria

1. THE Guide_System SHALL include a README documenting dependencies, data sources, configuration, startup and reproduction instructions, deployment of the data templates, seeding of the baseline Dataset_Snapshot, running the Seed_Import_Job, and deploying the CDK_App with one command.
2. THE Guide_System SHALL include technical documentation covering methods, justification of technologies, assets used, processing, assumptions, the explainability mechanism with one worked example linking a conclusion to Exhibits and Trace entries, validations, limits, and planned improvements.
3. THE Guide_System SHALL include a one-page summary covering the problem, the agentic approach, originality, data sources, explanation capability, and user benefits.
4. THE Guide_System SHALL include a demo script for a video of about 5 minutes showing the five demo cases of Requirement 33 (at minimum Robert with one Appeal, Amira citing Robert's Precedent, and Mateo), the pinned S3 snapshot, the Glue tables, an Athena validation query, the Trace and Observability view, and the Benchmark result of Requirement 34.
5. THE Guide_System SHALL state in the README and the one-page summary that the system is a simulation, is not personalized financial advice, and does not predict returns.
6. THE Guide_System SHALL run the demo video against the real S3 Primary_Store.
7. WHERE a Cache_Fallback demonstration is included in the demo, THE demo script SHALL present it as a separate scenario clearly labelled as a fallback demonstration.
8. THE README SHALL document how to reproduce the S3 setup: deploying the data platform and IAM templates, seeding the baseline Dataset_Snapshot into the Primary_Store, configuring the bucket and prefix, and verifying the pinned snapshot.
9. THE technical documentation SHALL include the AWS_Service_Map with each AWS service, its role, the requirement it serves, and whether it is MVP or stretch.
10. THE demo script SHALL show on screen each MVP service of the AWS_Service_Map that has a console or application view, and SHALL name the services it shows.

### Requirement 12: Flight Simulator (Optional Stretch)

**User Story:** As an investor, I want to replay real history and see how I react, so that my revealed risk tolerance informs my Investor_Contract.

#### Acceptance Criteria

1. WHERE the Flight Simulator is enabled, THE Flight_Director_Agent SHALL start a replay on 2021-11-12 with a fictional portfolio and advance week by week.
2. WHERE the Flight Simulator is enabled, THE Toolkit SHALL provide portfolio_value, market_snapshot, and detect_stress_events functions that accept an As_Of_Date and use only data available on that date.
3. WHERE the Flight Simulator is enabled, WHEN portfolio drawdown from its prior peak exceeds a configured threshold, THE Flight_Director_Agent SHALL pause the replay and mark a Stress_Event.
4. WHERE the Flight Simulator is enabled, WHEN a Stress_Event is marked, THE Copilot_Agent SHALL explain the event citing Exhibits computed as of that date and SHALL ask the investor to choose hold, sell, or buy more.
5. WHERE the Flight Simulator is enabled, THE Behavior_Analyst_Agent SHALL record each investor decision with its date and portfolio drawdown.
6. WHERE the Flight Simulator is enabled, WHEN a session ends, THE Behavior_Analyst_Agent SHALL compare the stated maximum drawdown in the Investor_Contract with the drawdown at which the investor first sold, and SHALL propose an updated Investor_Contract.
7. WHERE the Flight Simulator is enabled, THE Guide_System SHALL store the revealed-tolerance result in AgentCore Memory so that a later Tribunal_Session can use the updated Investor_Contract.
8. WHERE the Flight Simulator is enabled, THE Guide_System SHALL require investor approval before replacing the stored Investor_Contract with the proposed update.

### Requirement 13: Guidance-Only Constraint

**User Story:** As a datathon organizer and investor, I want the system to guide only and never act, so that the user alone decides and performs every action.

#### Acceptance Criteria

1. THE Guide_System SHALL comply with the Guidance_Only_Rule in every component and agent.
2. THE Guide_System SHALL contain no function that places, routes, prefills, or triggers an order, transfer, or brokerage or bank action.
3. THE Guide_System SHALL hold no brokerage or bank credentials, API keys, or session tokens.
4. THE Guide_System SHALL contain no integration with a brokerage or bank API.
5. THE Guardrail SHALL block any model input or output that instructs, requests, or simulates the execution of a real order, transfer, or brokerage or bank action.
6. IF the Guardrail or the Judge_Agent detects a Guidance_Only_Rule violation, THEN THE Guide_System SHALL block the output, record the block in the Trace, and display a message stating that the Guide_System only provides guidance.
7. THE Guide_System SHALL phrase each recommendation-like statement in the Ruling as guidance for the user to consider and decide personally.
8. THE Guide_System SHALL include a test that verifies the Guardrail and Judge_Agent block outputs that instruct or trigger an order, transfer, or brokerage or bank action.
9. THE Guide_System SHALL include a test that verifies the source code, configuration, Instruction_Files, and Skill_Files contain no brokerage or bank credentials and no brokerage or bank API client.
10. THE Guide_System SHALL state the Guidance_Only_Rule in the README, the technical documentation, and the one-page summary.

### Requirement 14: Removed

**User Story:** As a datathon team, I want the removed Companion_Extension scope recorded, so that references to the number 14 stay unambiguous.

#### Acceptance Criteria

1. THE Guide_System SHALL contain no browser extension, no simulated brokerage page, and no local guidance API for a browser extension.

### Requirement 15: Proactive Alerts (Optional Stretch)

**User Story:** As an investor, I want to be notified when a major market event affects my simulated portfolio, so that I can review my position with guidance in time.

#### Acceptance Criteria

1. WHERE Alerts are enabled, THE Guide_System SHALL detect Market_Events using only Dataset-derived data as of the As_Of_Date.
2. WHERE Alerts are enabled, WHEN a Market_Event affects an asset held in the Simulated_Portfolio, THE Guide_System SHALL create an Alert naming the asset, the event date, and the Exhibit that quantifies the event.
3. WHERE Alerts are enabled, THE Guide_System SHALL label each Alert as guidance, as a simulation, and as not personalized financial advice.
4. WHERE Alerts are enabled, THE Guide_System SHALL display each Alert in the UI as a notification with a plain-language summary in Friendly_Mode and the underlying Exhibits in Advanced_Mode.
5. WHERE Alerts are enabled, THE Guide_System SHALL use a configured threshold to decide that a single-day price move or portfolio drawdown is a Market_Event.
6. WHERE Alerts are enabled, THE Guide_System SHALL include in each Alert a link that opens a Tribunal_Session for the affected position.
7. WHERE Alerts are enabled, THE Guide_System SHALL include in each Alert no instruction to buy, sell, or transfer and no trigger of an order, transfer, or brokerage or bank action.
8. WHERE Alerts are enabled, THE Guide_System SHALL record each Alert in the Trace with its source Exhibit.
9. WHERE Alerts are enabled, IF the Simulated_Portfolio holds no asset affected by a Market_Event, THEN THE Guide_System SHALL create no Alert for that Market_Event.
10. WHERE Alerts are enabled, THE Guide_System SHALL include in each Alert a statement that the Alert is based on the Dataset_Snapshot named by its Snapshot_Id and retrieval date, and not on live news or live market data.

### Requirement 16: Persona Templates File

**User Story:** As an investor, I want ready-made persona templates that I can edit, extend, or replace with my own profile, so that I start from a faithful reference and still get guidance that fits my situation.

#### Acceptance Criteria

1. THE Persona_File SHALL ship three Persona_Templates with the identifiers `amira`, `mateo`, and `robert` and the display names Amira, Mateo, and Robert, transcribed from section 3 of the Context_Document as default starting points.
2. WHEN the Persona_File contains more or fewer than three entries, entries with edited values, or entries with identifiers other than `amira`, `mateo`, and `robert`, THE Profiler_Agent SHALL load every valid entry without failing.
3. THE Persona_File SHALL require for each entry an identifier, a display name, a risk level, a horizon, and the Contract_Values horizon in years, maximum volatility, maximum tolerated drawdown, per-asset cap, per-asset-class caps, crypto cap, sector caps, and ESG exclusions.
4. THE Persona_File SHALL accept for each entry the optional fields age, occupation, family situation, investment experience, objective, preferences and constraints, what the Persona tests, speculative-asset limit, verbatim excerpts, and rationales.
5. IF an entry lacks a required field or holds an invalid value, THEN THE Profiler_Agent SHALL report each failing pair of Persona identifier and field, SHALL exclude that entry from the persona picker, and SHALL keep every valid entry available.
6. IF the Persona_File cannot be read or parsed, THEN THE UI SHALL display the loading error, SHALL list no Persona_Template, and SHALL keep the custom-profile form available.
7. THE Persona_File SHALL allow each Contract_Value to carry a Contract_Value_Basis of `quoted`, `assumption`, or `user`, a rationale, and a verbatim excerpt.
8. THE shipped Persona_Templates SHALL record for each Contract_Value a Contract_Value_Basis and a rationale, and for each `quoted` Contract_Value and each quoted Persona_Fact the verbatim excerpt of section 3 of the Context_Document.
9. THE shipped Persona_Templates SHALL record the Persona_Facts as stated in the Context_Document, including: Amira, age 26, software engineer, risk level high, horizon 15 years or more; Mateo, age 41, operations manager, risk level moderate, horizon 8 to 12 years; Robert, age 59, health professional, risk level low to moderate, horizon 3 to 5 years.
10. THE shipped Persona_Templates SHALL use the lower bound of the Context_Document horizon (15, 8, and 3 years) as the default `horizon_years`, and THE Profiler_Agent SHALL accept another single value or a range from the user.
11. WHEN a Persona_Template is selected and used without edits, THE Profiler_Agent SHALL build the Investor_Contract only from the Contract_Values of that Persona_Template, without a language model call.
12. THE Profiler_Agent SHALL set the provenance of each Investor_Contract field built from a Contract_Value to `persona_quoted` for the basis `quoted`, to `persona_assumption` for the basis `assumption`, and to `user` for the basis `user`.
13. WHEN the user edits the values of a Persona_Template in the form and submits the form, THE Profiler_Agent SHALL build the Investor_Contract from the submitted values, SHALL set the provenance `user` for each field whose submitted value differs from the Persona_Template, and SHALL keep the Persona_Template provenance for each unchanged field.
14. WHEN a custom-profile form is filled from blank, THE Profiler_Agent SHALL build the Investor_Contract from the form values and stated defaults only, with the provenance `form` or `default` and with no Persona_File value.
15. THE Profiler_Agent SHALL read persona facts only from the Persona_File and the form values and SHALL ask no language model for persona facts.
16. WHEN a Ruling relies on an Investor_Contract field with `persona_assumption` provenance, THE Clerk SHALL list the field, its value, and its rationale from the Persona_File in the Assumptions section, and WHERE the Persona_File has no rationale for the field, THE Clerk SHALL state that no rationale is recorded.

### Requirement 17: Amazon S3 Primary Store and Local Cache

**User Story:** As a data reviewer, I want one system of record for the data and a visible, recorded fallback, so that every Exhibit can be reproduced from a known snapshot even when S3 is unreachable.

#### Acceptance Criteria

1. THE Data_Loader SHALL read every Dataset table from a Dataset_Snapshot in the Primary_Store, in local and deployed environments.
2. WHEN a Tribunal_Session starts, THE Data_Loader SHALL resolve the Current_Snapshot_Pointer once and pin the resulting Snapshot_Id for the whole Tribunal_Session.
3. WHILE a Tribunal_Session is running, THE Data_Loader SHALL read only the files listed in the Snapshot_Manifest of the pinned Dataset_Snapshot, by the S3 object version identifiers recorded in that Snapshot_Manifest.
4. WHEN the Local_Cache holds a file whose S3 object version identifier and SHA-256 checksum match the Snapshot_Manifest, THE Data_Loader SHALL serve the file from the Local_Cache without downloading the file.
5. WHEN the Data_Loader resolves the Current_Snapshot_Pointer while the Primary_Store is reachable, THE Data_Loader SHALL send a conditional request with the ETag of the cached pointer and SHALL replace the cached pointer when the Primary_Store returns a different ETag.
6. IF the SHA-256 checksum of a cached or downloaded file differs from the Snapshot_Manifest, THEN THE Data_Loader SHALL discard the file and download the file once more.
7. IF the SHA-256 checksum of a re-downloaded file still differs from the Snapshot_Manifest, THEN THE Data_Loader SHALL report a data-integrity error naming the file, and THE Guide_System SHALL start no Tribunal_Session.
8. IF the Primary_Store is unreachable, meaning a connection error, a timeout after the configured number of seconds, an HTTP 5xx response after the configured retries, or unavailable AWS credentials, THEN THE Data_Loader SHALL serve the Dataset_Snapshot named by the cached Current_Snapshot_Pointer from the Local_Cache after checksum verification and SHALL record a Cache_Fallback.
9. IF the Primary_Store returns an access-denied error, THEN THE Data_Loader SHALL report a configuration error naming the denied resource and SHALL start no Cache_Fallback.
10. WHEN a Cache_Fallback occurs, THE Guide_System SHALL record in the Trace one event with the cause, the served Snapshot_Id, and its retrieval timestamp.
11. WHEN a Cache_Fallback occurs, THE Toolkit SHALL add to the processing notes of every Exhibit of the Tribunal_Session a note stating that the Dataset was served from the Local_Cache and naming the Snapshot_Id.
12. WHEN a Cache_Fallback occurs, THE UI SHALL display in Friendly_Mode and Advanced_Mode a notice stating that the Primary_Store was unreachable and naming the served Snapshot_Id and its retrieval date.
13. IF the Primary_Store is unreachable and the Local_Cache holds no checksum-verified Dataset_Snapshot, THEN THE Guide_System SHALL report a Dataset-unavailable error naming the Primary_Store location and SHALL start no Tribunal_Session.
14. THE Guide_System SHALL serialize each Snapshot_Manifest and the Current_Snapshot_Pointer as JSON validated against a JSON schema stored in the repository.
15. FOR ALL valid Snapshot_Manifests, serializing then parsing SHALL produce an equivalent Snapshot_Manifest (round-trip property).
16. IF a Snapshot_Manifest or the Current_Snapshot_Pointer fails schema validation, THEN THE Data_Loader SHALL report an error naming the failing fields and SHALL treat the Dataset_Snapshot as unavailable.

### Requirement 18: Parquet Snapshots and AWS Glue Data Catalog

**User Story:** As a data reviewer, I want the Dataset stored as typed, partitioned tables in a catalog, so that the data can be inspected and queried in a standard way.

#### Acceptance Criteria

1. WHEN the Snapshot_Writer writes a Dataset_Snapshot, THE Snapshot_Writer SHALL store the source CSV files unchanged and one Parquet file per Dataset table under a `snapshot_id` partition prefix.
2. THE Snapshot_Writer SHALL write each Parquet file with the column names and explicit column types (date, string, double, bigint) defined for its Dataset table.
3. FOR ALL Dataset tables, converting the CSV to Parquet and reading the Parquet back SHALL produce the same column names, row count, and values as reading the CSV with the declared column types (round-trip property).
4. THE Data_Catalog SHALL define one AWS Glue database and one table each for assets_universe, prices_daily, corporate_actions, fx_usdcad_daily, and macro_rates, with explicit column definitions, Parquet storage, and `snapshot_id` as the partition key.
5. WHEN a Dataset_Snapshot passes validation, THE Snapshot_Writer SHALL register one `snapshot_id` partition per Dataset table in the Data_Catalog.
6. IF writing a file, registering a partition, or validating a Dataset_Snapshot fails, THEN THE Snapshot_Writer SHALL leave the Current_Snapshot_Pointer unchanged and SHALL report the failing step.
7. THE Guide_System SHALL define the Primary_Store bucket, the Athena results bucket, the Data_Catalog, and the Athena_Workgroup in deployment templates stored in the repository.
8. THE Snapshot_Writer SHALL provide a seed operation that writes the starter files in /workshop/Agent52/data as the baseline Dataset_Snapshot with source `starter` and the retrieval date 2026-11-13 recorded in sources_metadata.csv.
9. THE Data_Loader SHALL read Dataset tables from the Parquet files of the pinned Dataset_Snapshot.
10. THE Snapshot_Writer SHALL write each Dataset_Snapshot object only to a key that does not yet exist in the Primary_Store.

### Requirement 19: Amazon Athena Queries

**User Story:** As a data reviewer, I want to query the catalogued Dataset with SQL, so that I can explore and cross-check the data without affecting the deterministic Toolkit.

#### Acceptance Criteria

1. THE Athena_Workgroup SHALL enforce a query result location in the Athena results bucket, encryption of query results, and a per-query scanned-bytes limit read from configuration.
2. WHEN the Snapshot_Writer validates a Dataset_Snapshot, THE Snapshot_Writer SHALL run Athena validation queries for the row count per table, duplicate (date, ticker) rows, equality of the price ticker set with the assets_universe ticker set, non-positive adj_close values, and currency mismatches with assets_universe, and SHALL store the results in the Snapshot_Manifest.
3. IF an Athena validation query reports a violation or a result that differs from the Python validation result for the same check, THEN THE Snapshot_Writer SHALL leave the Current_Snapshot_Pointer unchanged and SHALL report the check.
4. IF Athena is unavailable during validation, THEN THE Snapshot_Writer SHALL record the Athena validation as skipped in the Snapshot_Manifest and SHALL use the Python validation result as the gate for the Current_Snapshot_Pointer update.
5. THE Guide_System SHALL provide in the repository at least one saved exploration query per Dataset table over the Data_Catalog.
6. THE Guide_System SHALL include a `snapshot_id` predicate, passed as an Athena execution parameter, in every Athena query that the Guide_System issues.
7. IF a Snapshot_Id passed to the Athena query builder does not match the Snapshot_Id format, THEN THE Guide_System SHALL reject the query before submission.
8. THE Toolkit SHALL compute every Exhibit value in deterministic Python from tables read by the Data_Loader and SHALL use no Athena query result as an input to an Exhibit value.

### Requirement 20: Dataset Sources, Licensing, and Seed Import

**User Story:** As a data reviewer, I want every data source to be licensed for this project and documented, so that the team uses and redistributes only data it is allowed to use.

#### Acceptance Criteria

1. THE Guide_System SHALL create Dataset_Snapshots only from the starter data in the seed directory and from documented additions that satisfy Requirements 20.2 and 20.3.
2. IF the terms of use of a candidate source in the Data_Source_Document do not permit use in this project and redistribution within the Primary_Store, or limit the source to personal or non-commercial use, THEN THE Guide_System SHALL reject the source and SHALL add no data from the source to any Dataset_Snapshot.
3. WHERE data from an addition is added to a Dataset_Snapshot, THE Guide_System SHALL add to the Data_Source_Document an entry with the origin, the URL, the retrieval date, the terms-of-use URL, and a statement of the permitted use and redistribution, before the Seed_Import_Job writes the Dataset_Snapshot.
4. THE Data_Source_Document SHALL state that Yahoo Finance through the yfinance library is the origin of the starter prices and corporate actions, that the Baseline_Build_Script `data/build_dataset.py` built the starter files, that the starter data is used under the datathon permission "Free to use within the datathon" recorded in sources_metadata.csv, and that the team downloads no new Yahoo Finance data.
5. THE guide package, THE S3_Build_Script, and THE dependency list SHALL contain no code that downloads data from Yahoo Finance or through the yfinance library and no yfinance dependency.
6. WHEN the Seed_Import_Job prepares a Dataset_Snapshot, THE Seed_Import_Job SHALL validate that no (date, ticker) row is duplicated, every universe ticker has rows, each ticker currency equals its assets_universe currency, and every adj_close value is positive, before the Snapshot_Writer writes the Dataset_Snapshot.
7. IF the validation of Requirement 20.6 fails, THEN THE Seed_Import_Job SHALL write no Dataset_Snapshot, SHALL leave the Current_Snapshot_Pointer unchanged, and SHALL report each violation.
8. IF a ticker outside the assets_universe table of the starter data is requested for import, THEN THE Seed_Import_Job SHALL reject the ticker unless the Universe_Additions_File lists the ticker with name, asset class, market, currency, sector, source name, and data file, and the Data_Source_Document has an entry that satisfies Requirement 20.3.
9. WHEN a documented addition changes only some Dataset tables, THE Seed_Import_Job SHALL copy the other tables from the previous Dataset_Snapshot and SHALL record the source Snapshot_Id of each copied table in the Snapshot_Manifest.
10. WHEN a Toolkit function is called with an As_Of_Date later than the coverage end of the pinned Dataset_Snapshot, THE Toolkit SHALL use observations up to the coverage end and SHALL add a processing note stating the coverage end.
11. THE Guide_System SHALL keep the Baseline_Build_Script unchanged as the reference for how the starter files were built, and SHALL run the Baseline_Build_Script in no test, job, or deployment step.

### Requirement 21: Agent Instruction Files and Skills

**User Story:** As a juror and developer, I want each agent to follow its own versioned instructions built from shared skills, so that agent behavior is reviewable and every explanation can be tied to the exact instructions used.

#### Acceptance Criteria

1. THE Guide_System SHALL provide for each of the Profiler_Agent (free-text intake only), Advocate_Agent, Investigator_Agent, and Judge_Agent, and for each enabled stretch agent, one Instruction_File at `guide/agents/instructions/<agent>.md`.
2. THE Instruction_File SHALL contain the sections role, goals, allowed tools, output JSON format, forbidden behaviors, citation rule, guidance-only rule, tone, and included skills.
3. THE Guide_System SHALL provide the Skill_Files `citing_exhibits.md`, `guidance_only.md`, `data_limits.md`, `plain_language.md`, and `persona_handling.md` at `guide/agents/skills/<skill>.md`.
4. THE Instruction_Loader SHALL compose the System_Prompt of an agent from the agent's Instruction_File followed by the Skill_Files listed in the Instruction_File, in the listed order.
5. IF an agent has no Instruction_File or an Instruction_File lists a Skill_File that does not exist, THEN THE Instruction_Loader SHALL report an error naming the agent and the missing file, and THE Guide_System SHALL start no Tribunal_Session.
6. THE System_Prompt of every agent SHALL contain the text of the guidance_only Skill_File.
7. THE Instruction_Loader SHALL compute the Instruction_Hash of each System_Prompt, and the Instruction_Hash SHALL change whenever the text of the Instruction_File or of a listed Skill_File changes.
8. WHEN an agent is invoked, THE Guide_System SHALL pass the System_Prompt of that agent to the Bedrock Converse call and SHALL record the Instruction_Hash in the Trace as specified in Requirement 9.8.
9. THE Instruction_Files and Skill_Files SHALL contain no credentials or secrets and SHALL forbid every instruction to place, route, prefill, or trigger an order, transfer, or brokerage or bank action.
10. THE static scan of Requirement 13.9 SHALL cover every Instruction_File and Skill_File.
11. THE `data_limits` Skill_File SHALL state the survivorship bias of the Dataset, the absence of ESG scores, news, and company fundamentals, and the unverified CNQ.TO split note.
12. THE `plain_language` Skill_File SHALL require plain-language summaries of at most 60 words written in English.
13. THE `persona_handling` Skill_File SHALL state that a profile is not equated with an asset, that volatility is one risk indicator among others, that persona facts come only from the Investor_Contract, and that a request incoherent with the Investor_Contract is challenged.
14. THE `citing_exhibits` Skill_File SHALL require that each factual claim cites an Exhibit number and states numbers as the Exhibit states them.

### Requirement 22: Web Delivery, Authentication, and Session API

**User Story:** As an investor or juror, I want to open the guide from a hosted website after signing in, so that I can use it without installing anything and my sessions stay private.

#### Acceptance Criteria

1. THE UI SHALL be a single-page web application built from the `frontend/` directory of the repository and hosted on AWS Amplify Hosting.
2. WHEN a user opens the UI without a valid Identity_Provider session, THE UI SHALL display the sign-in page and SHALL display no Tribunal_Session data.
3. THE Session_API SHALL authorize every request with a JSON Web Token issued by the Identity_Provider.
4. IF a request to the Session_API carries no valid token, THEN THE Session_API SHALL return HTTP 401 and SHALL create or return no Tribunal_Session data.
5. WHEN the UI submits a profile and an Investment_Request, THE Session_API SHALL store a Tribunal_Session record with status `running` in the Session_Store and SHALL return the session identifier within 3 seconds.
6. WHILE a Tribunal_Session is running, THE Agent_Runtime SHALL write the updated SessionView to the Session_Store after each agent stage completes.
7. WHEN the UI requests a Tribunal_Session by identifier, THE Session_API SHALL return the SessionView of that Tribunal_Session to the user who created it.
8. IF a user requests a Tribunal_Session that another user created, THEN THE Session_API SHALL return HTTP 404.
9. THE Session_API SHALL expose only operations to list Persona_Templates, save and list Custom_Profiles, create a Tribunal_Session, read a Tribunal_Session, and download the Trace of a Tribunal_Session.
10. THE Session_API SHALL expose no operation that places, routes, prefills, or triggers an order, transfer, or brokerage or bank action.
11. THE Session_API SHALL accept cross-origin requests only from the origin of the hosted UI.
12. THE Session_Store SHALL delete each Tribunal_Session record 7 days after its creation.
13. THE UI and THE Session_API SHALL hold no AWS access keys and no brokerage or bank credentials, and THE browser SHALL hold only Identity_Provider tokens.
14. THE Guide_System SHALL provide one orchestrator entry point `run_session` that the Agent_Runtime, the tests, and a local command-line runner call, so that the Python core runs unchanged outside AWS.
15. THE Guide_System SHALL serialize each SessionView as JSON validated against a JSON schema stored in the repository.
16. FOR ALL valid SessionViews, serializing then parsing SHALL produce an equivalent SessionView (round-trip property).
17. IF an agent stage of a Tribunal_Session fails, THEN THE Agent_Runtime SHALL write to the Session_Store a SessionView with status `failed`, the failing stage, and an error message.

### Requirement 23: Amazon Bedrock AgentCore Runtime and Agent Services

**User Story:** As a datathon team, I want the agents hosted on a managed agent runtime with memory and observability, so that the AWS integration is real and verifiable.

#### Acceptance Criteria

1. THE Agent_Runtime SHALL host the Tribunal_Orchestrator, all agents, and the Toolkit as one Amazon Bedrock AgentCore Runtime built from a container image defined in the repository.
2. WHEN the Session_API invokes the Agent_Runtime for a new Tribunal_Session, THE Agent_Runtime SHALL start the Tribunal_Session as a background task and SHALL return an acknowledgement before the Verdict exists.
3. THE Agent_Runtime SHALL run under the Application_Role.
4. THE Guide_System SHALL key each AgentCore Memory entry by the Identity_Provider user identifier and the profile identifier, and SHALL read only the entries of the signed-in user.
5. THE Agent_Runtime SHALL emit one OpenTelemetry span to AgentCore Observability for each agent call, tool call, and Judge check, and each span SHALL carry the Snapshot_Id.
6. IF the Session_API cannot reach the Agent_Runtime, THEN THE Session_API SHALL set the Tribunal_Session status to `failed` with the stage `runtime` and SHALL return HTTP 503.
7. WHERE AgentCore Gateway is enabled, THE Guide_System SHALL publish each Toolkit function as an MCP tool through the Gateway with the same JSON input schema as its Converse tool specification.
8. WHERE AgentCore Gateway is enabled, THE Toolkit SHALL return the same value for a call through the Gateway as for the in-process call with identical inputs on the same Dataset_Snapshot.
9. WHERE AgentCore Identity is enabled, THE Agent_Runtime SHALL accept only invocations authorized by a JSON Web Token from the Identity_Provider.

### Requirement 24: Automated Snapshot Pipeline (Optional Stretch)

**User Story:** As a data reviewer, I want a new Dataset candidate dropped into S3 to be validated, catalogued, and published automatically, so that publishing a Dataset_Snapshot needs no manual steps.

#### Acceptance Criteria

1. WHERE the Snapshot_Pipeline is enabled, WHEN a marker object `_READY` is created under an `incoming/{label}/` prefix of the Primary_Store, THE Snapshot_Pipeline SHALL start one state machine execution through an Amazon S3 event delivered by Amazon EventBridge.
2. WHERE the Snapshot_Pipeline is enabled, THE Snapshot_Pipeline SHALL run validation, the write of raw CSV and Parquet files, the registration of Data_Catalog partitions, the Athena validation, and the update of the Current_Snapshot_Pointer, in this order, by calling the Seed_Import_Job library.
3. WHERE the Snapshot_Pipeline is enabled, IF a step fails, THEN THE Snapshot_Pipeline SHALL leave the Current_Snapshot_Pointer unchanged and SHALL record the failing step in the execution output.
4. WHERE the Snapshot_Pipeline is enabled, THE Snapshot_Pipeline SHALL apply Requirements 20.2, 20.3, and 20.8 to the candidate files before it writes any object.
5. WHERE the Glue ETL job variant is enabled, THE Glue ETL job SHALL convert each CSV table to Parquet with the column types of Requirement 18.2.
6. WHERE the Glue ETL job variant is enabled, FOR ALL Dataset tables, the Parquet file produced by the Glue ETL job and the Parquet file produced by the Snapshot_Writer SHALL contain the same column names, row count, and values.
7. THE Snapshot_Writer SHALL be the only component that registers partitions in the Data_Catalog, and THE CDK_App SHALL define no Glue crawler for the curated tables.

### Requirement 25: Security, Monitoring, and Cost Control

**User Story:** As a datathon team, I want security controls, monitoring, and a cost alarm on the deployed system, so that the demo is safe, observable, and affordable.

#### Acceptance Criteria

1. THE CDK_App SHALL create a separate IAM role for each of the Application_Role, the Session_API Lambda functions, the Seed_Import_Job, the Snapshot_Pipeline, and the Athena query role, and each role SHALL hold only the permissions that the design lists for it.
2. THE CDK_App SHALL grant the Session_API Lambda role only DynamoDB read and write actions on the Session_Store, the AgentCore Runtime invocation action on the Agent_Runtime, and log and trace write actions.
3. THE CDK_App SHALL create Amazon CloudWatch log groups with 30-day retention for the Session_API, the Agent_Runtime, and the Snapshot_Pipeline.
4. THE CDK_App SHALL create one CloudWatch dashboard that shows the number of Tribunal_Sessions started, the number of Tribunal_Sessions failed, the number of Guardrail interventions, the number of Bedrock throttling errors, the number of Session_API 5xx responses, and the number of Cache_Fallback events.
5. THE CDK_App SHALL create CloudWatch alarms for Session_API 5xx responses, failed Tribunal_Sessions, and Bedrock throttling errors, and each alarm SHALL notify an Amazon SNS topic.
6. THE CDK_App SHALL enable Amazon Bedrock model invocation logging to a CloudWatch log group with 30-day retention.
7. THE CDK_App SHALL create an AWS Budgets monthly cost budget with a notification at 80 percent of the budget amount for actual cost and at 100 percent for forecast cost, sent to an email address read from configuration.
8. THE CDK_App SHALL enable AWS X-Ray active tracing on the Session_API Lambda functions.
9. WHERE AWS WAF is enabled, THE CDK_App SHALL associate a web ACL with the AWS managed common rule group and a rate-based rule to the Session_API stage and to the Amplify Hosting application.
10. WHERE the customer managed KMS key is enabled, THE CDK_App SHALL create one KMS key with key rotation enabled and use the key to encrypt the Primary_Store, the Session_Store, and the CloudWatch log groups.
11. WHERE CloudTrail data events are enabled, THE CDK_App SHALL create a trail that records S3 data events of the Primary_Store.
12. WHERE S3 Object Lock is enabled, THE CDK_App SHALL create the Primary_Store with S3 Object Lock in governance mode and a default retention of 30 days.
13. IF a deployment value is a secret, THEN THE CDK_App SHALL read the value from AWS Secrets Manager at deployment time and SHALL store no secret in the repository.

### Requirement 26: Infrastructure as Code and One-Command Deployment

**User Story:** As a datathon team, I want the whole AWS environment defined in code and deployed with one command, so that the jury can reproduce it and the team can rebuild it quickly.

#### Acceptance Criteria

1. THE CDK_App SHALL define in Python with AWS CDK v2 every AWS resource that the AWS_Service_Map marks as MVP.
2. THE repository SHALL provide a command `make deploy` that builds the front end and the Agent_Runtime container image, deploys all MVP stacks of the CDK_App, publishes the front end to Amplify Hosting, and prints the UI URL.
3. THE repository SHALL provide a command `make seed` that runs the Seed_Import_Job on the starter files against the deployed Primary_Store.
4. THE CDK_App SHALL read the region, the bucket name suffix, the model identifier, the budget amount, the budget email address, and the enable flags of the stretch components from CDK context, and THE CDK_App SHALL contain no credentials.
5. WHEN a deployment completes, THE CDK_App SHALL output the UI URL, the Session_API URL, the Identity_Provider identifiers, the Agent_Runtime ARN, the Primary_Store bucket name, and the Athena_Workgroup name.
6. WHEN the command `make destroy` runs, THE CDK_App SHALL remove every stack resource except the Primary_Store bucket and its objects.
7. THE README SHALL document the prerequisites, the one-command deployment, the seeding, a smoke test of the deployed Session_API, and the teardown.

### Requirement 27: S3-Focused Dataset Build Script (Optional Future Improvement)

**User Story:** As a data reviewer, I want one command that rebuilds a dated Dataset_Snapshot in S3 from the provided CSV files, so that the S3 data can be recreated reproducibly without touching the baseline script.

#### Acceptance Criteria

1. WHERE the S3_Build_Script is implemented, THE S3_Build_Script SHALL read the five Dataset CSV files from an input directory given on the command line, with the seed directory as default, and SHALL write them as a dated Dataset_Snapshot through the Seed_Import_Job library.
2. WHERE the S3_Build_Script is implemented, THE S3_Build_Script SHALL accept the output directory of the Baseline_Build_Script as the input directory.
3. WHERE the S3_Build_Script is implemented, THE S3_Build_Script SHALL write the raw CSV files, the Parquet files, and the Snapshot_Manifest to the Primary_Store, register the Data_Catalog partitions, and update the Current_Snapshot_Pointer only after the validation of Requirement 20.6 passes.
4. WHERE the S3_Build_Script is implemented, THE S3_Build_Script SHALL leave the Baseline_Build_Script file unmodified and SHALL neither import nor execute the Baseline_Build_Script.
5. WHERE the S3_Build_Script is implemented, THE S3_Build_Script SHALL download no data from Yahoo Finance, the Bank of Canada, FRED, or any other internet source, and SHALL provide no option that does.
6. WHERE the S3_Build_Script is implemented, THE S3_Build_Script SHALL form the Snapshot_Id from the retrieval timestamp in sources_metadata.csv or from a `--retrieved-at` argument, and from a source label argument that matches the Snapshot_Id format.
7. WHERE the S3_Build_Script is implemented, WHEN the user passes `--dry-run`, THE S3_Build_Script SHALL run the validation, print the planned Snapshot_Id and object keys, and write nothing to the Primary_Store.
8. WHERE the S3_Build_Script is implemented, WHEN the script runs twice on identical input files with the same label and retrieval timestamp, THE S3_Build_Script SHALL produce Parquet files and Snapshot_Manifest entries with identical SHA-256 checksums.
9. WHERE the S3_Build_Script is implemented, IF the Snapshot_Id already exists in the Primary_Store, THEN THE S3_Build_Script SHALL report the existing Snapshot_Id and SHALL write nothing.
10. WHERE the S3_Build_Script is implemented, WHEN the user passes `--prefill-cache`, THE S3_Build_Script SHALL copy the pointer, the Snapshot_Manifest, and the Parquet files into the Local_Cache.

### Requirement 28: Base Portfolios and Risk Evidence

**User Story:** As an investor, I want my request judged against the portfolio I already hold, so that the evidence shows its real effect on me.

#### Acceptance Criteria

1. THE Persona_File SHALL define one Base_Portfolio for each shipped Persona_Template, with tickers from the assets_universe table, weights summing to 1, and the Contract_Value_Basis `assumption` with a rationale.
2. WHEN an Investment_Request adds a position of weight w in an asset, THE Toolkit SHALL build the proposed portfolio by multiplying every Base_Portfolio weight by (1 - w) and adding the requested asset at weight w, and WHERE the asset is already held, adding w to its scaled weight.
3. THE Toolkit SHALL provide `risk_contribution(weights, start, end)` that returns, in CAD, each asset's percentage share of the total portfolio variance, and SHALL store the result as an Exhibit.
4. THE Toolkit SHALL provide `portfolio_comparison(base, proposed, start, end)` that returns, for the Base_Portfolio and the proposed portfolio, the annualized volatility, maximum drawdown, worst rolling 252-trading-day return, calendar-year 2022 return, and annualized return, stored as one Exhibit.
5. THE Toolkit SHALL provide `max_weight_within_contract(asset, contract, base, start, end)` that returns the largest position size, in steps of 0.5 percentage points, for which every Hard_Rule passes, or 0 when no positive size passes, stored as an Exhibit.
6. FOR the Robert Base_Portfolio (XBB.TO 40 %, ZST.TO 15 %, XIU.TO 15 %, SPY 15 %, JNJ 8 %, RY.TO 7 %, daily rebalanced, CAD, dates on which every held asset has a price, 2021-11-12 to 2026-11-12), THE Toolkit SHALL reproduce, within 0.3 percentage points, a maximum drawdown of -10.4 % for the Base_Portfolio and -30.1 % with 30 % TSLA, and a TSLA share of variance of 86.7 % within 1 percentage point.
7. THE Ruling SHALL state that the Base_Portfolio is a fictional assumption.

### Requirement 29: Soft Preferences Weighed by the Judge

**User Story:** As a juror, I want the agents to change the outcome where code cannot decide, so that the multi-agent design is not decorative.

#### Acceptance Criteria

1. THE Investor_Contract SHALL hold a list of Soft_Preferences, each with an identifier, a text, and a provenance, and THE shipped Persona_Templates SHALL each define at least two Soft_Preferences taken from section 3 of the Context_Document with their verbatim excerpts.
2. THE Judge_Agent SHALL assess each Soft_Preference as `satisfied`, `tension`, or `not_satisfied` for each Option that passes the Hard_Rules, and SHALL record the Exhibits and Investigator_Agent findings it relied on.
3. IF a Soft_Preference is assessed `not_satisfied` for the Option retained in the Verdict, THEN THE Guide_System SHALL change a Verdict of accept into accept with conditions and SHALL state the condition in plain language.
4. THE Guide_System SHALL enforce in code that no Judge_Agent output turns a failed Hard_Rule into a pass or a reject into an accept.
5. THE Ruling SHALL show, for each Soft_Preference, the assessment and the findings that decided it, each linked to its Exhibits.

### Requirement 30: Appeal

**User Story:** As an investor, I want to change one assumption and see whether the verdict changes, so that I understand what drives the decision.

#### Acceptance Criteria

1. WHEN a Tribunal_Session is complete, THE UI SHALL offer an Appeal control that lets the user change exactly one input among position size, horizon in years, maximum drawdown, and analysis period.
2. WHEN an Appeal is submitted, THE Guide_System SHALL run a new Tribunal_Session with the changed input, linked to the original session identifier, and SHALL leave the original Tribunal_Session unchanged.
3. THE UI SHALL display the original and the Appeal Verdicts side by side with the changed input, the Hard_Rules whose result changed, the Soft_Preference assessments that changed, and the Exhibits whose value changed.
4. THE Session_API SHALL expose the Appeal as a parameter of the create-session operation and SHALL add no other operation.

### Requirement 31: Precedents

**User Story:** As an investor, I want consistent rulings across profiles, so that a different verdict for a similar request is explained.

#### Acceptance Criteria

1. WHEN a Tribunal_Session completes, THE Guide_System SHALL store a Precedent holding the Persona or profile identifier, the asset, the position size, the Verdict, the deciding Hard_Rules, the Soft_Preference assessments, and the key Exhibit values.
2. WHEN a new Investment_Request names an asset for which a Precedent exists, THE Judge_Agent SHALL cite the Precedent with the closest position size and SHALL name the Investor_Contract fields whose values explain any difference in Verdict.
3. THE Guide_System SHALL store Precedents in the Session_Store table under a shared partition readable by every signed-in user, containing no user identifier other than the Persona or profile identifier.
4. THE Guide_System SHALL seed the Precedent store with the Tribunal_Sessions of the five demo cases of Requirement 33.

### Requirement 32: Documented ESG Exclusion List

**User Story:** As Mateo, I want my ESG preference applied with a stated source, so that the system integrates a criterion beyond risk and return.

#### Acceptance Criteria

1. THE Guide_System SHALL ship the ESG_Exclusion_List `data/esg_exclusions.csv` with the columns ticker, excluded, reason, source_url, and retrieved, covering every asset of the assets_universe table, built by hand from a cited public exclusion methodology (for example the fossil-fuel and controversial-activity exclusions of the index tracked by ESGV).
2. THE Data_Source_Document SHALL describe the ESG_Exclusion_List with its source, retrieval date, method, and the statement that it is a simplified proxy and not an ESG rating.
3. WHERE the Investor_Contract lists ESG exclusions and the requested asset is marked excluded, THE rule engine SHALL fail the ESG Hard_Rule and THE Ruling SHALL cite the source of the exclusion.
4. WHEN the ESG Hard_Rule fails, THE Toolkit SHALL create an exclusion-cost Exhibit comparing, over the analysis period, the annualized return and volatility of the excluded asset with those of the closest non-excluded asset of the same asset class, labelled as past data that does not predict future returns.
5. THE ESG_Exclusion_List SHALL be loaded by the Toolkit like any other Dataset file and SHALL be named in the Snapshot_Manifest.

### Requirement 33: Ruling Answers and Demo Cases

**User Story:** As a juror from National Bank, I want each ruling to answer the questions a credible investment proposal must answer, so that I can judge it with the framework I already use.

#### Acceptance Criteria

1. THE Ruling SHALL contain, in addition to the sections of Requirement 6, four headed answers: "Which data?", "Why this choice?", "Which limits?", and "What would change the answer?", each built from Exhibits, rule results, and the Assumptions and Limits sections.
2. THE Guide_System SHALL ship five demo cases in `demo/cases.yaml`: Robert "30% in TSLA"; Amira "30% in TSLA"; Mateo "10% in XOM"; Amira "40% in BTC-USD"; and a Canadian-heavy Base_Portfolio requesting "20% in SPY" to improve diversification.
3. THE expected outcome of each demo case SHALL be recorded in `demo/cases.yaml`, and at least one demo case SHALL be expected to end in accept or accept with conditions on diversification grounds.
4. THE Friendly_Mode SHALL present the four answers of 33.1 in plain language of at most 60 words each, with Exhibit links.

### Requirement 34: Evaluation Benchmark

**User Story:** As a juror, I want measured evidence that the tribunal behaves better than a single assistant, so that the agentic design is justified by results.

#### Acceptance Criteria

1. THE Guide_System SHALL provide a Benchmark command `python -m guide.bench` that runs every case of `demo/cases.yaml` and `bench/cases.yaml` (at least 10 cases in total) N times through the Guide_System and N times through the Baseline_Agent, with N read from the command line and at least 5 for the published result.
2. THE Benchmark SHALL record, per case and per arm, the share of runs whose Verdict matches the expected outcome, the share of runs that accept a request violating a Hard_Rule (yes-man rate), the share of numbers in the output that match an Exhibit or cannot be verified, the mean latency, and the mean token count.
3. THE Benchmark SHALL report each rate with a Wilson 95 % confidence interval and a Confidence_Label: `Measured` when the intervals of the two arms do not overlap, `Indicative` when they overlap, and `Context` for figures that are not measured.
4. THE Benchmark SHALL write its results to `docs/benchmark.md` and `docs/benchmark.json`, and THE technical documentation and the demo SHALL use only these files for Benchmark figures.
5. THE Baseline_Agent SHALL use the same model, the same Guardrail, and the same Investor_Contract as the Guide_System, and SHALL receive no Toolkit, no Exhibits, and no other agent.
6. THE Benchmark SHALL include an ablation that reruns the Guide_System with each of the Advocate_Agent, the Investigator_Agent, and the Judge_Agent switched off in turn, and SHALL report what each removal changes: Options offered, material risks reported, and Verdicts changed by Soft_Preferences.
7. IF the ablation shows that removing an agent changes none of these measures beyond its confidence interval, THEN THE technical documentation SHALL state it and the team SHALL consider removing the agent.

### Requirement 35: Demo Resilience and Jury Access

**User Story:** As a datathon team, I want the demo to work for the jury after the AWS accounts close, so that a closed account or a live failure never costs the pitch.

#### Acceptance Criteria

1. THE Guide_System SHALL provide a pre-created demo user in the Identity_Provider, and THE submission SHALL include its sign-in name and password for the jury.
2. THE Guide_System SHALL export the SessionView, the Trace, and the Precedents of every demo case and every Benchmark case to `demo/sessions/` in the repository before Sunday 23:59.
3. THE UI SHALL provide a Replay_Mode that renders the exported SessionViews, including Friendly_Mode, Advanced_Mode, and the Appeal comparison, without calling the Session_API or any AWS service.
4. THE UI SHALL display a visible label "Replay of a recorded session" on every screen of the Replay_Mode, with the original session date and Snapshot_Id.
5. THE repository SHALL provide a command that builds the Replay_Mode as static files that open in a browser with no server and no network access.

### Requirement 36: Fixed Agent Flow, Bounds, and Fallbacks

**User Story:** As a datathon team, I want a simple, bounded agent flow that always ends with a valid Ruling, so that the demo is reliable and every agent has a clear purpose.

#### Acceptance Criteria

1. THE Tribunal_Orchestrator SHALL run, in this order and once each: the Profiler (code), the Risk_Panel and Hard_Rules of the request (code), the Advocate_Agent, the Risk_Panel and Hard_Rules of each Option (code), the Investigator_Agent, the Judge_Agent, and the Clerk template with the citation, guidance-only, and Guardrail checks (code).
2. THE agents SHALL never call one another; THE Tribunal_Orchestrator SHALL be the only component that passes data between stages.
3. THE Guide_System SHALL make at most 3 agent invocations per Tribunal_Session, not counting citation revisions bounded by Requirement 4.6, and SHALL apply a configured timeout to each invocation.
4. THE Guide_System SHALL validate every agent output against a JSON schema and SHALL treat an invalid output as a failed stage.
5. IF the Advocate_Agent fails, THEN THE Ruling SHALL offer only the request and the maximum weight within the contract computed by code.
6. IF the Investigator_Agent fails, THEN THE Ruling SHALL show the Risk_Panels without the material-risk explanation.
7. IF the Judge_Agent fails, THEN THE Verdict SHALL be the code result of the Hard_Rules with a template sentence in place of the narrative.
8. THE Ruling SHALL list which agents ran and which failed, and THE Verdict SHALL never depend on an agent succeeding.
