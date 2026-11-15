-- Exploration: corporate actions per ticker and action type in one snapshot.
SELECT ticker, action, COUNT(*) AS actions, MIN(ex_date) AS first_ex_date, MAX(ex_date) AS last_ex_date
FROM corporate_actions
WHERE snapshot_id = ?
GROUP BY ticker, action
ORDER BY ticker, action
