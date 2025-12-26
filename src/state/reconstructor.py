"""State reconstruction from raw Dune data"""

import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
import logging

from .models import Position, PoolSnapshot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StateReconstructor:
    """Reconstructs pool state from raw data"""

    def __init__(self, pool_config: dict, prices: Dict[str, float]):
        """
        Initialize state reconstructor

        Args:
            pool_config: Pool configuration from pools.yaml
            prices: Dictionary mapping token addresses to USD prices
        """
        self.pool_config = pool_config
        self.prices = prices

        # Normalize addresses to lowercase for comparison
        self.prices = {k.lower(): v for k, v in prices.items()}

        # Get decimals for token normalization (Morpho stores all values in loan token units)
        self.loan_decimals = pool_config.get('decimals', 18)

        logger.info(f"Initialized reconstructor for {pool_config['name']}")
        logger.info(f"  Loan token decimals: {self.loan_decimals}")

    def _get_token_price(self, address: str) -> float:
        """Get token price with fallback"""
        address = address.lower()

        if address in self.prices:
            return self.prices[address]

        logger.warning(f"Price not found for {address}, using 0")
        return 0.0

    def reconstruct_positions(
        self,
        positions_df: pd.DataFrame,
        collateral_df: pd.DataFrame
    ) -> List[Position]:
        """
        Convert raw position data into Position objects with health factors

        Args:
            positions_df: DataFrame with borrow data
            collateral_df: DataFrame with collateral data

        Returns:
            List of Position objects
        """
        logger.info("Reconstructing positions...")

        if positions_df.empty:
            logger.warning("No positions data available")
            return []

        # Normalize column names (handle both 'id' and 'market_id')
        if 'id' in positions_df.columns and 'market_id' not in positions_df.columns:
            positions_df = positions_df.rename(columns={'id': 'market_id'})
        if 'id' in collateral_df.columns and 'market_id' not in collateral_df.columns:
            collateral_df = collateral_df.rename(columns={'id': 'market_id'})

        # Normalize collateral column name (query returns 'collateral', code expects 'collateral_assets')
        if 'collateral' in collateral_df.columns and 'collateral_assets' not in collateral_df.columns:
            collateral_df = collateral_df.rename(columns={'collateral': 'collateral_assets'})

        # Merge positions with collateral
        merged = positions_df.merge(
            collateral_df,
            on=['market_id', 'borrower'],
            how='left',
            suffixes=('_borrow', '_collateral')
        )

        # Fill missing collateral with 0
        merged['collateral_assets'] = merged['collateral_assets'].fillna(0)

        # Get loan token price (Morpho stores all values in loan token terms)
        loan_price = self._get_token_price(self.pool_config['loan_address'])
        lltv = self.pool_config['lltv']

        logger.info(f"Using {self.pool_config['loan']} price: ${loan_price:.2f}")

        positions = []

        for _, row in merged.iterrows():
            try:
                # Extract raw amounts (Morpho stores all values in loan token units)
                collateral_amount_raw = float(row['collateral_assets'])
                debt_amount_raw = float(row.get('active_borrow_assets', row.get('active_borrow_shares', 0)))

                # Normalize to human-readable units by dividing by 10^loan_decimals
                # Both collateral and debt are denominated in loan token
                collateral_amount = collateral_amount_raw / (10 ** self.loan_decimals)
                debt_amount = debt_amount_raw / (10 ** self.loan_decimals)

                # Convert to USD (both already in loan token terms, just multiply by loan price)
                collateral_value = collateral_amount * loan_price
                debt_value = debt_amount * loan_price

                # Calculate health factor: (collateral_value * LLTV) / debt_value
                if debt_value > 0:
                    health_factor = (collateral_value * lltv) / debt_value
                else:
                    health_factor = float('inf')

                # Get timestamp
                timestamp = row.get('last_borrow_time', row.get('block_time'))
                if timestamp and not isinstance(timestamp, datetime):
                    timestamp = pd.to_datetime(timestamp)

                position = Position(
                    borrower=row['borrower'],
                    market_id=row['market_id'],
                    collateral_amount=collateral_amount,
                    collateral_value_usd=collateral_value,
                    debt_amount=debt_amount,
                    debt_value_usd=debt_value,
                    health_factor=health_factor,
                    lltv=lltv,
                    timestamp=timestamp or datetime.now()
                )

                positions.append(position)

            except Exception as e:
                logger.warning(f"Error processing position for {row.get('borrower')}: {e}")
                continue

        logger.info(f"Reconstructed {len(positions)} positions")

        # Log health factor statistics
        if positions:
            healthy = sum(1 for p in positions if p.is_healthy)
            logger.info(f"  Healthy positions: {healthy}/{len(positions)} "
                       f"({healthy/len(positions)*100:.1f}%)")

            finite_hfs = [p.health_factor for p in positions if p.health_factor != float('inf')]
            if finite_hfs:
                avg_hf = sum(finite_hfs) / len(finite_hfs)
                min_hf = min(finite_hfs)
                max_hf = max(finite_hfs)
                logger.info(f"  Health factors: avg={avg_hf:.2f}, min={min_hf:.2f}, max={max_hf:.2f}")

        return positions

    def create_snapshot(
        self,
        positions_df: pd.DataFrame,
        collateral_df: pd.DataFrame,
        pool_state_df: pd.DataFrame,
        timestamp: Optional[datetime] = None
    ) -> PoolSnapshot:
        """
        Create a complete pool snapshot

        Args:
            positions_df: DataFrame with borrow positions
            collateral_df: DataFrame with collateral data
            pool_state_df: DataFrame with pool state metrics
            timestamp: Snapshot timestamp (default: now)

        Returns:
            PoolSnapshot object
        """
        logger.info(f"Creating snapshot for {self.pool_config['name']}...")

        # Reconstruct positions
        positions = self.reconstruct_positions(positions_df, collateral_df)

        # Get latest pool state
        if not pool_state_df.empty:
            # Sort by call_block_time descending and take first
            pool_state_df = pool_state_df.sort_values('call_block_time', ascending=False)
            latest_state = pool_state_df.iloc[0]

            # Get raw values and normalize to human-readable units
            total_supply_raw = float(latest_state.get('output_totalSupplyAssets', 0))
            total_borrow_raw = float(latest_state.get('output_totalBorrowAssets', 0))

            # Normalize by loan token decimals (pool state is in loan token)
            total_supply = total_supply_raw / (10 ** self.loan_decimals)
            total_borrow = total_borrow_raw / (10 ** self.loan_decimals)

            # Convert to USD
            loan_price = self._get_token_price(self.pool_config['loan_address'])
            total_supply = total_supply * loan_price
            total_borrow = total_borrow * loan_price

            if total_supply > 0:
                utilization = total_borrow / total_supply
            else:
                utilization = 0.0
        else:
            logger.warning("No pool state data, using aggregated values")
            total_supply = sum(p.collateral_value_usd for p in positions)
            total_borrow = sum(p.debt_value_usd for p in positions)
            utilization = total_borrow / total_supply if total_supply > 0 else 0.0

        snapshot = PoolSnapshot(
            market_id=self.pool_config['market_id'],
            pool_name=self.pool_config['name'],
            timestamp=timestamp or datetime.now(),
            positions=positions,
            total_supply=total_supply,
            total_borrow=total_borrow,
            utilization=utilization,
            lltv=self.pool_config['lltv']
        )

        logger.info(f"Snapshot created: {snapshot.num_positions} positions, "
                   f"utilization={snapshot.utilization*100:.1f}%")

        return snapshot

    def save_snapshot(self, snapshot: PoolSnapshot, output_path: str):
        """
        Save snapshot to JSON file

        Args:
            snapshot: PoolSnapshot to save
            output_path: Path to save JSON file
        """
        import json
        from pathlib import Path

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        snapshot_data = {
            'snapshot': snapshot.to_dict(),
            'positions': [p.to_dict() for p in snapshot.positions]
        }

        with open(output_path, 'w') as f:
            json.dump(snapshot_data, f, indent=2, default=str)

        logger.info(f"Snapshot saved to {output_path}")

    def load_snapshot(self, input_path: str) -> PoolSnapshot:
        """
        Load snapshot from JSON file

        Args:
            input_path: Path to JSON file

        Returns:
            PoolSnapshot object
        """
        import json
        from pathlib import Path

        input_path = Path(input_path)

        with open(input_path, 'r') as f:
            data = json.load(f)

        # Reconstruct positions
        positions = []
        for p_data in data['positions']:
            position = Position(
                borrower=p_data['borrower'],
                market_id=p_data['market_id'],
                collateral_amount=p_data['collateral_amount'],
                collateral_value_usd=p_data['collateral_value_usd'],
                debt_amount=p_data['debt_amount'],
                debt_value_usd=p_data['debt_value_usd'],
                health_factor=p_data['health_factor'],
                lltv=p_data['lltv'],
                timestamp=datetime.fromisoformat(p_data['timestamp']) if p_data['timestamp'] else None
            )
            positions.append(position)

        # Reconstruct snapshot
        snapshot_data = data['snapshot']
        snapshot = PoolSnapshot(
            market_id=snapshot_data['market_id'],
            pool_name=snapshot_data['pool_name'],
            timestamp=datetime.fromisoformat(snapshot_data['timestamp']) if snapshot_data['timestamp'] else None,
            positions=positions,
            total_supply=snapshot_data['total_supply'],
            total_borrow=snapshot_data['total_borrow'],
            utilization=snapshot_data['utilization'],
            lltv=snapshot_data['lltv']
        )

        logger.info(f"Snapshot loaded from {input_path}")

        return snapshot
