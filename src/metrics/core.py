"""
Risk Metrics Engine - Calculates risk metrics for pool snapshots
"""

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from ..state.models import PoolSnapshot, Position


class RiskMetrics:
    """Calculates risk metrics for a pool snapshot"""

    def __init__(self, snapshot: PoolSnapshot):
        self.snapshot = snapshot
        self.positions = snapshot.positions

    # ====== Baseline Metrics ======

    def utilization_rate(self) -> float:
        """
        Total borrow / total supply

        Returns:
            Utilization rate as a decimal (e.g., 0.75 = 75%)
        """
        return self.snapshot.utilization

    def concentration_metrics(self) -> Dict[str, float]:
        """
        Top N borrower concentration metrics

        Returns:
            Dict with top_5_pct, top_10_pct, top_5_debt_usd, top_10_debt_usd
        """
        if not self.positions:
            return {
                "top_5_pct": 0,
                "top_10_pct": 0,
                "top_5_debt_usd": 0,
                "top_10_debt_usd": 0,
            }

        # Sort by debt value
        sorted_positions = sorted(
            self.positions, key=lambda p: p.debt_value_usd, reverse=True
        )

        total_debt = self.snapshot.total_debt_usd

        if total_debt == 0:
            return {
                "top_5_pct": 0,
                "top_10_pct": 0,
                "top_5_debt_usd": 0,
                "top_10_debt_usd": 0,
            }

        top_5_debt = sum(p.debt_value_usd for p in sorted_positions[:5])
        top_10_debt = sum(p.debt_value_usd for p in sorted_positions[:10])

        return {
            "top_5_pct": (top_5_debt / total_debt * 100),
            "top_10_pct": (top_10_debt / total_debt * 100),
            "top_5_debt_usd": top_5_debt,
            "top_10_debt_usd": top_10_debt,
        }

    def gini_coefficient(self) -> float:
        """
        Borrow distribution inequality

        Returns:
            Gini coefficient (0 = equal distribution, 1 = maximum concentration)
        """
        if not self.positions:
            return 0.0

        debt_values = sorted([p.debt_value_usd for p in self.positions])
        n = len(debt_values)

        if sum(debt_values) == 0:
            return 0.0

        # Calculate Gini coefficient
        index = np.arange(1, n + 1)
        return (2 * np.sum(index * debt_values)) / (n * np.sum(debt_values)) - (
            n + 1
        ) / n

    def herfindahl_index(self) -> float:
        """
        Herfindahl-Hirschman Index for debt concentration

        Returns:
            HHI (0-10000, higher = more concentrated)
        """
        if not self.positions:
            return 0.0

        total_debt = self.snapshot.total_debt_usd

        if total_debt == 0:
            return 0.0

        # Calculate market shares and sum of squares
        market_shares = [(p.debt_value_usd / total_debt * 100) for p in self.positions]
        hhi = sum(share**2 for share in market_shares)

        return hhi

    # ====== Health Factor Analysis ======

    def weighted_avg_health_factor(self) -> float:
        """
        Debt-weighted average health factor

        Returns:
            Weighted average HF (inf if no debt)
        """
        if not self.positions:
            return float("inf")

        total_debt = sum(p.debt_value_usd for p in self.positions)

        if total_debt == 0:
            return float("inf")

        weighted_sum = sum(
            p.health_factor * p.debt_value_usd
            for p in self.positions
            if p.health_factor != float("inf")
        )

        return weighted_sum / total_debt

    def health_factor_distribution(self) -> Dict[str, float]:
        """
        Distribution of positions by health factor buckets

        Returns:
            Dict with percentage of debt in each HF range
        """
        if not self.positions:
            return {
                "hf_below_1.05": 0,
                "hf_1.05_to_1.1": 0,
                "hf_1.1_to_1.2": 0,
                "hf_1.2_to_1.5": 0,
                "hf_above_1.5": 0,
            }

        total_debt = self.snapshot.total_debt_usd

        if total_debt == 0:
            return {
                "hf_below_1.05": 0,
                "hf_1.05_to_1.1": 0,
                "hf_1.1_to_1.2": 0,
                "hf_1.2_to_1.5": 0,
                "hf_above_1.5": 0,
            }

        buckets = {
            "hf_below_1.05": 0,
            "hf_1.05_to_1.1": 0,
            "hf_1.1_to_1.2": 0,
            "hf_1.2_to_1.5": 0,
            "hf_above_1.5": 0,
        }

        for p in self.positions:
            hf = p.health_factor
            debt = p.debt_value_usd

            if hf < 1.05:
                buckets["hf_below_1.05"] += debt
            elif hf < 1.1:
                buckets["hf_1.05_to_1.1"] += debt
            elif hf < 1.2:
                buckets["hf_1.1_to_1.2"] += debt
            elif hf < 1.5:
                buckets["hf_1.2_to_1.5"] += debt
            else:
                buckets["hf_above_1.5"] += debt

        # Convert to percentages
        return {k: (v / total_debt * 100) for k, v in buckets.items()}

    def liquidation_buffer_percentage(self, threshold: float = 1.1) -> float:
        """
        Percentage of debt with health factor below threshold

        Args:
            threshold: Health factor threshold

        Returns:
            Percentage of total debt at risk
        """
        if not self.positions:
            return 0.0

        total_debt = self.snapshot.total_debt_usd

        if total_debt == 0:
            return 0.0

        at_risk_debt = sum(
            p.debt_value_usd for p in self.positions if p.health_factor < threshold
        )

        return at_risk_debt / total_debt * 100

    def positions_at_risk(self, threshold: float = 1.1) -> List[Position]:
        """
        Get all positions with health factor below threshold

        Args:
            threshold: Health factor threshold

        Returns:
            List of at-risk positions, sorted by health factor
        """
        at_risk = [p for p in self.positions if p.health_factor < threshold]

        return sorted(at_risk, key=lambda p: p.health_factor)

    # ====== Position Distribution ======

    def position_size_distribution(self) -> Dict[str, int]:
        """
        Distribution of positions by debt size buckets

        Returns:
            Dict with count of positions in each size range
        """
        if not self.positions:
            return {
                "micro_below_10k": 0,
                "small_10k_to_100k": 0,
                "medium_100k_to_1m": 0,
                "large_1m_to_10m": 0,
                "whale_above_10m": 0,
            }

        buckets = {
            "micro_below_10k": 0,
            "small_10k_to_100k": 0,
            "medium_100k_to_1m": 0,
            "large_1m_to_10m": 0,
            "whale_above_10m": 0,
        }

        for p in self.positions:
            debt_usd = p.debt_value_usd

            if debt_usd < 10_000:
                buckets["micro_below_10k"] += 1
            elif debt_usd < 100_000:
                buckets["small_10k_to_100k"] += 1
            elif debt_usd < 1_000_000:
                buckets["medium_100k_to_1m"] += 1
            elif debt_usd < 10_000_000:
                buckets["large_1m_to_10m"] += 1
            else:
                buckets["whale_above_10m"] += 1

        return buckets

    # ====== Summary Report ======

    def compute_all_metrics(self) -> Dict[str, any]:
        """
        Compute all risk metrics and return as a dictionary

        Returns:
            Dict with all risk metrics
        """
        concentration = self.concentration_metrics()
        hf_dist = self.health_factor_distribution()
        size_dist = self.position_size_distribution()

        return {
            # Pool-level metrics
            "utilization_rate": self.utilization_rate(),
            "total_positions": len(self.positions),
            "total_debt_usd": self.snapshot.total_debt_usd,
            "total_collateral_usd": self.snapshot.total_collateral_usd,
            # Concentration metrics
            "top_5_concentration_pct": concentration["top_5_pct"],
            "top_10_concentration_pct": concentration["top_10_pct"],
            "top_5_debt_usd": concentration["top_5_debt_usd"],
            "top_10_debt_usd": concentration["top_10_debt_usd"],
            "gini_coefficient": self.gini_coefficient(),
            "herfindahl_index": self.herfindahl_index(),
            # Health factor metrics
            "weighted_avg_health_factor": self.weighted_avg_health_factor(),
            "debt_below_hf_1_05_pct": hf_dist["hf_below_1.05"],
            "debt_below_hf_1_1_pct": hf_dist["hf_below_1.05"]
            + hf_dist["hf_1.05_to_1.1"],
            "liquidation_buffer_10pct": self.liquidation_buffer_percentage(1.1),
            "positions_at_risk_count": len(self.positions_at_risk(1.1)),
            # Position size distribution
            "micro_positions": size_dist["micro_below_10k"],
            "small_positions": size_dist["small_10k_to_100k"],
            "medium_positions": size_dist["medium_100k_to_1m"],
            "large_positions": size_dist["large_1m_to_10m"],
            "whale_positions": size_dist["whale_above_10m"],
        }

    def summary_report(self) -> str:
        """
        Generate a human-readable summary report

        Returns:
            Formatted string with key metrics
        """
        metrics = self.compute_all_metrics()

        report = f"""
=== Risk Metrics Summary ===

Pool: {self.snapshot.pool_name}
Timestamp: {self.snapshot.timestamp}

--- Pool Overview ---
Total Positions: {metrics['total_positions']}
Total Debt: ${metrics['total_debt_usd']:,.2f}
Total Collateral: ${metrics['total_collateral_usd']:,.2f}
Utilization Rate: {metrics['utilization_rate']:.2%}

--- Concentration Risk ---
Top 5 Borrowers: {metrics['top_5_concentration_pct']:.1f}% of debt (${metrics['top_5_debt_usd']:,.2f})
Top 10 Borrowers: {metrics['top_10_concentration_pct']:.1f}% of debt (${metrics['top_10_debt_usd']:,.2f})
Gini Coefficient: {metrics['gini_coefficient']:.3f}
Herfindahl Index: {metrics['herfindahl_index']:.0f}

--- Health Factor Analysis ---
Weighted Avg HF: {metrics['weighted_avg_health_factor']:.3f}
Debt with HF < 1.05: {metrics['debt_below_hf_1_05_pct']:.1f}%
Debt with HF < 1.1: {metrics['debt_below_hf_1_1_pct']:.1f}%
Positions at Risk (HF < 1.1): {metrics['positions_at_risk_count']}

--- Position Distribution ---
Micro (<$10k): {metrics['micro_positions']}
Small ($10k-$100k): {metrics['small_positions']}
Medium ($100k-$1M): {metrics['medium_positions']}
Large ($1M-$10M): {metrics['large_positions']}
Whale (>$10M): {metrics['whale_positions']}
"""
        return report
