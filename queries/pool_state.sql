-- Get current pool state metrics for Morpho Blue markets
-- Aggregates supply, borrow, and collateral events to calculate pool state

WITH ranked AS (
    SELECT
        _0 AS market_id,
        call_block_time,
        output_totalBorrowAssets,
        output_totalSupplyAssets,
        ROW_NUMBER() OVER (
            PARTITION BY _0
            ORDER BY call_block_time DESC
        ) AS rn
    FROM morpho_blue_ethereum.MorphoBlue_call_market
    WHERE _0 IN ({{market_ids}})
)

SELECT
    market_id,
    call_block_time,
    output_totalBorrowAssets,
    output_totalSupplyAssets
FROM ranked
WHERE rn = 1
ORDER BY market_id;
