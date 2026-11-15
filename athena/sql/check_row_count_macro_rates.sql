SELECT 'macro_rates' AS table_name, COUNT(*) AS row_count
FROM macro_rates
WHERE snapshot_id = ?
