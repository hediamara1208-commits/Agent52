# Requirements Document

## Introduction

The Agentic Investment Guide is a simulation-only, self-explaining multi-agent system built for the AlphaForge AI datathon 2026. It helps a fictional investor judge a concrete investment request (for example, Robert's "I want to put 30% in TSLA") against an explicit investor contract.

The MVP is the Decision Tribunal. A Profiler Agent converts a persona or custom profile into a JSON Investor_Contract. A Prosecutor Agent and a Defense Agent argue for and against the request using only numbered Exhibits produced by deterministic Python tools. A Judge Agent checks the arguments against the Investor_Contract and the Challenge_Rules. A Clerk Agent writes the ruling and a sensitivity-based answer to "What would change the verdict?".

The Guide_System is a guidance website. It only guides: it never performs an action directly or indirectly, never places, routes, prefills, or triggers orders, transfers, or brokerage or bank actions, and never holds brokerage or bank credentials. The MVP is a Streamlit web application offering profile-based guidance in two modes: a Friendly_Mode with a visual courtroom scene and plain-language summaries, and an Advanced_Mode with full detail.

The Flight Simulator (Flight Director, Co-pilot, Behavior Analyst) is an optional stretch. It replays history from 2021-11-12 and compares stated risk tolerance with revealed risk tolerance. Two further optional stretch surfaces exist: a Companion_Extension that shows guidance beside a simulated brokerage or bank page while the user acts personally, and Alerts that notify the user of Dataset-derived market events affecting the simulated portfolio.

Evaluation of the ideaHedi.md concept, reflected in scope decisions:

- Strengths: separating what the investor says from what the system enforces (Investor_Contract); adversarial Prosecutor and Defense agents counter "yes-man AI" behavior and directly address the Robert persona; the "no exhibit, no argument" rule makes explanations verifiable; the Clerk's sensitivity calculation ties explanation to computation; the AWS mapping (Bedrock Guardrails, AgentCore Memory, AgentCore Observability) covers the 15% AWS criterion.
- Risks: seven or eight agents increase cost, latency, and demo complexity, while the jury favors simple, focused, verifiable approaches. The Flight Simulator needs a replay engine, stress-event detection, and persistent memory, which is a large build. Replay requires strict look-ahead control. Language models may invent numbers unless figures come from tools. The 5-year window and the survivorship-biased universe limit the strength of any conclusion. The dataset has no ESG scores, news, or fundamentals.
- Scope decisions: the Tribunal is the MVP; the Flight Simulator is optional stretch; all numerical facts come from deterministic tools that emit numbered Exhibits; agents may only cite Exhibits; Prosecutor and Defense are two role prompts over a shared toolkit, not separate infrastructure.

## Glossary

- **Guide_System**: The complete Agentic Investment Guide application, including agents, tools, UI, and AWS integration.
- **Profiler_Agent**: The agent that converts an investor conversation, persona, or form input into an Investor_Contract.
- **Prosecutor_Agent**: The agent that builds the case against an Investment_Request using Exhibits only.
- **Defense_Agent**: The agent that builds the strongest honest case for an Investment_Request using Exhibits only.
- **Judge_Agent**: The agent that checks arguments against the Investor_Contract and Challenge_Rules and issues a Verdict.
- **Clerk_Agent**: The agent that writes the Ruling and the sensitivity-based answer.
- **Flight_Director_Agent**: (Stretch) The agent that runs the historical replay and pauses at Stress_Events.
- **Copilot_Agent**: (Stretch) The agent that explains a Stress_Event using only data available on the replay date.
- **Behavior_Analyst_Agent**: (Stretch) The agent that compares stated and revealed risk tolerance.
- **Investor_Contract**: A JSON document holding explicit, checkable investor rules: maximum volatility, maximum tolerated drawdown, per-asset cap, per-asset-class cap, sector cap, crypto cap, ESG exclusions, and horizon in years.
- **Persona**: A fictional reference investor: Amira, Mateo, or Robert, as defined in /workshop/Agent52/data/context.md.
- **Investment_Request**: A request such as "put 30% of the portfolio in TSLA", made by a Persona or custom profile.
- **Toolkit**: The set of deterministic local Python functions that read the Dataset and compute metrics.
- **Exhibit**: A numbered, immutable record produced by a Toolkit function. It contains the metric name, value, period, assets, currency, data files used, and processing notes.
- **Exhibit_Registry**: The store of all Exhibits created during one Tribunal_Session.
- **Dataset**: The starter data in /workshop/Agent52/data (31 assets, 2021-11-12 to 2026-11-12, FX, macro series, corporate actions) plus any documented additions.
- **Tribunal_Session**: One run of Profiler, Prosecutor, Defense, Judge, and Clerk on one Investment_Request.
- **Verdict**: The Judge_Agent outcome: reject, accept, or accept with conditions.
- **Ruling**: The Clerk_Agent's plain-language document with sections Facts, Assumptions, Fictional scenarios, and Limits.
- **Challenge_Rules**: The rules that all outputs be simulation only, contain no personalized financial advice, contain no return predictions, and comply with the Guidance_Only_Rule.
- **Guidance_Only_Rule**: The Datathon rule that the Guide_System may only guide and SHALL NOT perform any action directly or indirectly. Prohibited are placing, routing, prefilling, or triggering orders, transfers, or any brokerage or bank action, and holding brokerage or bank credentials.
- **Friendly_Mode**: The UI mode that shows a visual courtroom scene with the Prosecutor_Agent, Defense_Agent, Judge_Agent, and Clerk_Agent and plain-language summaries.
- **Advanced_Mode**: The UI mode that shows full detail: Exhibits, per-rule table, Sensitivity_Analysis results, Trace, and JSON export.
- **Session_State**: The inputs, Investor_Contract, Tribunal_Session progress, Verdict, Ruling, Exhibits, and Trace held for the current browser session.
- **Companion_Extension**: (Stretch) A browser-extension-style component that displays guidance beside a Simulated_Brokerage_Page and reads only user-visible, user-provided request information.
- **Simulated_Brokerage_Page**: (Stretch) A locally hosted mock brokerage or bank page that contains no real account, no real credentials, and no connection to a real institution.
- **Alert**: (Stretch) A notification, labelled as guidance, that a Dataset-derived market event affects the simulated portfolio.
- **Market_Event**: (Stretch) An event detected from the Dataset, such as a Stress_Event or a single-day price move above a configured threshold.
- **Simulated_Portfolio**: A fictional portfolio defined by the user or Persona, used for the Flight Simulator and Alerts.
- **Sensitivity_Analysis**: A Toolkit computation that re-evaluates the Investor_Contract checks with one changed input (such as position size, horizon, or period) to find the threshold at which the Verdict changes.
- **Stress_Event**: (Stretch) A replay date on which a portfolio drawdown, rate change, or crypto decline exceeds a configured threshold.
- **Trace**: The recorded sequence of agent calls, tool calls, Exhibits, and Judge checks for a Tribunal_Session.
- **UI**: The Streamlit web application.
- **Guardrail**: An Amazon Bedrock Guardrails configuration enforcing the Challenge_Rules.
- **As_Of_Date**: The simulated date at which only information published on or before that date may be used.

## Requirements

### Requirement 1: Investor Contract Creation

**User Story:** As an investor, I want my goals translated into explicit rules, so that the system enforces what I need rather than only what I say.

#### Acceptance Criteria

1. WHEN a Persona is selected, THE Profiler_Agent SHALL produce an Investor_Contract in JSON containing risk level, horizon in years, maximum volatility, maximum tolerated drawdown, per-asset cap, crypto cap, sector caps, and ESG exclusions.
2. WHEN a custom-profile form is submitted, THE Profiler_Agent SHALL produce an Investor_Contract from the submitted values.
3. THE Guide_System SHALL validate each Investor_Contract against a JSON schema before any other agent uses the Investor_Contract.
4. IF an Investor_Contract fails schema validation, THEN THE Guide_System SHALL display the failing fields and withhold the Tribunal_Session from starting.
5. THE Profiler_Agent SHALL record for each contract field whether its value came from the Persona definition, the form input, or a stated default.
6. WHERE a Persona is Amira, THE Profiler_Agent SHALL set a per-asset-class cap and a diversification rule so that high risk tolerance does not permit unlimited concentration.
7. WHERE a Persona is Mateo, THE Profiler_Agent SHALL include ESG exclusion preferences and a speculative-asset limit in the Investor_Contract.
8. WHERE a Persona is Robert, THE Profiler_Agent SHALL set a horizon of 3 to 5 years and a crypto cap consistent with a low-to-moderate risk level.

### Requirement 2: Deterministic Toolkit and Exhibits

**User Story:** As a juror, I want every number traceable to a computation, so that I can verify what supports a conclusion.

#### Acceptance Criteria

1. THE Toolkit SHALL provide deterministic Python functions for annualized return, annualized volatility, maximum drawdown with peak and trough dates, correlation between two assets, drawdown during a named period, and portfolio-level metrics for a weighted position.
2. WHEN a Toolkit function is called, THE Guide_System SHALL create an Exhibit with a sequential number, metric name, value, period start, period end, assets, currency, source files, and processing notes, and store the Exhibit in the Exhibit_Registry.
3. THE Guide_System SHALL make each Exhibit immutable after creation.
4. WHEN the same Toolkit function is called with identical inputs, THE Toolkit SHALL return an identical value.
5. THE Toolkit SHALL compute returns from the adj_close column of prices_daily.csv.
6. IF a Toolkit function is called with a ticker absent from assets_universe.csv, THEN THE Toolkit SHALL return an error naming the ticker and SHALL create no Exhibit.
7. IF a requested period contains fewer than 20 price observations for an asset, THEN THE Toolkit SHALL return an insufficient-data error and SHALL create no Exhibit.
8. THE Toolkit SHALL expose each function to the agents as a Bedrock Converse API tool with a JSON input schema.

### Requirement 3: Data Handling and Quality

**User Story:** As a data reviewer, I want the data used correctly and its limits stated, so that conclusions are not misleading.

#### Acceptance Criteria

1. WHEN a Toolkit function combines assets quoted in different currencies, THE Toolkit SHALL convert prices to CAD using fx_usdcad_daily.csv and SHALL record the conversion in the Exhibit processing notes.
2. IF an FX rate is missing for a date, THEN THE Toolkit SHALL use the most recent earlier rate and SHALL record the carry-forward in the Exhibit processing notes.
3. WHEN a Toolkit function compares assets with different trading calendars, THE Toolkit SHALL align them on the dates on which all compared assets have a price and SHALL record the alignment method and the resulting observation count in the Exhibit.
4. WHEN a Toolkit function uses a monthly macro series, THE Toolkit SHALL treat the value as available only after the reference month plus a configured publication lag in days.
5. THE Guide_System SHALL define the publication lag for each macro series in a configuration file.
6. WHEN a Toolkit function is called with an As_Of_Date, THE Toolkit SHALL exclude every price and macro observation dated after the As_Of_Date.
7. WHEN an Exhibit involves CNQ.TO and its period includes 2022-08-22, THE Guide_System SHALL attach a note stating that the 1.021 split factor likely reflects a special distribution and is unverified.
8. WHEN an Exhibit includes a result derived from the Dataset, THE Guide_System SHALL attach the survivorship-bias limitation to the Ruling.
9. IF a request depends on ESG scores, news, or company fundamentals, THEN THE Guide_System SHALL report that the Dataset does not contain this information and SHALL label any related argument as unsupported by Exhibits.
10. THE Guide_System SHALL maintain a data-source document listing, for each source, its origin, retrieval date, processing, limitations, and terms of use.
11. WHERE external data is added to the Dataset, THE Guide_System SHALL add an entry for that data to the data-source document before any Exhibit uses the data.

### Requirement 4: Prosecutor and Defense Arguments

**User Story:** As an investor, I want a balanced adversarial analysis of my request, so that I receive more than agreement with what I asked for.

#### Acceptance Criteria

1. WHEN a Tribunal_Session starts, THE Prosecutor_Agent SHALL produce an argument against the Investment_Request in which each factual claim cites at least one Exhibit number.
2. WHEN a Tribunal_Session starts, THE Defense_Agent SHALL produce an argument for the Investment_Request in which each factual claim cites at least one Exhibit number.
3. THE Guide_System SHALL reject any Prosecutor_Agent or Defense_Agent claim that cites no Exhibit or cites an Exhibit number absent from the Exhibit_Registry.
4. WHEN a claim is rejected for a missing or invalid citation, THE Guide_System SHALL return the rejected claim to the originating agent for revision, up to 2 revision attempts.
5. IF a claim still has no valid citation after 2 revision attempts, THEN THE Guide_System SHALL remove the claim from the argument and record the removal in the Trace.
6. THE Guide_System SHALL verify that every number in an argument matches the value of the cited Exhibit.
7. THE Defense_Agent SHALL consider the effect of a reduced position size on the Investor_Contract checks in the Defense argument.
8. THE Prosecutor_Agent and THE Defense_Agent SHALL use the same Toolkit and the same Exhibit_Registry.

### Requirement 5: Judge and Governance

**User Story:** As an investor, I want a governance check against my own contract and the challenge rules, so that results are consistent and safe.

#### Acceptance Criteria

1. WHEN the Prosecutor_Agent and Defense_Agent arguments are complete, THE Judge_Agent SHALL evaluate the Investment_Request against each Investor_Contract rule using Exhibit values and SHALL record a pass or fail result per rule.
2. THE Judge_Agent SHALL issue a Verdict of reject, accept, or accept with conditions.
3. WHEN the Verdict is accept with conditions, THE Judge_Agent SHALL state each condition as a numeric limit, such as a maximum position size in percent.
4. IF any Investor_Contract rule fails and no numeric condition can satisfy every failed rule, THEN THE Judge_Agent SHALL issue a Verdict of reject.
5. IF the Judge_Agent identifies missing evidence for a rule, THEN THE Judge_Agent SHALL return a named evidence request to the Prosecutor_Agent or Defense_Agent, up to 2 times per Tribunal_Session.
6. IF evidence for a rule is still missing after the evidence requests, THEN THE Judge_Agent SHALL list the rule as unverified in the Verdict.
7. THE Guide_System SHALL apply a Guardrail to every model input and output that blocks real-trade instructions, personalized financial advice, return predictions, and any output that violates the Guidance_Only_Rule.
8. IF the Guardrail blocks a model output, THEN THE Guide_System SHALL record the block in the Trace and display a message stating which Challenge_Rule applied.
9. THE Judge_Agent SHALL compute the pass or fail result of each Investor_Contract rule with deterministic code, and THE Judge_Agent SHALL use the language model only for the narrative of the Verdict.
10. WHEN a Persona has a risk level of low to moderate and the Investment_Request exceeds a per-asset cap, THE Judge_Agent SHALL state the tension between the request and the Investor_Contract in the Verdict.
11. WHEN the Judge_Agent evaluates arguments, THE Judge_Agent SHALL check each Prosecutor_Agent, Defense_Agent, and Clerk_Agent output against the Guidance_Only_Rule and SHALL record a pass or fail result in the Trace.
12. IF an agent output fails the Guidance_Only_Rule check, THEN THE Judge_Agent SHALL remove the offending statement from the Ruling and SHALL record the removal in the Trace.

### Requirement 6: Clerk Ruling and Sensitivity

**User Story:** As an investor, I want a plain-language ruling that shows what would change the outcome, so that I understand the decision and its limits.

#### Acceptance Criteria

1. WHEN the Judge_Agent issues a Verdict, THE Clerk_Agent SHALL produce a Ruling with the sections Facts, Assumptions, Fictional scenarios, and Limits.
2. THE Clerk_Agent SHALL cite an Exhibit number for each statement in the Facts section.
3. THE Clerk_Agent SHALL list every assumption in the Assumptions section, including period, currency, and calendar alignment choices.
4. THE Clerk_Agent SHALL label each hypothetical item in the Fictional scenarios section as a simulation.
5. THE Ruling SHALL include a section titled "What would change the verdict" containing at least one Sensitivity_Analysis result.
6. WHEN the Ruling is produced, THE Toolkit SHALL run the Sensitivity_Analysis by re-evaluating the Investor_Contract rules with varied position size, varied horizon, and the 2022 drawdown period, and SHALL store each result as an Exhibit.
7. THE Ruling SHALL state the threshold value at which the Verdict changes for each varied input, or state that no change occurs within the tested range.
8. THE Ruling SHALL include the statements that the output is a simulation, is not personalized financial advice, and does not predict future returns.
9. THE Ruling SHALL present volatility as one risk indicator and SHALL reference at least one further factor from horizon, diversification, or stated preferences.

### Requirement 7: Streamlit User Interface

**User Story:** As an investor or juror, I want an interface that is friendly to follow and detailed to verify, so that I can understand a Tribunal_Session at a glance and inspect the evidence in depth.

#### Acceptance Criteria

1. THE UI SHALL provide a persona picker with the options Amira, Mateo, and Robert.
2. THE UI SHALL provide a custom-profile form with fields for risk level, horizon in years, maximum volatility, maximum drawdown, per-asset cap, crypto cap, and ESG exclusions.
3. THE UI SHALL provide a request box that accepts a free-text Investment_Request.
4. WHEN the user submits an Investment_Request, THE UI SHALL start a Tribunal_Session and display progress for each agent stage.
5. WHEN a Tribunal_Session completes, THE UI SHALL display the Verdict, the Ruling, and the per-rule pass or fail table.
6. THE UI SHALL render each Exhibit citation in the Ruling and arguments as a clickable element that opens the Exhibit details.
7. THE UI SHALL provide a trace panel showing the ordered agent calls, tool calls, Exhibits created, Judge checks, and Guardrail blocks of the Tribunal_Session.
8. THE UI SHALL display a persistent banner stating that the output is a simulation and not financial advice.
9. THE UI SHALL provide a Friendly_Mode and an Advanced_Mode and SHALL offer a control to switch between them.
10. WHILE the UI is in Friendly_Mode, THE UI SHALL display a courtroom scene showing the Prosecutor_Agent, Defense_Agent, Judge_Agent, and Clerk_Agent.
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

### Requirement 8: AWS Integration

**User Story:** As a datathon team, I want a solid AWS integration, so that the solution scores on the AWS criterion and runs in a deployable form.

#### Acceptance Criteria

1. THE Guide_System SHALL invoke every agent through the Amazon Bedrock Converse API with tool use.
2. THE Guide_System SHALL apply an Amazon Bedrock Guardrail configuration to model calls.
3. THE Guide_System SHALL emit Traces to AgentCore Observability for each Tribunal_Session.
4. THE Guide_System SHALL store the Investor_Contract and session summaries in AgentCore Memory, keyed by a profile identifier.
5. WHERE the Guide_System is deployed, THE Guide_System SHALL read the Dataset files from Amazon S3.
6. WHERE the Guide_System runs locally, THE Guide_System SHALL read the Dataset files from the local /workshop/Agent52/data directory.
7. THE Guide_System SHALL read AWS region, model identifier, Guardrail identifier, S3 bucket name, and data location from configuration, and SHALL contain no credentials in source code or logs.
8. IF a Bedrock call fails with a throttling error, THEN THE Guide_System SHALL retry up to 3 times with exponential backoff before reporting a stage failure.
9. THE Guide_System SHALL grant each AWS component only the permissions needed for its function.

### Requirement 9: Observability and Explainability Traces

**User Story:** As a juror, I want an inspectable court record, so that I can verify that explanations match observed actions.

#### Acceptance Criteria

1. THE Guide_System SHALL record in the Trace each agent invocation, with agent name, input summary, output summary, and timestamp.
2. THE Guide_System SHALL record in the Trace each Toolkit call with its arguments and the resulting Exhibit number.
3. THE Guide_System SHALL record in the Trace each Judge rule check with its inputs and result.
4. WHEN a Tribunal_Session completes, THE Guide_System SHALL export the Trace as a JSON file.
5. THE Guide_System SHALL provide for each statement in the Ruling a link chain from statement to Exhibit to source data files in the Trace.
6. THE Guide_System SHALL exclude detailed internal model reasoning from the Ruling and the Trace.

### Requirement 10: Validation and Testing

**User Story:** As a developer, I want automated checks, so that I can show that results and explanations are faithful to the data.

#### Acceptance Criteria

1. THE Guide_System SHALL include unit tests for each Toolkit function with fixed input data and expected outputs.
2. THE Guide_System SHALL include a test that fails if any Toolkit function returns a value using an observation dated after the As_Of_Date.
3. THE Guide_System SHALL include a test that verifies each number in a Ruling matches its cited Exhibit.
4. THE Guide_System SHALL include a test that runs a Tribunal_Session for Robert with the request "30% in TSLA" and verifies that the Verdict is not an unconditional accept.
5. THE Guide_System SHALL include a test that runs a Tribunal_Session for Amira with a crypto-heavy request and verifies that the Judge_Agent applies a per-asset-class cap.
6. THE Guide_System SHALL include a test that runs a Tribunal_Session for Mateo and verifies that the Ruling reports the absence of ESG scores in the Dataset.
7. THE Guide_System SHALL include a test that verifies the CNQ.TO split-anomaly note is attached to any Exhibit whose period includes 2022-08-22.
8. THE Guide_System SHALL include a sensitivity test that verifies the reported threshold flips the Verdict when applied.

### Requirement 11: Deliverables and Documentation

**User Story:** As a datathon team, I want all required deliverables prepared, so that the submission is complete.

#### Acceptance Criteria

1. THE Guide_System SHALL include a README documenting dependencies, data sources, configuration, and startup and reproduction instructions.
2. THE Guide_System SHALL include technical documentation covering methods, justification of technologies, assets used, processing, assumptions, the explainability mechanism with one worked example linking a conclusion to Exhibits and Trace entries, validations, limits, and planned improvements.
3. THE Guide_System SHALL include a one-page summary covering the problem, the agentic approach, originality, data sources, explanation capability, and user benefits.
4. THE Guide_System SHALL include a demo script for a video of about 5 minutes showing two contrasting Personas end to end, with Robert and Amira as the default pair.
5. THE Guide_System SHALL state in the README and the one-page summary that the system is a simulation, is not personalized financial advice, and does not predict returns.

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

1. THE Guide_System SHALL comply with the Guidance_Only_Rule in every component, agent, and delivery surface.
2. THE Guide_System SHALL contain no function that places, routes, prefills, or triggers an order, transfer, or brokerage or bank action.
3. THE Guide_System SHALL hold no brokerage or bank credentials, API keys, or session tokens.
4. THE Guide_System SHALL contain no integration with a brokerage or bank API.
5. THE Guardrail SHALL block any model input or output that instructs, requests, or simulates the execution of a real order, transfer, or brokerage or bank action.
6. IF the Guardrail or the Judge_Agent detects a Guidance_Only_Rule violation, THEN THE Guide_System SHALL block the output, record the block in the Trace, and display a message stating that the Guide_System only provides guidance.
7. THE Guide_System SHALL phrase each recommendation-like statement in the Ruling as guidance for the user to consider and decide personally.
8. THE Guide_System SHALL include a test that verifies the Guardrail and Judge_Agent block outputs that instruct or trigger an order, transfer, or brokerage or bank action.
9. THE Guide_System SHALL include a test that verifies the source code and configuration contain no brokerage or bank credentials and no brokerage or bank API client.
10. THE Guide_System SHALL state the Guidance_Only_Rule in the README, the technical documentation, and the one-page summary.

### Requirement 14: Companion Extension (Optional Stretch)

**User Story:** As an investor, I want guidance displayed beside the page where I act, so that I can consider the guidance while I make my own decision.

#### Acceptance Criteria

1. WHERE the Companion_Extension is enabled, THE Companion_Extension SHALL display guidance in a side panel next to a Simulated_Brokerage_Page.
2. WHERE the Companion_Extension is enabled, THE Companion_Extension SHALL read only the information that is visible on the Simulated_Brokerage_Page and was entered by the user, limited to the ticker and the position size.
3. WHERE the Companion_Extension is enabled, WHEN the user enters a ticker and a position size, THE Companion_Extension SHALL send the ticker and position size to the Guide_System as an Investment_Request and SHALL display the Verdict and a plain-language summary.
4. WHERE the Companion_Extension is enabled, THE Companion_Extension SHALL operate only on Simulated_Brokerage_Pages and SHALL connect to no real brokerage or bank account.
5. WHERE the Companion_Extension is enabled, THE Companion_Extension SHALL leave every field, button, and form of the Simulated_Brokerage_Page unmodified.
6. WHERE the Companion_Extension is enabled, THE Companion_Extension SHALL read no credentials, account numbers, balances, or cookies from the page.
7. WHERE the Companion_Extension is enabled, THE Companion_Extension SHALL provide a link that opens the full Tribunal_Session in the UI.
8. WHERE the Companion_Extension is enabled, THE Companion_Extension SHALL display the banner stating that the output is a simulation and not financial advice, and that the user acts personally.
9. WHERE the Companion_Extension is enabled, IF the ticker or the position size is missing or cannot be parsed, THEN THE Companion_Extension SHALL display a message naming the missing value and SHALL not send an Investment_Request.

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
10. WHERE Alerts are enabled, THE Guide_System SHALL include in each Alert a statement that the Alert is based on the Dataset and not on live news or live market data.
