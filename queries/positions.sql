-- Get all open positions for Morpho Blue markets
-- This aggregates supply and borrow events to calculate current position state

WITH latest_positions AS (
    SELECT
        id,
        market_id,
        user as borrower,
        shares_balance,
        assets_balance,
        evt_block_time as block_time,
        ROW_NUMBER() OVER (PARTITION BY market_id, user ORDER BY evt_block_time DESC) as rn
    FROM morpho_ethereum.MorphoBlue_evt_Borrow
    WHERE market_id IN ({{market_ids}})
        AND evt_block_time >= NOW() - INTERVAL '7' DAY
)
SELECT
    market_id,
    borrower,
    shares_balance as borrow_shares,
    assets_balance as borrow_assets,
    block_time
FROM latest_positions
WHERE rn = 1
    AND shares_balance > 0
ORDER BY shares_balance DESC
LIMIT 1000
