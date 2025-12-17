-- Get current pool state metrics for Morpho Blue markets
-- This query retrieves historical pool state over the past 30 days
-- including supply, borrow, and utilization metrics

SELECT
    market_id,
    block_time,
    total_supply_assets,
    total_borrow_assets,
    total_supply_shares,
    total_borrow_shares,
    CAST(total_borrow_assets AS DOUBLE) / NULLIF(CAST(total_supply_assets AS DOUBLE), 0) as utilization
FROM morpho_ethereum.MorphoBlue_evt_AccrueInterest
WHERE market_id IN ({{market_ids}})
    AND block_time >= NOW() - INTERVAL '30' DAY
ORDER BY block_time DESC
