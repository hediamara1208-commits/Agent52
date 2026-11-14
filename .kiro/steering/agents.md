---
inclusion: fileMatch
fileMatchPattern: "guide/agents/**"
---
# Agent rules (apply only when editing guide/agents/)

Each agent is a specialist with a written job, a written NOT, and bounded tools.

| Agent | Job | NOT | Tools |
|---|---|---|---|
| Prosecutor | Strongest case against the request | Never invents a number; never gives advice | Read-only Toolkit |
| Defense | Strongest honest case for the request, including a smaller position | Same | Read-only Toolkit |
| Judge | Weighs soft preferences; writes the verdict narrative from code results; cites the closest precedent | Never overrides a hard-rule result; never calls the Toolkit | None (receives rule results, anonymized arguments, precedent) |
| Clerk | Fills the Ruling template | Never adds a fact without an Exhibit | Sensitivity tool only |

Agents return structured JSON (`claims: [{text, citations, numbers}]`). When the citation validator rejects a claim, the next attempt receives the named defect ("claim 2 cites Exhibit 14, which does not exist; do not repeat it").
