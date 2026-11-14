---
inclusion: fileMatch
fileMatchPattern: "guide/toolkit/**"
---
# Toolkit rules (apply only when editing guide/toolkit/)

- Every public function returns an `Exhibit` or a `ToolError`; a `ToolError` never touches the registry.
- Every Exhibit records: metric, value, period, assets, currency, source files, processing notes (FX carry-forward, calendar alignment and observation count, CNQ.TO 2022-08-22 note when relevant).
- Accept `as_of` and drop every observation after it.
- Test oracle (starter data, CAD, daily rebalanced, 2021-11-12 to 2026-11-12), Robert base portfolio XBB.TO 40 / ZST.TO 15 / XIU.TO 15 / SPY 15 / JNJ 8 / RY.TO 7:
  base vol 6.2 %, max DD -10.4 %; +30 % TSLA vol 19.5 %, max DD -31.0 %, TSLA share of variance about 87 %.
