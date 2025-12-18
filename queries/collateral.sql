-- Get collateral balances for borrowers
-- Aggregates SupplyCollateral and WithdrawCollateral events to calculate net collateral

WITH supply_collateral AS (
    SELECT
        id as market_id,
        onBehalf as borrower,
        SUM(CAST(assets AS DOUBLE)) as total_supplied,
        MAX(evt_block_time) as last_supply_time
    FROM morpho_blue_ethereum.MorphoBlue_evt_SupplyCollateral
    WHERE id IN ({{market_ids}})
    GROUP BY id, onBehalf
),
withdraw_collateral AS (
    SELECT
        id as market_id,
        onBehalf as borrower,
        SUM(CAST(assets AS DOUBLE)) as total_withdrawn
    FROM morpho_blue_ethereum.MorphoBlue_evt_WithdrawCollateral
    WHERE id IN ({{market_ids}})
    GROUP BY id, onBehalf
)
SELECT
    s.market_id as id,
    s.borrower,
    GREATEST(s.total_supplied - COALESCE(w.total_withdrawn, 0), 0) as collateral,
    s.last_supply_time as block_time
FROM supply_collateral s
LEFT JOIN withdraw_collateral w
    ON s.market_id = w.market_id
    AND s.borrower = w.borrower
WHERE GREATEST(s.total_supplied - COALESCE(w.total_withdrawn, 0), 0) > 0
ORDER BY collateral DESC
