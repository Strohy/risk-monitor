-- Get current pool state metrics for Morpho Blue markets
-- Aggregates supply, borrow, and collateral events to calculate pool state
-- Note: Morpho Blue doesn't have a single state table, we need to aggregate events

WITH supply_events AS (
    SELECT
        id as market_id,
        evt_block_time,
        evt_block_number,
        SUM(assets) OVER (PARTITION BY id ORDER BY evt_block_time, evt_index) as cumulative_supply
    FROM morpho_blue_ethereum.MorphoBlue_evt_Supply
    WHERE id IN ({{market_ids}})
        AND evt_block_time >= NOW() - INTERVAL '30' DAY
),
borrow_events AS (
    SELECT
        id as market_id,
        evt_block_time,
        evt_block_number,
        SUM(assets) OVER (PARTITION BY id ORDER BY evt_block_time, evt_index) as cumulative_borrow
    FROM morpho_blue_ethereum.MorphoBlue_evt_Borrow
    WHERE id IN ({{market_ids}})
        AND evt_block_time >= NOW() - INTERVAL '30' DAY
),
latest_state AS (
    SELECT
        s.market_id,
        s.evt_block_time as block_time,
        s.cumulative_supply as total_supply_assets,
        COALESCE(b.cumulative_borrow, 0) as total_borrow_assets
    FROM supply_events s
    LEFT JOIN borrow_events b
        ON s.market_id = b.market_id
        AND s.evt_block_time = b.evt_block_time
)
SELECT
    market_id,
    block_time,
    total_supply_assets,
    total_borrow_assets,
    total_supply_assets as total_supply_shares,
    total_borrow_assets as total_borrow_shares,
    CASE
        WHEN total_supply_assets > 0
        THEN CAST(total_borrow_assets AS DOUBLE) / CAST(total_supply_assets AS DOUBLE)
        ELSE 0.0
    END as utilization
FROM latest_state
ORDER BY block_time DESC
LIMIT 100
