# Data sources

## ESG exclusion list

| Field | Documented value |
| --- | --- |
| Dataset file | `data/esg_exclusions.csv` |
| Source | [Vanguard ESG U.S. Stock ETF summary prospectus](https://fund-docs.vanguard.com/F4393.pdf), which describes exclusion screens for fossil-fuel activities and specified controversial activities. |
| Retrieval date | 2026-11-14 |
| Method | The project team manually applied a narrow, issuer-level fossil-fuel screen to every ticker in `assets_universe.csv`. Direct oil and gas exploration, production, refining, transportation, and distribution are marked `excluded=true`. All other assets are marked `false` unless a direct match is documented. ETF holdings are not assessed. Each row repeats the source URL and retrieval date so a Ruling can cite its provenance. |
| Processing and snapshot use | The CSV is a hand-authored source file. The Snapshot_Writer records it as `esg_exclusions` in each immutable Snapshot_Manifest; later Toolkit loading reads the pinned snapshot copy. No market data is downloaded or changed by this file. |
| Limitations | This is a simplified binary exclusion proxy, not an ESG score, ESG rating, controversy database, sustainability assessment, or a prediction. It does not assess ETF holdings, indirect exposures, changing company activities, or the source methodology's full constituent-level screening. |
| Terms and project use | The methodology document is publicly available and cited by URL. This project redistributes no fund document, holdings file, or third-party ESG dataset; it ships only hand-authored proxy labels for its simulation-only dataset. |

This source supports fictional, simulation-only tribunal scenarios. It must not be interpreted as investment advice or as a directive to take any brokerage or bank action.
