"""Data models for pool positions and snapshots"""

from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class Position:
    """Represents a single borrower position in a lending pool"""

    borrower: str
    market_id: str
    collateral_amount: float
    collateral_value_usd: float
    debt_amount: float
    debt_value_usd: float
    health_factor: float
    lltv: float
    timestamp: datetime

    @property
    def liquidation_price(self) -> float:
        """
        Calculate the collateral price at which position becomes liquidatable

        Returns:
            Price in USD where health factor = 1.0
        """
        if self.collateral_amount == 0:
            return 0.0

        # At liquidation: (collateral_value * LLTV) / debt_value = 1.0
        # So: collateral_value = debt_value / LLTV
        # And: liquidation_price = (debt_value / LLTV) / collateral_amount
        return self.debt_value_usd / (self.collateral_amount * self.lltv)

    @property
    def is_healthy(self) -> bool:
        """Check if position is above liquidation threshold"""
        return self.health_factor > 1.0

    @property
    def liquidation_buffer(self) -> float:
        """
        Calculate buffer above liquidation threshold

        Returns:
            Percentage buffer (e.g., 0.15 means 15% above liquidation)
        """
        if self.health_factor == float("inf"):
            return float("inf")

        return self.health_factor - 1.0

    def health_factor_after_shock(self, price_shock_pct: float) -> float:
        """
        Calculate health factor after a collateral price shock

        Args:
            price_shock_pct: Price change as decimal (e.g., -0.10 for -10%)

        Returns:
            New health factor after shock
        """
        new_collateral_value = self.collateral_value_usd * (1 + price_shock_pct)

        if self.debt_value_usd == 0:
            return float("inf")

        return (new_collateral_value * self.lltv) / self.debt_value_usd

    def liquidation_price_drop_pct(self) -> float:
        """
        Calculate percentage drop in collateral price needed to reach liquidation

        Returns:
            Percentage drop needed (e.g., 0.15 means 15% drop)
        """
        if self.health_factor == float("inf") or self.health_factor <= 1.0:
            return 0.0

        # HF = (collateral_value * LLTV) / debt_value
        # At liquidation: HF = 1.0
        # So price_drop = 1 - (1 / HF)
        return 1.0 - (1.0 / self.health_factor)

    def to_dict(self) -> dict:
        """Convert position to dictionary"""
        return {
            "borrower": self.borrower,
            "market_id": self.market_id,
            "collateral_amount": self.collateral_amount,
            "collateral_value_usd": self.collateral_value_usd,
            "debt_amount": self.debt_amount,
            "debt_value_usd": self.debt_value_usd,
            "health_factor": self.health_factor,
            "lltv": self.lltv,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "liquidation_price": self.liquidation_price,
            "is_healthy": self.is_healthy,
            "liquidation_buffer": self.liquidation_buffer,
        }


@dataclass
class PoolSnapshot:
    """Complete snapshot of a lending pool at a point in time"""

    market_id: str
    pool_name: str
    timestamp: datetime
    positions: List[Position]
    total_supply: float
    total_borrow: float
    utilization: float
    lltv: float

    @property
    def total_collateral_usd(self) -> float:
        """Total collateral value across all positions"""
        return sum(p.collateral_value_usd for p in self.positions)

    @property
    def total_debt_usd(self) -> float:
        """Total debt value across all positions"""
        return sum(p.debt_value_usd for p in self.positions)

    @property
    def num_positions(self) -> int:
        """Number of open positions"""
        return len(self.positions)

    @property
    def num_healthy_positions(self) -> int:
        """Number of healthy positions (HF > 1.0)"""
        return sum(1 for p in self.positions if p.is_healthy)

    @property
    def num_unhealthy_positions(self) -> int:
        """Number of positions at or below liquidation threshold"""
        return sum(1 for p in self.positions if not p.is_healthy)

    @property
    def avg_health_factor(self) -> float:
        """Simple average health factor across positions"""
        if not self.positions:
            return float("inf")

        finite_hfs = [
            p.health_factor for p in self.positions if p.health_factor != float("inf")
        ]

        if not finite_hfs:
            return float("inf")

        return sum(finite_hfs) / len(finite_hfs)

    @property
    def weighted_avg_health_factor(self) -> float:
        """Debt-weighted average health factor"""
        if not self.positions:
            return float("inf")

        total_debt = self.total_debt_usd

        if total_debt == 0:
            return float("inf")

        weighted_sum = sum(
            p.health_factor * p.debt_value_usd
            for p in self.positions
            if p.health_factor != float("inf")
        )

        return weighted_sum / total_debt

    def get_positions_by_health_factor(
        self, min_hf: float = None, max_hf: float = None
    ) -> List[Position]:
        """
        Filter positions by health factor range

        Args:
            min_hf: Minimum health factor (inclusive)
            max_hf: Maximum health factor (inclusive)

        Returns:
            List of positions in range
        """
        filtered = self.positions

        if min_hf is not None:
            filtered = [p for p in filtered if p.health_factor >= min_hf]

        if max_hf is not None:
            filtered = [p for p in filtered if p.health_factor <= max_hf]

        return filtered

    def get_top_borrowers(self, n: int = 10) -> List[Position]:
        """
        Get top N borrowers by debt value

        Args:
            n: Number of top positions to return

        Returns:
            List of positions sorted by debt (descending)
        """
        return sorted(self.positions, key=lambda p: p.debt_value_usd, reverse=True)[:n]

    def to_dict(self) -> dict:
        """Convert snapshot to dictionary"""
        return {
            "market_id": self.market_id,
            "pool_name": self.pool_name,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "num_positions": self.num_positions,
            "total_supply": self.total_supply,
            "total_borrow": self.total_borrow,
            "utilization": self.utilization,
            "lltv": self.lltv,
            "total_collateral_usd": self.total_collateral_usd,
            "total_debt_usd": self.total_debt_usd,
            "avg_health_factor": self.avg_health_factor,
            "weighted_avg_health_factor": self.weighted_avg_health_factor,
            "num_healthy_positions": self.num_healthy_positions,
            "num_unhealthy_positions": self.num_unhealthy_positions,
        }
