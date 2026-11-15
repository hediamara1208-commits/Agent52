-- Exploration: FX coverage and range in one snapshot.
SELECT MIN(date) AS first_date, MAX(date) AS last_date, COUNT(*) AS observations,
       MIN(usdcad) AS min_usdcad, MAX(usdcad) AS max_usdcad
FROM fx_usdcad_daily
WHERE snapshot_id = ?
