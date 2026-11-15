SELECT COUNT(*) AS duplicate_keys FROM (
  SELECT ex_date, ticker, action FROM corporate_actions WHERE snapshot_id = ?
  GROUP BY ex_date, ticker, action HAVING COUNT(*) > 1)
