-- Exploration: coverage and price range per ticker in one snapshot.
SELECT ticker, MIN(date) AS first_date, MAX(date) AS last_date,
       COUNT(*) AS observations, MIN(adj_close) AS min_adj_close, MAX(adj_close) AS max_adj_close
FROM prices_daily
WHERE snapshot_id = ?
GROUP BY ticker
ORDER BY ticker
