SELECT COUNT(*) AS duplicate_keys FROM (
  SELECT ticker FROM assets_universe WHERE snapshot_id = ?
  GROUP BY ticker HAVING COUNT(*) > 1)
