---
inclusion: always
---
# Product rules (always apply)

The product is a simulation-only investment tribunal. A Prosecutor and a Defense argue a fictional investor's request with numbered Exhibits; a Judge rules against the investor's contract; a Clerk writes the Ruling.

1. **Numbers come only from code.** Agents never compute or recall a figure. Every number shown to a user comes from a Toolkit Exhibit. If a figure has no Exhibit, it does not exist.
2. **Hard_Rules are decided by code.** The model only weighs Soft_Preferences (Req. 29) and writes narrative; it never upgrades a Verdict.
3. **Guidance only.** No code, prompt, API route, or UI element may place, route, prefill, or trigger an order, transfer, or bank or brokerage action.
4. **Data:** returns from `adj_close`; amounts in CAD; no observation after `as_of`; macro series lagged to publication; every Exhibit names its Snapshot_Id.
5. **Every Ruling answers four questions** (Req. 33): Which data? Why this choice? Which limits? What would change the answer?
6. **An agent never certifies its own work.** The orchestrator checks the Exhibit registry and rule results, never an agent's self-report.
7. **Scope:** follow the Delivery Tiers in `requirements.md`. Do not start Tier 3 work before the Sunday 12:30 freeze.
