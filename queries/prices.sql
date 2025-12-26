-- Get current token prices from Dune's prices.usd table
-- This provides USD pricing for collateral and loan assets

WITH ranked_prices AS (
    SELECT
        contract_address,
        symbol,
        decimals,
        price,
        minute,
        ROW_NUMBER() OVER (
            PARTITION BY contract_address
            ORDER BY minute DESC
        ) AS rn
    FROM prices.usd
    WHERE blockchain = 'ethereum'
      AND contract_address IN ({{token_addresses}})
      AND minute >= NOW() - INTERVAL '1' HOUR
)

SELECT
    contract_address,
    symbol,
    decimals,
    price,
    minute
FROM ranked_prices
WHERE rn = 1
ORDER BY contract_address;
