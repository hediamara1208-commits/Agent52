# Data sources

## ESG exclusion list

| Field | Documented value |
| --- | --- |
| Dataset file | `data/esg_exclusions.csv` |
| Source | [Vanguard ESG U.S. Stock ETF summary prospectus](https://fund-docs.vanguard.com/F4393.pdf), which describes exclusion screens for fossil-fuel activities and specified controversial activities. |
| Retrieval date | 2026-11-14 |
| Method | The project team manually applied a narrow, issuer-level fossil-fuel screen to every ticker in `assets_universe.csv`. Direct oil and gas exploration, production, refining, transportation, and distribution are marked `excluded=true`. All other assets are marked `false` unless a direct match is documented. ETF holdings are not assessed. Each row repeats the source URL and retrieval date so a Ruling can cite its provenance. |
| Processing and snapshot use | The CSV is a hand-authored source file. `scripts/add_reference_table.py` adds it to a new immutable Dataset_Snapshot as the `esg_exclusions` reference table (raw CSV + Parquet, SHA-256 in the Snapshot_Manifest, all market files carried over unchanged) and moves the current pointer; Toolkit and Hard_Rule loading read the pinned snapshot copy. No market data is downloaded or changed by this file. |
| Limitations | This is a simplified binary exclusion proxy, not an ESG score, ESG rating, controversy database, sustainability assessment, or a prediction. It does not assess ETF holdings, indirect exposures, changing company activities, or the source methodology's full constituent-level screening. |
| Terms and project use | The methodology document is publicly available and cited by URL. This project redistributes no fund document, holdings file, or third-party ESG dataset; it ships only hand-authored proxy labels for its simulation-only dataset. |

This source supports fictional, simulation-only tribunal scenarios. It must not be interpreted as investment advice or as a directive to take any brokerage or bank action.

## Recent web context (Newsroom)

| Field | Documented value |
| --- | --- |
| Service | Amazon Bedrock AgentCore Web Search (`InvokeWebSearch`, tool `web-search.v1`, us-east-1). Amazon-operated web index; queries stay inside AWS; IAM-only access (`bedrock-agentcore:InvokeWebSearch`). |
| When | At run time, once per Tribunal_Session: 2 searches for the requested asset (news; results and guidance) plus 1 controversy search when the investor has ESG exclusions or preferences. The Investigator may run at most 2 follow-up searches through its `web_search` tool. |
| Filters | Published in the last 30 days (`publishedAfter` / `publishedBefore`). News and controversy searches use press, wire services and regulators only (`NEWS_DOMAINS`); the results search also allows issuers' releases and newswires (`ISSUER_DOMAINS`), in `guide/toolkit/web_evidence.py`. Landing pages (e.g. "Investor Relations" or bare ticker pages) are dropped. Rating and price-target aggregators are left out. |
| Processing | Each result becomes a Web Exhibit (`metric: web_news`) with title, URL, source domain, publication date, a snippet of at most 600 characters, query, and retrieval timestamp. Duplicates and results without a URL or title are dropped; at most 6 per session. Each snippet is screened with the Bedrock Guardrail (prompt-attack filter, `ApplyGuardrail`) before an agent sees it. |
| Use | Context only. Web Exhibits never change a Hard_Rule, a computed number, or the maximum weight; those come only from the pinned Dataset_Snapshot. Agents may cite events (recall, lawsuit, guidance change, controversy) by Exhibit number; analyst ratings, price targets and forecasts are never repeated. |
| Look-ahead | News is retrieved on the session date and may be published after the Dataset_Snapshot end (2026-11-12). It is shown as current context, never mixed into historical calculations. |
| Limitations | Search ranking and coverage are not controlled by the project; snippets can be incomplete or wrong; no sentiment score is computed. If the service fails or times out, the session continues on the Dataset_Snapshot alone and a data notice says so. |
| Terms | AgentCore Web Search acceptable use: every surfaced result keeps and displays its source citation and link (the Ruling's `recent_context` and the Exhibits panel). No bulk extraction or storage beyond the session record. |
