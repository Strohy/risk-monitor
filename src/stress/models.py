"""
Stress Testing Models - Data structures for stress test results
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class StressResult:
    """Results from a single stress scenario"""

    scenario_name: str
    price_shock_pct: float
    liquidatable_positions: int
    total_collateral_at_risk_usd: float
    total_debt_at_risk_usd: float
    bad_debt_potential_usd: float
    pct_pool_affected: float
    positions_details: List[Dict]

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            "scenario_name": self.scenario_name,
            "price_shock_pct": self.price_shock_pct,
            "liquidatable_positions": self.liquidatable_positions,
            "total_collateral_at_risk_usd": self.total_collateral_at_risk_usd,
            "total_debt_at_risk_usd": self.total_debt_at_risk_usd,
            "bad_debt_potential_usd": self.bad_debt_potential_usd,
            "pct_pool_affected": self.pct_pool_affected,
            "positions_count": len(self.positions_details),
        }

    def summary(self) -> str:
        """Generate human-readable summary"""
        return f"""
Stress Test: {self.scenario_name}
----------------------------------------
Price Shock: {self.price_shock_pct:+.1f}%
Liquidatable Positions: {self.liquidatable_positions}
Collateral at Risk: ${self.total_collateral_at_risk_usd:,.2f}
Debt at Risk: ${self.total_debt_at_risk_usd:,.2f}
Bad Debt Potential: ${self.bad_debt_potential_usd:,.2f}
Pool Affected: {self.pct_pool_affected:.1f}%
"""
