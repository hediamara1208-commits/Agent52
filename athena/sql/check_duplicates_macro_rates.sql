SELECT COUNT(*) AS duplicate_keys FROM (
  SELECT date, series_id FROM macro_rates WHERE snapshot_id = ?
  GROUP BY date, series_id HAVING COUNT(*) > 1)
