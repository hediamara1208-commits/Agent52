-- Exploration: assets in one snapshot, by class and market.
SELECT asset_class, market, currency, COUNT(*) AS assets
FROM assets_universe
WHERE snapshot_id = ?
GROUP BY asset_class, market, currency
ORDER BY asset_class, market
