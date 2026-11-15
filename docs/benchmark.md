# Benchmark: the Tribunal versus a single agent

Run on Sunday 2026-11-15, 11:05–11:20 ET, against the deployed system (AgentCore Runtime v15, Bedrock `us.anthropic.claude-sonnet-5-5`, Guardrail `verdict-guardrail`, Dataset_Snapshot `20261115T154221Z-esg`, live AgentCore Web Search).

Confidence labels follow the plan: **Measured** (counted on every run), **Indicative** (5 runs per case, enough to show a pattern, not a statistical claim), **Context** (explanation, not a measurement).

## Method

- **6 demo cases × 5 runs = 30 Tribunal sessions** through the public Session_API (same path as the web app). Each case has an expected verdict computed by code from the investor's contract and the snapshot (`demo/cases.yaml`, `tests/test_demo_cases.py`).

| Case | Investor | Request | Expected (code) |
|---|---|---|---|
| robert_tsla | Robert, low-to-moderate, 3–5 y | 30% TSLA | accept with conditions, max 5% |
| robert_appeal | Robert, speculative limit raised to 10% | 30% TSLA | accept with conditions, max 10% |
| amira_tsla | Amira, high risk, 15 y+ | 30% TSLA | accept with conditions, max 15% |
| mateo_xom | Mateo, ESG fossil-fuel screen | 10% XOM | reject |
| amira_btc | Amira (already holds BTC) | 40% BTC-USD | accept with conditions, max 5.5% |
| robert_spy | Robert | 2% SPY | accept |

- **Single-agent baseline, 2 × 30 calls:** one Bedrock Converse call per run, same model, same Guardrail, same Investor_Contract JSON, the prompt "You are an investment assistant", no tools, no data, no other agent (`docs/benchmark/baseline_converse.py`, contracts in `docs/benchmark/contracts.json`).
  - **Baseline A** applies the Guardrail to the whole prompt (the naive setup).
  - **Baseline B** scopes the Guardrail to the user's request text with `guardContent`, exactly as the Tribunal does, so the comparison is fair.

## Results

| Metric | Tribunal (30 runs) | Baseline A | Baseline B |
|---|---|---|---|
| Runs that produced a verdict | **30/30** | 10/30 (20 blocked by the Guardrail input filter) | 30/30 |
| Verdict class equals the expected one | **30/30** | 5/30 | 5/30 |
| Accepts a compliant request (robert_spy) | **5/5 accept** | 0/5 (accept with conditions) | 0/5 (accept with conditions) |
| Offers a lawful smaller size instead of only refusing (4 sizing cases) | **20/20** | 0/20 | 0/20 (rejects all) |
| Proposed size ≤ the code-computed maximum | **25/25** | n/a | n/a |
| Final decision made by the Judge agent (not the code fallback) | **30/30** | n/a | n/a |
| Numbers stated with no evidence behind them | **0** (citation validator) | ≈ 2–18 % figures per answer, none traceable | ≈ 2–18 per answer, none traceable |
| Recent news used as cited evidence (sessions with ≥ 1 risk citing a Web Exhibit) | **30/30** (6 Web Exhibits per session) | none | none |
| Median latency | 73 s (52–78) | 0.3 s blocked / ~5 s | ~5 s |

Labels: verdict counts, Judge decisions, lawfulness and news citations are **Measured**; stability below is **Indicative**.

### Stability (Indicative, 5 runs per case)

| Case | Verdict class (5 runs) | Sizes adopted by the Judge | Code maximum |
|---|---|---|---|
| robert_tsla | 5 × accept with conditions | 3%, 3%, 3%, 2%, 2% | 5% |
| robert_appeal | 5 × accept with conditions | 5% × 5 | 10% |
| amira_tsla | 5 × accept with conditions | 10% × 5 | 15% |
| mateo_xom | 5 × reject | – | – |
| amira_btc | 5 × accept with conditions | 5.5%, 3%, 5.5%, 3%, 5.5% | 5.5% |
| robert_spy | 5 × accept | 2% × 5 | 2% (as requested) |

The verdict class never changed across runs. The size varies inside the lawful range: the Judge often picks a more cautious Option than the code maximum (e.g. 2–3% for Robert, whose soft preferences are "stability and quality"), and always explains why in its reason.

## What this shows (Context)

- **The agents decide, the code guards.** All 30 rulings were made by the Judge after the Advocate's options and the Investigator's risks; the code only enforced the investor's limits and never had to fall back.
- **Constructive, not just cautious.** A single agent with the same model and contract either refused (20/30 blocked or rejected) or attached conditions to a request that already complied. The Tribunal said *no* to Mateo's XOM, *yes* to a compliant SPY request, and *yes at a lawful size* to the four oversized requests.
- **Verifiable.** Every number in a Tribunal ruling is tied to a numbered Exhibit (data file, column, period, or web source with a link). The baseline's percentages cannot be checked.
- **Media hype handled.** In every session, at least one Investigator risk cited a recent news Exhibit (for Robert, the reported SpaceX–Tesla merger), and the Judge kept the decision tied to the contract.

## Limits

- 5 runs per case is small; the stability figures are indicative.
- Latency is ~15× the baseline (≈ 70 s for 3–4 model calls, Toolkit calls, web search and checks). Acceptable for a considered decision, not for chat.
- Token cost of Tribunal sessions was not measured in this run (the baseline used ≈ 750–1,150 tokens per call).
- The Advocate failed on the 5 robert_spy runs (it proposed another asset while the scope allows only a smaller size of the requested one). The request itself was lawful, so the Judge still accepted it; the Advocate's prompt should allow "no alternative needed" when the request already passes.
- Baseline A's blocks come from applying a prompt-attack filter to a long structured prompt; Baseline B removes that effect.
