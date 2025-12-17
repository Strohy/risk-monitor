-- Get current token prices from Dune's prices.usd table
-- This provides USD pricing for collateral and loan assets

SELECT
    contract_address,
    symbol,
    decimals,
    price,
    minute as timestamp
FROM prices.usd
WHERE blockchain = 'ethereum'
    AND contract_address IN ({{token_addresses}})
    AND minute >= NOW() - INTERVAL '1' HOUR
ORDER BY minute DESC
