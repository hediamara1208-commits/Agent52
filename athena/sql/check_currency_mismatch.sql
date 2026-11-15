SELECT COUNT(*) AS mismatched_rows
FROM prices_daily p
JOIN assets_universe a ON p.ticker = a.ticker AND a.snapshot_id = ?
WHERE p.snapshot_id = ? AND p.currency <> a.currency
