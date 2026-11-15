SELECT 'prices_daily' AS table_name, COUNT(*) AS row_count
FROM prices_daily
WHERE snapshot_id = ?
