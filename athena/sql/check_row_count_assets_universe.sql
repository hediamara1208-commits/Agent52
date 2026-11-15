SELECT 'assets_universe' AS table_name, COUNT(*) AS row_count
FROM assets_universe
WHERE snapshot_id = ?
