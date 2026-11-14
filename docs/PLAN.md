# VERDICT: build plan to win the AlphaForge AI Datathon

Plan written Saturday 2026-11-14, 15:00. Owner of this file: the whole team. Update the checkboxes as you go.

## 0. What wins (from every source we have)

| Source | What it tells us | How the plan uses it |
|---|---|---|
| Official case + grid | Solution 20, Agentic & explainability 20, Data 20, AWS 15 (eligibility condition), Pitch 15, UX 10. "Simple, focused, verifiable" beats complexity. | Every phase ends with something the jury can see. No decorative agent. |
| National Bank finance workshop | Objective before product; return, risk, and horizon go together; diversification means exposures, not number of names; the investor sets the limits; a credible proposal answers 4 questions. | The Ruling is structured on the 4 questions: Which data? Why this choice? Which limits? What would change the answer? |
| National Bank example (slide 13) | "My portfolio is very Canadian: would XSP improve my diversification?" | One demo case must end in **accept**: not every verdict is a rejection. |
| AWS workshop 1 | Bedrock, Guardrails, Knowledge Bases, AgentCore (Runtime, Memory, Observability), Strands, Kiro; region us-east-1; save everything outside AWS; record the video while accounts are live. | Architecture in section 3. Backups in Phase 5. |
| Last year's winner | Won the **AWS architecture** prize with event-driven Lambdas and document bases. | A clean, justified architecture diagram is a scoring asset. |
| Workshop 2 (10 levels) | Instructions that name the case; scoped rules; specialized agents with bounded tools; deterministic scripts for numbers; guards that **block**, not remind; the chef checks the disk, never the self-report; named-defect memory loop; **measure everything, with a confidence level**. | Used twice: to **build** (Kiro steering, hooks) and in the **product** (section 2). Our evaluation benchmark copies the workshop's method. |

**Our pitch in one line:** "Other AI tools imitate a trading desk. VERDICT puts your request on trial, with evidence, and protects you from your own biases."

## 1. The demo we are building toward (5-minute video)

1. **Robert** (59, retiring in 3 to 5 years): "Put 30 % in TSLA."
   - Prosecutor: Exhibit, TSLA would carry 87 % of portfolio risk; max drawdown goes from -10.4 % to -31.0 %.
   - Defense: Exhibit, annualized return 8.1 % to 11.0 % (past data), and a smaller position.
   - Live objection: one unsourced number gets struck from the record.
   - **Verdict:** rejected at 30 %, accepted with conditions at about 5 % (computed).
   - **Appeal:** "What if I retire in 10 years?" Side-by-side verdicts.
2. **Amira** (26, high risk): same request. Different verdict, and the Judge **cites Robert's precedent** to explain why.
3. **Mateo** (41, ESG): "Add XOM." ESG exclusion with its source; cost of the conviction shown as an Exhibit.
4. **A Canadian-heavy portfolio adds SPY or XIU** (National Bank's example): **accepted**, because diversification improves.
5. Closing: the benchmark slide. "Single-agent baseline said yes to Robert X/10 times; VERDICT 0/10."

## 2. Workshop 2 levels applied to our product

| Level | In VERDICT |
|---|---|
| 1-2 Instructions, scoped rules | `.kiro/steering/` (product, tech, toolkit, agents). Kiro follows them when generating code. |
| 3 Specialized agent | Each agent has a job, a written NOT, bounded tools (see `agents.md`). The Judge has **no** Toolkit access. |
| 4 Skill | The Ruling template and the persona contracts live in files loaded on demand, not in every prompt. |
| 5 Template + script | Numbers come from the Toolkit; the Ruling is a template; the verdict on hard rules is code. |
| 6 Guard that blocks | Bedrock Guardrails + the deterministic guidance-only check + the citation validator **block** output; prompts also **say** the rule (workshop: tell AND block). |
| 7 Chef checks the disk | The orchestrator checks the Exhibit registry and rule results; it never trusts an agent saying "done" or "verified". |
| 8 Scripted pipeline | Plain Python orchestrator holds the loop (profile, arguments, validation, judge, clerk), capped revisions. |
| 9 Self-correction | Citation validator sends back a **named defect**, up to 2 revisions, then strikes the claim and records it. |
| 10 Memory + measurement | Precedents (DynamoDB) and contracts (AgentCore Memory). Benchmark with N runs per case, a **blind control arm** (single-agent baseline), and confidence labels **Measured / Indicative / Context** on every result. |

## 3. Target architecture

```
Streamlit UI (App Runner)
   └─> Tribunal orchestrator (Python; target: AgentCore Runtime; fallback: same container)
         ├─ Bedrock Converse + Guardrail  (Sonnet 4.5: Judge, Clerk; Haiku 4.5: Prosecutor, Defense)
         ├─ Toolkit (deterministic) ── S3 (dataset)
         ├─ Exhibit registry + Precedents ── DynamoDB
         ├─ Investor contracts ── AgentCore Memory
         ├─ Traces ── AgentCore Observability / CloudWatch
         └─ ESG sources ── documented CSV (stretch: Bedrock Knowledge Base)
```
Decision gate Sunday 10:00: if AgentCore Runtime is not working, everything runs in the App Runner container. Do not lose more than 1 hour on it.

## 4. Team roles

| Role | Owns | Main folders |
|---|---|---|
| **A: Data & Toolkit** | Exhibits, metrics, base portfolios, risk contribution, max-weight search, ESG CSV, data-source doc | `guide/toolkit/`, `guide/data/`, `docs/data_sources.md` |
| **B: Agents & Tribunal** | Bedrock wrapper, Guardrail, prompts, citation validator, rules, Judge, Clerk, orchestrator, appeal, precedents | `guide/agents/`, `guide/tribunal/` |
| **C: UI & AWS deploy** | Streamlit (courtroom view + advanced view), Docker, App Runner, S3, DynamoDB, IAM | `guide/ui/`, `deploy/` |
| **D: Evidence & story** | Persona contracts, test cases, benchmark, README, technical doc, one-pager, video script, pitch | `personas.yaml`, `tests/scenarios/`, `docs/` |

Rule: one owner per folder at a time. Pull before you start, push every hour.

## 5. Schedule and gates

### Phase 0: Align (Sat 15:00 to 16:00)
- [ ] Merge PR #1 (spec review + steering + this plan); everyone `git pull`.
- [ ] Final product name.
- [ ] AWS: in the Bedrock console, check model access for Claude Sonnet 4.5 and Haiku 4.5 in us-east-1; copy the exact model IDs into `config.yaml`.
- [ ] Create the S3 bucket and upload `data/`; create the DynamoDB table `verdict-precedents`.
- [ ] Create the Bedrock Guardrail (denied topics: real trades and transfers, personalized advice, return predictions); put its ID in `config.yaml`.
- **Gate:** one `converse` call with the Guardrail works from a notebook or Kiro terminal.

### Phase 1: Deterministic core (Sat 16:00 to 20:00)
- [ ] A: tasks 2 to 4 + 17 (contracts, Exhibits, metrics, base portfolios, `risk_contribution`, `portfolio_comparison`), max-weight bisection, test oracle passing.
- [ ] B: task 6 (trace recorder, Bedrock wrapper with Guardrail and retry), task 7.3 (citation validator with named defects), task 7.5 (rules).
- [ ] C: UI skeleton reading a **mock session JSON** (so UI work never waits for agents); Dockerfile.
- [ ] D: persona contracts (hard rules + soft preferences + base portfolios), 10 benchmark cases with expected verdict, ESG exclusion CSV with sources.
- **Gate (20:00):** `pytest` green; for Robert +30 % TSLA, the code alone prints the rule table and the conditional max weight.

### Phase 2: First full trial (Sat 20:00 to 01:00)
- [ ] B: Prosecutor, Defense, Judge (anonymized, shuffled arguments), Clerk template with the 4 questions; orchestrator end to end.
- [ ] C: courtroom view wired to the real session; Exhibit links; trace panel.
- [ ] D: run the 3 personas, log what is wrong, feed named defects back to B.
- **Gate (01:00), milestone M1:** Robert's full trial runs end to end in the UI locally. Save the session JSON as a demo fallback.

### Phase 3: Differentiators (Sun 08:00 to 12:30)
- [ ] B: appeal + diff; precedents (DynamoDB) cited by the Judge; AgentCore Memory for contracts.
- [ ] C: deploy on App Runner (S3, DynamoDB, role); appeal view side by side; try AgentCore Runtime (gate 10:00).
- [ ] D: **benchmark**: 10 cases × 5 runs, VERDICT vs a single-agent baseline (same model, one prompt, no tools); report verdict stability and the "yes-man" rate with confidence labels.
- [ ] A: Observability traces; sensitivity Exhibits (position size, horizon, 2022 period).
- **Gate (12:30), FEATURE FREEZE:** the 5 demo cases work on the deployed URL.

### Phase 4: Polish and record (Sun 12:30 to 16:00, on site)
- [ ] UX pass: the plain-language view must make sense to someone who has never seen the project.
- [ ] Record the raw demo video **on the deployed app** (AWS accounts close Monday 13:59).
- [ ] Ask the AWS and National Bank mentors on site to try the app; note their reactions for the pitch.

### Phase 5: Submit code (Sun 16:00 to 23:59)
- [ ] README: run instructions, data sources, architecture diagram with one line of justification per AWS service, guidance-only and simulation statements.
- [ ] Export traces, precedents table, and session JSONs into the repo (`demo/`).
- [ ] Push GitHub and the app link before **23:59**.

### Phase 6: Documents (Mon 08:00 to 13:00)
- [ ] Technical doc: methods, data treatment, explainability with one worked example (statement → Exhibit → source file → trace), benchmark results, limits.
- [ ] One-pager.
- [ ] Final video edit (about 5 minutes).
- [ ] Submit everything by **13:00** (deadline 14:00). Last AWS check before 13:59.

### Phase 7: If finalist (Tue to Fri 20)
- [ ] Pitch deck, rehearsal × 3, answers to likely questions (why debate, why not a single agent, data limits, business model for National Bank's direct brokerage).

## 6. Using Kiro well (Workshop 2 in practice)
- Steering files in `.kiro/steering/` are loaded automatically; scoped ones (`fileMatch`) only for their folder. Keep them short: a rule that names the case beats a long file.
- Run Kiro task by task and **check the result on disk** (tests, Exhibit values), never the agent's summary.
- Add a Kiro hook: on save in `guide/**`, run `pytest -q` (a guard that blocks, not one that reminds).
- When Kiro gets something wrong twice, write the named rule into the relevant steering file.

## 7. Risks and fallbacks
| Risk | Fallback |
|---|---|
| Bedrock throttling or model access | Haiku for every agent; cached session JSON to replay the demo |
| App Runner problems | EC2 with Docker, or Streamlit in SageMaker Studio with a public URL |
| AgentCore Runtime takes too long | Run the orchestrator in the app container (gate Sun 10:00) |
| Debate looks decorative | Soft preferences decided by the Judge from the arguments; benchmark against a single agent |
| Live demo fails during the pitch | Recorded video plus replay mode from saved session JSON |
| AWS accounts close | Everything exported to GitHub by Sunday 23:59 |
