SELECT 'fx_usdcad_daily' AS table_name, COUNT(*) AS row_count
FROM fx_usdcad_daily
WHERE snapshot_id = ?
