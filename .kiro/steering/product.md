---
inclusion: always
---
# Product rules (always apply)

Product: VERDICT, a simulation-only "investment tribunal". A Prosecutor and a Defense argue a fictional investor's request with numbered Exhibits; a Judge rules against the investor's contract; a Clerk writes the Ruling.

1. **Numbers come only from code.** Agents never compute or recall a figure. Every number shown to a user comes from a Toolkit Exhibit (`guide/toolkit/`). If a figure has no Exhibit, it does not exist.
2. **Hard rules are decided by code** (`guide/tribunal/rules.py`). The model only weighs soft preferences and writes narrative.
3. **Guidance only.** No code, prompt, or UI element may place, route, prefill, or trigger an order, transfer, or bank/brokerage action. Simulation only, no personalized advice, no return prediction.
4. **Data:** returns from `adj_close`; amounts in CAD via `fx_usdcad_daily.csv` (carry the last rate forward); no observation after `as_of`; macro series lagged to publication date (`config.yaml`).
5. **Every Ruling answers the four questions** from National Bank's workshop: Which data? Why this choice? Which limits? What would change the answer?
6. **An agent never certifies its own work.** The orchestrator checks the Exhibit registry and the rule results, never an agent's self-report.
