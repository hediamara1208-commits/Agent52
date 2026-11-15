SELECT COUNT(*) AS duplicate_keys FROM (
  SELECT date FROM fx_usdcad_daily WHERE snapshot_id = ?
  GROUP BY date HAVING COUNT(*) > 1)
