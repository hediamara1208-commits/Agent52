SELECT 'corporate_actions' AS table_name, COUNT(*) AS row_count
FROM corporate_actions
WHERE snapshot_id = ?
