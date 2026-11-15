SELECT COUNT(*) AS duplicate_keys FROM (
  SELECT date, ticker FROM prices_daily WHERE snapshot_id = ?
  GROUP BY date, ticker HAVING COUNT(*) > 1)
