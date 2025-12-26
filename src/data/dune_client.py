"""Dune Analytics API client for fetching Morpho Blue data"""

from dune_client.client import DuneClient
from dune_client.query import QueryBase
from dune_client.types import QueryParameter
import pandas as pd
import yaml
from typing import List, Dict, Optional
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MorphoDataFetcher:
    """Fetches Morpho Blue data from Dune Analytics"""

    def __init__(self, api_key: str, use_query_ids: bool = True):
        """
        Initialize Dune client

        Args:
            api_key: Dune Analytics API key
            use_query_ids: If True, use pre-created query IDs from config.
                          If False, attempt to create queries programmatically (may fail on free tier)
        """
        self.client = DuneClient(api_key)
        self.queries_dir = Path(__file__).parent.parent.parent / "queries"
        self.config_dir = Path(__file__).parent.parent.parent / "config"
        self.use_query_ids = use_query_ids

        # Load query IDs from config if using query ID mode
        if self.use_query_ids:
            self.query_ids = self._load_query_ids()
            logger.info(f"Initialized Dune client (using query IDs: {list(self.query_ids.keys())})")
        else:
            self.query_ids = {}
            logger.info("Initialized Dune client (dynamic query creation mode)")

    def _load_query_ids(self) -> Dict[str, int]:
        """Load query IDs from config file"""
        config_path = self.config_dir / "dune_queries.yaml"

        if not config_path.exists():
            logger.warning(f"Query IDs config not found: {config_path}")
            logger.warning("Falling back to dynamic query creation (may not work on free tier)")
            return {}

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        query_ids = config.get('queries', {})

        # Check if any IDs are null/None
        missing = [k for k, v in query_ids.items() if v is None]
        if missing:
            logger.error(f"Missing query IDs in config for: {missing}")
            logger.error(f"Please update {config_path} with your Dune query IDs")
            logger.error(f"See DUNE_SETUP.md for instructions")

        return query_ids

    def _execute_query_by_id(self, query_key: str, params: List[QueryParameter] = None) -> pd.DataFrame:
        """
        Execute a pre-created query using its ID

        Args:
            query_key: Key in dune_queries.yaml (e.g., 'positions', 'collateral')
            params: Optional query parameters

        Returns:
            DataFrame with results
        """
        query_id = self.query_ids.get(query_key)

        if query_id is None:
            logger.error(f"Query ID not found for '{query_key}'")
            logger.error(f"Please add it to config/dune_queries.yaml")
            return pd.DataFrame()

        try:
            # Create QueryBase with the pre-existing query ID
            query = QueryBase(
                query_id=query_id,
                name=query_key,
                params=params or []
            )

            logger.info(f"Executing query '{query_key}' (ID: {query_id})...")
            results = self.client.run_query_dataframe(query)
            logger.info(f"Query '{query_key}' returned {len(results)} rows")

            return results

        except Exception as e:
            logger.error(f"Error executing query '{query_key}' (ID: {query_id}): {e}")
            return pd.DataFrame()

    def _execute_custom_query(self, query_sql: str, query_name: str = "Custom Query") -> pd.DataFrame:
        """
        Execute a custom SQL query using Dune API

        Note: This creates a query on your Dune account first, then executes it.

        Args:
            query_sql: SQL query string
            query_name: Name for the query

        Returns:
            DataFrame with results
        """
        try:
            # Create a query on Dune - returns a query object with .base.query_id
            query_obj = self.client.create_query(
                name=query_name,
                query_sql=query_sql,
                is_private=False
            )

            # Extract the query_id from the returned object
            query_id = query_obj.base.query_id
            logger.info(f"Created query '{query_name}' with ID: {query_id}")

            # Now execute the created query using the base QueryBase object
            results = self.client.run_query_dataframe(query_obj.base)

            return results

        except Exception as e:
            logger.error(f"Error executing custom query: {e}")
            logger.warning(f"Dune client may not support ad-hoc SQL execution")
            logger.info(f"To use this tool, you need to:")
            logger.info(f"  1. Create queries manually on Dune.com")
            logger.info(f"  2. Get the query IDs")
            logger.info(f"  3. Update the code to use query IDs instead of SQL")
            # Return empty DataFrame as fallback
            return pd.DataFrame()

    def _load_query(self, query_name: str) -> str:
        """
        Load SQL query from file

        Args:
            query_name: Name of query file (without .sql extension)

        Returns:
            SQL query string
        """
        query_path = self.queries_dir / f"{query_name}.sql"

        if not query_path.exists():
            raise FileNotFoundError(f"Query file not found: {query_path}")

        with open(query_path, "r") as f:
            return f.read()

    def _format_market_ids(self, market_ids: List[str]) -> str:
        """Format market IDs for SQL IN clause"""
        return ",".join(f"0x{mid.replace('0x', '')}" for mid in market_ids)

    def _format_addresses(self, addresses: List[str]) -> str:
        """Format addresses for SQL IN clause"""
        return ",".join(f"0x{addr.replace('0x', '').lower()}" for addr in addresses)

    def fetch_pool_state(self, market_ids: List[str]) -> pd.DataFrame:
        """
        Fetch current pool state from Dune

        Args:
            market_ids: List of Morpho Blue market IDs

        Returns:
            DataFrame with pool state metrics
        """
        logger.info(f"Fetching pool state for {len(market_ids)} markets...")

        if self.use_query_ids:
            # Use pre-created query with ID and parameters
            params = [
                QueryParameter.text_type(name="market_ids", value=self._format_market_ids(market_ids))
            ]
            result = self._execute_query_by_id("pool_state", params=params)
        else:
            # Dynamic query creation (may not work on free tier)
            query_sql = self._load_query("pool_state")
            query_sql = query_sql.replace("{{market_ids}}", self._format_market_ids(market_ids))
            result = self._execute_custom_query(query_sql, "Pool State")

        logger.info(f"Retrieved {len(result)} pool state records")
        return result

    def fetch_positions(self, market_ids: List[str]) -> pd.DataFrame:
        """
        Fetch all open positions

        Args:
            market_ids: List of Morpho Blue market IDs

        Returns:
            DataFrame with position data
        """
        logger.info(f"Fetching positions for {len(market_ids)} markets...")

        if self.use_query_ids:
            params = [
                QueryParameter.text_type(name="market_ids", value=self._format_market_ids(market_ids))
            ]
            result = self._execute_query_by_id("positions", params=params)
        else:
            query_sql = self._load_query("positions")
            query_sql = query_sql.replace("{{market_ids}}", self._format_market_ids(market_ids))
            result = self._execute_custom_query(query_sql, "Open Positions")

        logger.info(f"Retrieved {len(result)} open positions")
        return result

    def fetch_collateral(self, market_ids: List[str]) -> pd.DataFrame:
        """
        Fetch collateral balances for positions

        Args:
            market_ids: List of Morpho Blue market IDs

        Returns:
            DataFrame with collateral data
        """
        logger.info(f"Fetching collateral for {len(market_ids)} markets...")

        if self.use_query_ids:
            params = [
                QueryParameter.text_type(name="market_ids", value=self._format_market_ids(market_ids))
            ]
            result = self._execute_query_by_id("collateral", params=params)
        else:
            query_sql = self._load_query("collateral")
            query_sql = query_sql.replace("{{market_ids}}", self._format_market_ids(market_ids))
            result = self._execute_custom_query(query_sql, "Collateral Balances")

        logger.info(f"Retrieved {len(result)} collateral records")
        return result

    def fetch_liquidations(self, market_ids: List[str], days: int = 90) -> pd.DataFrame:
        """
        Fetch historical liquidations

        Args:
            market_ids: List of Morpho Blue market IDs
            days: Number of days of history to fetch

        Returns:
            DataFrame with liquidation events
        """
        logger.info(f"Fetching liquidations for past {days} days...")

        if self.use_query_ids:
            params = [
                QueryParameter.text_type(name="market_ids", value=self._format_market_ids(market_ids))
            ]
            result = self._execute_query_by_id("liquidations", params=params)
        else:
            query_sql = self._load_query("liquidations")
            query_sql = query_sql.replace("{{market_ids}}", self._format_market_ids(market_ids))
            result = self._execute_custom_query(query_sql, "Historical Liquidations")

        logger.info(f"Retrieved {len(result)} liquidation events")
        return result

    def fetch_prices(self, token_addresses: List[str]) -> Dict[str, float]:
        """
        Fetch current token prices

        Args:
            token_addresses: List of token contract addresses

        Returns:
            Dictionary mapping address to price in USD
        """
        logger.info(f"Fetching prices for {len(token_addresses)} tokens...")

        if self.use_query_ids:
            params = [
                QueryParameter.text_type(name="token_addresses", value=self._format_addresses(token_addresses))
            ]
            df = self._execute_query_by_id("prices", params=params)
        else:
            query_sql = self._load_query("prices")
            query_sql = query_sql.replace(
                "{{token_addresses}}", self._format_addresses(token_addresses)
            )
            df = self._execute_custom_query(query_sql, "Token Prices")

        if df.empty:
            logger.warning("No price data returned")
            return {}

        # Note: Query already returns most recent price per token via ROW_NUMBER()
        # But we'll sort/deduplicate anyway for safety
        df = df.sort_values("minute", ascending=False)
        df = df.drop_duplicates(subset=["contract_address"], keep="first")

        # Return as dict: address -> price
        price_dict = dict(zip(df["contract_address"].str.lower(), df["price"]))

        logger.info(f"Retrieved prices for {len(price_dict)} tokens")
        return price_dict

    def fetch_all_data(
        self, market_ids: List[str], token_addresses: List[str]
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch all data needed for analysis

        Args:
            market_ids: List of Morpho Blue market IDs
            token_addresses: List of token addresses for pricing

        Returns:
            Dictionary with all DataFrames
        """
        logger.info("Fetching all data for analysis...")

        data = {
            "pool_state": self.fetch_pool_state(market_ids),
            "positions": self.fetch_positions(market_ids),
            "collateral": self.fetch_collateral(market_ids),
            "liquidations": self.fetch_liquidations(market_ids),
            "prices": self.fetch_prices(token_addresses),
        }

        logger.info("All data fetched successfully")
        return data
