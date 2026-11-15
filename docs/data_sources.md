# Data sources

Every number in a Ruling comes from one pinned Dataset_Snapshot built from the organizers' starter files below, plus the hand-authored ESG list. Recent web news is context only and never enters a calculation. Each section gives origin, retrieval date, processing, limits and terms, as the brief requires.

| Source | Used for | Changes a computed number? |
| --- | --- | --- |
| Starter dataset (Yahoo Finance, Bank of Canada, FRED) | Prices, returns, risk metrics, CAD conversion | Yes: the only source of figures |
| ESG exclusion list (hand-authored) | The `esg_exclusions` Hard_Rule | Pass/fail only |
| AgentCore Web Search (Newsroom) | Recent context the agents may cite | No |

## Starter dataset (organizers' pack)

| Field | Documented value |
| --- | --- |
| Dataset files | `data/assets_universe.csv` (31 assets), `data/prices_daily.csv` (40,049 rows), `data/corporate_actions.csv` (658 rows), `data/fx_usdcad_daily.csv` (1,245 rows), `data/macro_rates.csv` (8,281 rows, 9 series). Per-file metadata: `data/sources_metadata.csv`. |
| Origin | Prices and corporate actions: Yahoo Finance via the open-source `yfinance` library. USD/CAD rate (series `FXUSDCAD`), Bank of Canada policy rate, Government of Canada 2y and 10y yields, Canada CPI: Bank of Canada Valet API. U.S. fed funds, Treasury 2y and 10y, CPI, unemployment: FRED (Federal Reserve Bank of St. Louis). Built by the organizers with `data/build_dataset.py`. |
| Coverage and retrieval | 2021-11-12 to 2026-11-12, retrieved 2026-11-13. Daily rows: 1,255 per TSX or U.S. listing, 1,827 per crypto asset (7 days a week). The build reported no data-quality warnings (`data/data_quality_warnings.txt`). |
| Ingestion | `python -m guide.ingest.seed` reads the five CSV files (no download, no `yfinance` import), validates them (duplicate date-ticker rows, universe tickers without prices, currency mismatches, missing or non-positive `adj_close`), writes raw CSV and Parquet to Amazon S3 (`alphaforge-guide-data/dataset/`) with a SHA-256 per object in the Snapshot_Manifest, registers one AWS Glue partition per table, and cross-checks row counts and duplicates with Amazon Athena. A snapshot is immutable; a new one (for example `20261115T154221Z-esg`, which adds the ESG table and carries every market file over unchanged) moves the current pointer. Each session pins one snapshot and reports its id in the Ruling. |
| Returns | From `adj_close` (split- and dividend-adjusted). `close` is never used for returns, and the split rows in `corporate_actions.csv` are not applied again (prices are already split-adjusted). |
| Currency | Every figure is in CAD. USD-listed prices are multiplied by that day's Bank of Canada `usdcad`. The FX file has no row on Canadian holidays (37 U.S. trading days in the window), so the most recent earlier rate is carried forward, and the Exhibit's processing notes say how many dates that affected. A date with no earlier rate would be dropped and named (none in this window). Code: `guide/toolkit/align.py`, `convert_to_cad`. |
| Calendar alignment | No forward-fill of prices. When assets are compared or combined, only dates on which every asset has a price are kept (date intersection), and the Exhibit records the observation count before and after. Example: Robert's portfolio plus TSLA keeps 1,228 common days (1,255 per listing; 27 TSX-only and 27 U.S.-only holidays). Crypto, which trades every day, is reduced to the same common days when it is compared with listed assets. |
| Metrics | Annualized volatility = sample standard deviation of daily returns × √252; annualized return is geometric over 252 trading days; maximum drawdown and worst rolling 252-day return from the CAD value path; risk contribution and correlation from the same aligned returns. Default window: the 5 years ending on the snapshot's last price date. Code: `guide/toolkit/metrics.py`. |
| Macro series | Loaded into the snapshot with a publication lag per series (`config.yaml`, `macro_publication_lag_days`: 45 days for CPI, 38 for U.S. unemployment, 1 for daily rates), so a value is visible only after it was published. No current Hard_Rule or Ruling figure uses macro data. |
| Limitations | Survivorship bias: the 31 assets were chosen in 2026 among names that are large today, so historical results look better than an investor would have experienced; the Clerk adds this limitation to every Ruling. Five years is a short sample. Yahoo data is not exchange-certified, and `adj_close` is back-adjusted, so it changes on re-download. FRED values are the latest revision, not as first published. CNQ.TO shows a 1.021 "split" factor on 2022-08-22 (the same day as a 0.75 CAD dividend) that likely reflects a special distribution; it is unverified, and any Exhibit whose period includes that date carries a note (`guide/data/quality.py`). Crypto rows are UTC calendar days with no market close. The dataset has no ESG scores, fundamentals or news; when a request mentions them (or the investor has ESG exclusions), the Clerk adds a notice that the Dataset does not contain them and any related argument is unsupported by Exhibits. |
| Terms and project use | Yahoo: https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html. Bank of Canada: https://www.bankofcanada.ca/terms/. FRED: https://fred.stlouisfed.org/legal/ (series from U.S. government agencies). Permitted use: provided by the organizers for the datathon; used only inside this simulation, with each source named in the Exhibits. Not redistributed beyond the competition repository. |

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
