Part 1: The Flight Simulator (revealing real risk tolerance)

1. Profiler Agent

Role: talks with the investor (or loads a persona: Amira, Mateo, Robert) and turns their goals into explicit, checkable rules. Examples: max volatility, max tolerated drawdown, caps per asset, sector and crypto, ESG exclusions, horizon.
Output: a structured “investor contract” (JSON) that every other agent must respect.
Why it exists: it separates what the person says from what the system enforces.

2. Flight Director Agent (orchestrator of the replay)

Role: runs the time machine. It starts the investor on Nov 12, 2021 with a fictional portfolio and advances week by week through real history. It detects turbulence moments (a sharp drawdown, a rate hike, a crypto collapse) and pauses the simulation there.
Tools: portfolio_value(as_of), market_snapshot(as_of), detect_stress_events().
Why it exists: it decides when the investor must face a decision, which is the agentic part.

3. Co-pilot Agent (coach)

Role: at each pause, explains what is happening using only information available on that date (“Your portfolio is down 18%; stocks and bonds fell together because rates rose”). Then it asks: hold, sell, or buy more?
Why it exists: it makes the experience educational and engaging rather than a static report.

4. Behavior Analyst Agent

Role: records each reaction and compares stated tolerance against revealed tolerance. For example: “You said high risk, but you sold everything at –15%.” It then updates the investor contract.
AWS: stored in AgentCore Memory, so the profile improves across sessions.
Why it exists: “risk tolerance ≠ risk capacity” is the key idea from National Bank’s presentation.
Part 2: The Decision Tribunal (judging a concrete request)

The investor makes a request, such as Robert’s “I want to put 30% in TSLA”.

5. Prosecutor Agent

Role: builds the case against the request. It may only use exhibits produced by the toolkit, for example “Exhibit 12: TSLA volatility 58%, max drawdown –73% over 2021–2026”.

6. Defense Agent

Role: builds the strongest honest case for the request (growth potential, diversification effect if the position is small). It is subject to the same rule: no exhibit, no argument.
Why two opposing agents: it forces a balanced analysis and avoids the “yes-man AI” problem. The Robert persona tests exactly that.

7. Judge Agent (governance)

Role: checks both arguments against the investor contract and the challenge rules (simulation only, no personalized advice). It can reject, accept, or accept with conditions (e.g. “5% maximum instead of 30%”). It flags missing data and can send the Prosecutor or Defense back for more evidence.
AWS: Bedrock Guardrails enforce hard rules (no real trades, no personalized advice).

8. Clerk Agent (explainability)

Role: writes the final ruling in plain language, separated into Facts / Assumptions / Fictional scenarios / Limits. Each fact cites its exhibit. It always answers: “What would change the verdict?”, backed by a real sensitivity calculation, for example “If your horizon were 10+ years, a 10% position would pass”.
AWS: AgentCore Observability traces become the “court record” the user can inspect.