---
inclusion: always
---
# Product rules (always apply)

The product is a simulation-only investment tribunal. Code computes every Exhibit and decides every Hard_Rule. Three agents run in this order, like a court: the Advocate pleads Options that serve the investor's goal, the Investigator names the risks material for this investor, and the Judge alone decides the Verdict, weighing Soft_Preferences and writing the narrative. A code template (the Clerk) writes the Ruling. Agents never call each other (Req. 36).

1. **Numbers come only from code.** Agents never compute or recall a figure. Every number shown to a user comes from a Toolkit Exhibit. If a figure has no Exhibit, it does not exist.
2. **Hard_Rules are the law, checked by code; the Judge decides.** Code computes every rule result as evidence and publishes no verdict. The Judge decides the Verdict and may only adopt an Option that passes every Hard_Rule (code checks the ruling, one send-back). If the Judge fails, a labeled code fallback keeps the session valid.
3. **Guidance only.** No code, prompt, API route, or UI element may place, route, prefill, or trigger an order, transfer, or bank or brokerage action.
4. **Data:** returns from `adj_close`; amounts in CAD; no observation after `as_of`; macro series lagged to publication; every Exhibit names its Snapshot_Id.
5. **Every Ruling answers four questions** (Req. 33): Which data? Why this choice? Which limits? What would change the answer?
6. **An agent never certifies its own work.** The orchestrator checks the Exhibit registry and rule results, never an agent's self-report.
7. **Scope:** follow the Delivery Tiers in `requirements.md`. Do not start Tier 3 work before the Sunday 12:30 freeze.
