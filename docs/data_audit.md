# Financial data audit

Audit date: 2026-11-15. Scope: the files in `data/` that the deployed snapshot was built from, the toolkit code that reads them (`guide/toolkit/align.py`, `metrics.py`, `risk_panel.py`), and the official challenge statement as summarised in `data/context.md`. Counts below were measured by `scripts/data_quality_audit.py` (results in `docs/data_quality_report.md`); nothing here is estimated. Source-by-source provenance and terms are in `docs/data_sources.md`.

Bottom line: the data is sufficient for price-based portfolio risk on 31 securities over five years, in CAD. It is not sufficient for company-specific analysis (fundamentals, valuation), ETF look-through, geographic exposure, benchmark-relative performance or ESG scoring. VERDICT does not compute any of those, and says so in each ruling's limits.

## 1. Dataset inventory

| Table | Rows | Fields | Provider | Coverage | Frequency | Used in a ruling? |
| --- | --- | --- | --- | --- | --- | --- |
| `assets_universe` | 31 | asset_id, ticker, name, asset_class, market, currency, sector | Compiled by the organizers; sectors are simplified GICS names | 20 stocks, 4 equity ETFs, 4 bond ETFs, 1 gold ETF, 2 crypto; TSX 13, NASDAQ 8, NYSE 4, NYSE Arca 3, Cboe BZX 1 | Static | Yes: asset class, sector and currency drive the caps and the exposure tables |
| `prices_daily` | 40,049 | date, ticker, open, high, low, close, adj_close, volume, currency | Yahoo Finance via `yfinance` | 2021-11-12 to 2026-11-12; 1,255 rows per listed security, 1,827 per crypto asset | Daily | Yes: `adj_close` only |
| `fx_usdcad_daily` | 1,245 | date, usdcad, cadusd | Bank of Canada Valet, series FXUSDCAD | Same window, Canadian business days | Daily | Yes: converts USD prices to CAD |
| `corporate_actions` | 658 | ex_date, ticker, action, value, unit | Yahoo Finance via `yfinance` | Same window | Per event | No: prices are already adjusted; kept for checks |
| `macro_rates` | 8,281 (9 series) | date, series_id, value, unit, frequency, label, source | Bank of Canada Valet; FRED | Same window | Daily or monthly | No ruling figure uses it |
| `esg_exclusions` | 31 | ticker, excluded, reason, source_url, retrieved | Hand-authored by the team from a public fund prospectus's screen description | All 31 tickers, retrieved 2026-11-14 | Static | Yes: pass or fail of the ESG exclusion only |
| Web news | up to 6 per hearing | title, URL, source, date, snippet | Amazon Bedrock AgentCore Web Search | Last 30 days at hearing time | Live | Context only; never in a calculation |

Update frequency: none. The snapshot was retrieved once (2026-11-13) and is immutable; the site shows "Market data to Nov 12, 2026". `data/build_dataset.py` regenerates the files, but a rebuild changes `adj_close` history (Yahoo back-adjusts), so a new snapshot would give slightly different numbers.

## 2. Treatment

| Topic | What is done | Evidence |
| --- | --- | --- |
| Adjusted prices | Returns use `adj_close` (splits and dividends). `close` is never used for returns; split rows are not applied a second time. | `align.price_matrix`, `metrics.py` |
| Corporate actions | Not applied by us. One unverified item: CNQ.TO has a 1.021 "split" on 2022-08-22, the day of a 0.75 CAD dividend; rulings whose period includes it carry a note. | `guide/data/quality.py` |
| Currency | Everything is in CAD. USD prices are multiplied by that day's Bank of Canada rate. On 37 U.S. trading days (582 crypto days) there is no rate, and the last earlier rate is used; the evidence notes say how many dates. | `align.convert_to_cad` |
| Missing prices | No forward-fill. Securities are compared only on dates where each has a price; the evidence records the count before and after (for example 1,228 common days for Robert's portfolio plus TSLA). | `align.py` |
| Quality checks | 0 duplicate date-ticker rows, 0 missing or non-positive prices, 0 gaps longer than 7 days, 0 one-day moves above 25%. | `docs/data_quality_report.md` |
| Reproducibility | Each hearing pins one snapshot; every file has a SHA-256 in the snapshot manifest; each piece of evidence records period, currency, securities and processing notes. | `guide/ingest`, evidence records |

## 3. Data-requirements matrix

| Analysis | Input needed | Current source | Sufficient? | Limitation | Improvement |
| --- | --- | --- | --- | --- | --- |
| Volatility | Daily total-return prices | `prices_daily.adj_close` | Yes | 5 years only; Yahoo is not exchange-certified | Longer history; a second price source for cross-checks |
| Maximum drawdown | Same | Same | Yes, within the window | The window includes 2022 but not 2008 or 2020 | History back to 2007 |
| Returns (annualised, 2022, worst 12 months) | Same | Same | Yes, as history | Survivorship bias: all 31 securities exist today | Include delisted names; state it (done) |
| Correlation with current holdings | Aligned daily returns | Same | Yes | Correlations move in stress; one 5-year estimate | Rolling or stressed correlations |
| Risk contribution | Weights and covariance | Same plus the portfolio | Yes | Same as correlation | Same |
| Sector concentration | Sector per security | `assets_universe.sector` | Partly | Organizer labels; an ETF counts as one "sector", no look-through | ETF holdings files from the issuers |
| Geographic concentration | Country of revenue or listing | None beyond listing market and currency | No | Only currency exposure (CAD or USD) is computed | Country field; ETF regional breakdowns |
| Currency exposure | Listing currency, FX | `assets_universe.currency`, `fx_usdcad_daily` | Yes for CAD and USD | A USD-listed fund holding other currencies counts as USD | ETF look-through |
| Diversification | The three rows above | As above | Partly | Without look-through, an S&P 500 ETF and its largest member count as separate | ETF holdings |
| Investor limits (caps, volatility, drawdown, speculative, crypto) | Profile limits; the metrics above | Profile; the snapshot | Yes | The limits are the investor's own statements | None needed |
| Investment horizon | Horizon; return distribution by horizon | Profile; 5 years of prices | Partly | Too short to test a 10-year horizon; used as a stated preference, not a test | Longer history |
| ESG | Issuer-level screens or scores | `esg_exclusions` (fossil-fuel screen, 3 names flagged) | Partly | A binary proxy by the team; no ESG score; ETF holdings not assessed | A licensed ESG dataset |
| Stress scenarios | Prices through named crises | 2022 only | Partly | One rate-shock year; no synthetic shocks | Longer history; rate and equity shock scenarios |
| Company-specific risk (earnings, leverage, valuation) | Financial statements, estimates | None | No | Not computed. Recent news is shown as context only | Filings (SEDAR+, EDGAR) |
| Market conditions | Rates, inflation, yields | `macro_rates` is loaded but unused; news as context | No | No ruling figure depends on macro data | Use the yield series for a rate-sensitivity figure on bond ETFs |
| Benchmark-relative performance | A benchmark series | None designated | No | XIU.TO and SPY are in the universe but not used as benchmarks | Declare a benchmark per profile |

## 4. Do the agents claim more than the data supports?

Controls in the code, not promises: the agents receive computed evidence and news snippets only; a claim with no evidence number behind it is removed by the citation check and shown as removed; pass or fail on every limit is computed, never written by a model; analyst ratings, price targets and forecasts are filtered out of news; when a request mentions fundamentals or ESG scores, the ruling carries a notice that the dataset does not contain them.

What was checked for this audit: the recorded Robert / 30% TSLA hearing. Its arguments cite concentration, volatility, drawdown and the limits, all backed by evidence, and none refers to earnings, valuation or analyst views. What was not done: a systematic review of many live hearings for unsupported statements. One hearing is not proof for all.

## 5. Against the challenge statement

| Requirement (`data/context.md`) | Status |
| --- | --- |
| Public financial data | Met: Yahoo Finance, Bank of Canada, FRED, all public |
| No asset or asset class is mandatory | Met: the organizers' 31 securities are used as provided |
| For each source: relevance, origin, date, processing, limits, terms | Met in `docs/data_sources.md` and `data/sources_metadata.csv` |
| Traceability: source, date, currency, processing | Met: every piece of evidence shows period, currency, securities, method and limits; the internal snapshot id is kept in the record but not shown to investors |
| Starter set says ESG ratings, news and fundamentals are absent, to be added by the team if needed | Partly: an ESG exclusion proxy and live news context were added and documented; fundamentals were not added |
| Temporal consistency, no look-ahead | Met for calculations: one fixed window ending 2026-11-12. Macro series carry a publication lag but are unused. News is dated after the window and shown as current context only |
| Comparability: dividends, splits, selection bias, missing data, CAD/USD | Met: section 2; survivorship bias is stated in every ruling |
| Explanations faithful to sources, no invented justification | Enforced by the citation check; see section 4 for what was and was not verified |

## 6. Sources considered and not added

No source was added in this pass. Fundamentals, ETF holdings and a longer price history would each need a new ingestion path, new validation and a new snapshot, and would change numbers on the live site hours before submission. They are listed in the matrix as improvements instead.
