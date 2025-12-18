-- Get historical liquidation events for Morpho Blue markets
-- This helps identify past stress events and liquidation patterns

SELECT
    evt_block_time,
    evt_block_number,
    id,
    borrower,
    seizedAssets as seized_assets,
    repaidAssets as repaid_assets,
    repaidShares as repaid_shares,
    evt_tx_hash as tx_hash
FROM morpho_blue_ethereum.MorphoBlue_evt_Liquidate
WHERE id IN ({{market_ids}})
    AND evt_block_time >= NOW() - INTERVAL '90' DAY
ORDER BY evt_block_time DESC
