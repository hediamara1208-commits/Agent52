SELECT COUNT(*) AS non_positive_rows
FROM prices_daily
WHERE snapshot_id = ? AND (adj_close IS NULL OR adj_close <= 0)
