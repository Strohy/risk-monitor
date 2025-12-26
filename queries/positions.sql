-- Active borrow positions for Morpho Blue markets

WITH borrow_events AS (
    SELECT
        id AS market_id,
        onBehalf AS borrower,
        SUM(CAST(assets AS DOUBLE)) AS total_borrowed_assets,
        SUM(CAST(shares AS DOUBLE)) AS total_borrowed_shares,
        MAX(evt_block_time) AS last_borrow_time
    FROM morpho_blue_ethereum.MorphoBlue_evt_Borrow
    WHERE id IN ({{market_ids}})
    GROUP BY 1, 2
),

repay_events AS (
    SELECT
        id AS market_id,
        onBehalf AS borrower,
        SUM(CAST(assets AS DOUBLE)) AS total_repaid_assets,
        SUM(CAST(shares AS DOUBLE)) AS total_repaid_shares,
        MAX(evt_block_time) AS last_repay_time
    FROM morpho_blue_ethereum.MorphoBlue_evt_Repay
    WHERE id IN ({{market_ids}})
    GROUP BY 1, 2
),

liquidate_events AS (
    SELECT
        id AS market_id,
        borrower,
        SUM(CAST(repaidAssets AS DOUBLE)) AS total_liquidated_assets,
        MAX(evt_block_time) AS last_liquidation_time
    FROM morpho_blue_ethereum.MorphoBlue_evt_Liquidate
    WHERE id IN ({{market_ids}})
    GROUP BY 1, 2
)

SELECT
    b.market_id,
    b.borrower,

    -- Net debt (principal-based)
    b.total_borrowed_assets
        - COALESCE(r.total_repaid_assets, 0)
        - COALESCE(l.total_liquidated_assets, 0)
        AS active_borrow_assets,

    -- Optional: share-based view
    b.total_borrowed_shares
        - COALESCE(r.total_repaid_shares, 0)
        AS active_borrow_shares,

    -- Timestamps
    b.last_borrow_time,
    r.last_repay_time,
    l.last_liquidation_time

FROM borrow_events b
LEFT JOIN repay_events r
    ON b.market_id = r.market_id
   AND b.borrower = r.borrower
LEFT JOIN liquidate_events l
    ON b.market_id = l.market_id
   AND b.borrower = l.borrower

-- Only active positions
WHERE (
    b.total_borrowed_assets
    - COALESCE(r.total_repaid_assets, 0)
    - COALESCE(l.total_liquidated_assets, 0)
) > 0

ORDER BY active_borrow_assets DESC;
