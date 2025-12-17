"""Dune Analytics API client for fetching Morpho Blue data"""

from dune_client.client import DuneClient
from dune_client.query import QueryBase 
import pandas as pd
from typing import List, Dict, Optional
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MorphoDataFetcher:
    """Fetches Morpho Blue data from Dune Analytics"""

    def __init__(self, api_key: str):
        """
        Initialize Dune client

        Args:
            api_key: Dune Analytics API key
        """
        self.client = DuneClient(api_key)
        self.queries_dir = Path(__file__).parent.parent.parent / "queries"
        logger.info("Initialized Dune client")

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

        with open(query_path, 'r') as f:
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

        query_sql = self._load_query("pool_state")
        query_sql = query_sql.replace("{{market_ids}}", self._format_market_ids(market_ids))

        query = self.client.create_query(
            name="Pool State",
            query_sql=query_sql
        )

        try:
            result = self.client.run_query(query)
            df = pd.DataFrame(result.result.rows)
            logger.info(f"Retrieved {len(df)} pool state records")
            return df
        except Exception as e:
            logger.error(f"Error fetching pool state: {e}")
            raise

    def fetch_positions(self, market_ids: List[str]) -> pd.DataFrame:
        """
        Fetch all open positions

        Args:
            market_ids: List of Morpho Blue market IDs

        Returns:
            DataFrame with position data
        """
        logger.info(f"Fetching positions for {len(market_ids)} markets...")

        query_sql = self._load_query("positions")
        query_sql = query_sql.replace("{{market_ids}}", self._format_market_ids(market_ids))

        query = self.client.create_query(
            name="Open Positions",
            query_sql=query_sql
        )

        try:
            result = self.client.run_query(query)
            df = pd.DataFrame(result.result.rows)
            logger.info(f"Retrieved {len(df)} open positions")
            return df
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            raise

    def fetch_collateral(self, market_ids: List[str]) -> pd.DataFrame:
        """
        Fetch collateral balances for positions

        Args:
            market_ids: List of Morpho Blue market IDs

        Returns:
            DataFrame with collateral data
        """
        logger.info(f"Fetching collateral for {len(market_ids)} markets...")

        query_sql = self._load_query("collateral")
        query_sql = query_sql.replace("{{market_ids}}", self._format_market_ids(market_ids))

        query = self.client.create_query(
            name="Collateral Balances",
            query_sql=query_sql
        )

        try:
            result = self.client.run_query(query)
            df = pd.DataFrame(result.result.rows)
            logger.info(f"Retrieved {len(df)} collateral records")
            return df
        except Exception as e:
            logger.error(f"Error fetching collateral: {e}")
            raise

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

        query_sql = self._load_query("liquidations")
        query_sql = query_sql.replace("{{market_ids}}", self._format_market_ids(market_ids))

        query = self.client.create_query(
            name="Historical Liquidations",
            query_sql=query_sql
        )

        try:
            result = self.client.run_query(query)
            df = pd.DataFrame(result.result.rows)
            logger.info(f"Retrieved {len(df)} liquidation events")
            return df
        except Exception as e:
            logger.error(f"Error fetching liquidations: {e}")
            raise

    def fetch_prices(self, token_addresses: List[str]) -> Dict[str, float]:
        """
        Fetch current token prices

        Args:
            token_addresses: List of token contract addresses

        Returns:
            Dictionary mapping address to price in USD
        """
        logger.info(f"Fetching prices for {len(token_addresses)} tokens...")

        query_sql = self._load_query("prices")
        query_sql = query_sql.replace("{{token_addresses}}", self._format_addresses(token_addresses))

        query = self.client.create_query(
            name="Token Prices",
            query_sql=query_sql
        )

        try:
            result = self.client.run_query(query)
            df = pd.DataFrame(result.result.rows)

            if df.empty:
                logger.warning("No price data returned")
                return {}

            # Take the most recent price for each token
            df = df.sort_values('timestamp', ascending=False)
            df = df.drop_duplicates(subset=['contract_address'], keep='first')

            # Return as dict: address -> price
            price_dict = dict(zip(
                df['contract_address'].str.lower(),
                df['price']
            ))

            logger.info(f"Retrieved prices for {len(price_dict)} tokens")
            return price_dict

        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            raise

    def fetch_all_data(self, market_ids: List[str], token_addresses: List[str]) -> Dict[str, pd.DataFrame]:
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
            'pool_state': self.fetch_pool_state(market_ids),
            'positions': self.fetch_positions(market_ids),
            'collateral': self.fetch_collateral(market_ids),
            'liquidations': self.fetch_liquidations(market_ids),
            'prices': self.fetch_prices(token_addresses)
        }

        logger.info("All data fetched successfully")
        return data
