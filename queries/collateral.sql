-- Get collateral balances for borrowers
-- This retrieves the latest collateral amounts for each position

WITH latest_collateral AS (
    SELECT
        market_id,
        onBehalf as borrower,
        assets as collateral,
        evt_block_time as block_time,
        ROW_NUMBER() OVER (PARTITION BY market_id, onBehalf ORDER BY evt_block_time DESC) as rn
    FROM morpho_ethereum.MorphoBlue_evt_SupplyCollateral
    WHERE market_id IN ({{market_ids}})
        AND evt_block_time >= NOW() - INTERVAL '7' DAY
)
SELECT
    market_id,
    borrower,
    collateral,
    block_time
FROM latest_collateral
WHERE rn = 1
    AND collateral > 0
ORDER BY collateral DESC
