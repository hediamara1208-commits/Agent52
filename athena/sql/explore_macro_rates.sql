-- Exploration: coverage per macro series in one snapshot.
SELECT series_id, label, frequency, MIN(date) AS first_date, MAX(date) AS last_date, COUNT(*) AS observations
FROM macro_rates
WHERE snapshot_id = ?
GROUP BY series_id, label, frequency
ORDER BY series_id
