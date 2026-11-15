-- Tickers present in only one of prices_daily and assets_universe (0 means equal sets).
SELECT COUNT(*) AS mismatched_tickers FROM (
  SELECT COALESCE(p.ticker, a.ticker) AS ticker
  FROM (SELECT DISTINCT ticker FROM prices_daily WHERE snapshot_id = ?) p
  FULL OUTER JOIN (SELECT DISTINCT ticker FROM assets_universe WHERE snapshot_id = ?) a
    ON p.ticker = a.ticker
  WHERE p.ticker IS NULL OR a.ticker IS NULL)
