-- Get all open positions for Morpho Blue markets
-- Aggregates borrow and repay events to calculate net outstanding debt

WITH borrow_events AS (
    SELECT
        id as market_id,
        onBehalf as borrower,
        SUM(CAST(assets AS DOUBLE)) as total_borrowed,
        SUM(CAST(shares AS DOUBLE)) as total_borrow_shares,
        MAX(evt_block_time) as last_borrow_time
    FROM morpho_blue_ethereum.MorphoBlue_evt_Borrow
    WHERE id IN ({{market_ids}})
    GROUP BY id, onBehalf
),
repay_events AS (
    SELECT
        id as market_id,
        onBehalf as borrower,
        SUM(CAST(assets AS DOUBLE)) as total_repaid,
        SUM(CAST(shares AS DOUBLE)) as total_repay_shares
    FROM morpho_blue_ethereum.MorphoBlue_evt_Repay
    WHERE id IN ({{market_ids}})
    GROUP BY id, onBehalf
)
SELECT
    b.market_id as id,
    b.borrower,
    GREATEST(b.total_borrowed - COALESCE(r.total_repaid, 0), 0) as borrow_assets,
    GREATEST(b.total_borrow_shares - COALESCE(r.total_repay_shares, 0), 0) as borrow_shares,
    b.last_borrow_time as block_time
FROM borrow_events b
LEFT JOIN repay_events r
    ON b.market_id = r.market_id
    AND b.borrower = r.borrower
WHERE GREATEST(b.total_borrowed - COALESCE(r.total_repaid, 0), 0) > 0
ORDER BY borrow_assets DESC
LIMIT 1000