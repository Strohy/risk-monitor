"""
Stress Testing Engine - Simulates price shocks and liquidation scenarios
"""

import pandas as pd
from typing import List, Dict
from ..state.models import Position, PoolSnapshot
from .models import StressResult


class StressTestEngine:
    """Runs stress test scenarios on pool positions"""

    # Default price shock scenarios (negative = price drops)
    DEFAULT_SCENARIOS = [-0.05, -0.10, -0.15, -0.20, -0.30, -0.40, -0.50]

    def __init__(self, snapshot: PoolSnapshot, scenarios: List[float] = None):
        """
        Initialize stress test engine

        Args:
            snapshot: Pool snapshot to test
            scenarios: List of price shock percentages (e.g., -0.10 for -10%)
        """
        self.snapshot = snapshot
        self.scenarios = scenarios or self.DEFAULT_SCENARIOS

    def apply_price_shock(self, shock_pct: float) -> StressResult:
        """
        Apply price shock to collateral and calculate liquidation impact

        Args:
            shock_pct: Price shock as decimal (e.g., -0.10 for -10% drop)

        Returns:
            StressResult with liquidation metrics
        """
        liquidatable_positions = []

        for pos in self.snapshot.positions:
            # Recalculate health factor after shock
            new_hf = pos.health_factor_after_shock(shock_pct)

            # Position becomes liquidatable if HF < 1.0
            if new_hf < 1.0:
                new_collateral_value = pos.collateral_value_usd * (1 + shock_pct)

                # Shortfall = debt that can't be covered by collateral
                shortfall = max(0, pos.debt_value_usd - new_collateral_value)

                liquidatable_positions.append({
                    'borrower': pos.borrower,
                    'original_hf': pos.health_factor,
                    'new_hf': new_hf,
                    'collateral_value': new_collateral_value,
                    'debt_value': pos.debt_value_usd,
                    'shortfall': shortfall,
                    'liquidation_penalty': new_collateral_value * 0.1  # Assume 10% liquidation penalty
                })

        # Calculate aggregate metrics
        total_collateral_at_risk = sum(p['collateral_value'] for p in liquidatable_positions)
        total_debt_at_risk = sum(p['debt_value'] for p in liquidatable_positions)
        bad_debt_potential = sum(p['shortfall'] for p in liquidatable_positions)

        pct_affected = (
            (total_debt_at_risk / self.snapshot.total_debt_usd * 100)
            if self.snapshot.total_debt_usd > 0
            else 0
        )

        return StressResult(
            scenario_name=f"{shock_pct * 100:+.0f}% price shock",
            price_shock_pct=shock_pct * 100,  # Convert to percentage
            liquidatable_positions=len(liquidatable_positions),
            total_collateral_at_risk_usd=total_collateral_at_risk,
            total_debt_at_risk_usd=total_debt_at_risk,
            bad_debt_potential_usd=bad_debt_potential,
            pct_pool_affected=pct_affected,
            positions_details=liquidatable_positions
        )

    def run_all_scenarios(self) -> pd.DataFrame:
        """
        Run all stress scenarios and return liquidation curve

        Returns:
            DataFrame with results for each scenario
        """
        results = []

        for shock in self.scenarios:
            result = self.apply_price_shock(shock)

            results.append({
                'price_shock_pct': shock * 100,
                'liquidatable_positions': result.liquidatable_positions,
                'collateral_at_risk_usd': result.total_collateral_at_risk_usd,
                'debt_at_risk_usd': result.total_debt_at_risk_usd,
                'bad_debt_potential_usd': result.bad_debt_potential_usd,
                'pct_pool_affected': result.pct_pool_affected
            })

        return pd.DataFrame(results)

    def find_cliff_points(
        self,
        results: pd.DataFrame = None,
        threshold: float = 50.0
    ) -> List[Dict]:
        """
        Identify non-linear risk jumps (cliff points) in liquidation curve

        A cliff point is when risk increases sharply between consecutive scenarios,
        indicating a concentration of positions at similar health factors.

        Args:
            results: DataFrame from run_all_scenarios (if None, will run it)
            threshold: Minimum percentage increase to qualify as cliff (default: 50%)

        Returns:
            List of cliff point dictionaries with risk jump details
        """
        if results is None:
            results = self.run_all_scenarios()

        if len(results) < 2:
            return []

        cliffs = []

        for i in range(1, len(results)):
            prev_risk = results.iloc[i-1]['pct_pool_affected']
            curr_risk = results.iloc[i]['pct_pool_affected']

            # Calculate percentage increase in risk
            if prev_risk > 0:
                risk_increase_pct = ((curr_risk - prev_risk) / prev_risk) * 100
            elif curr_risk > 0:
                # First scenario with risk (coming from 0%)
                risk_increase_pct = float('inf')
            else:
                continue

            if risk_increase_pct > threshold:
                cliffs.append({
                    'from_shock_pct': results.iloc[i-1]['price_shock_pct'],
                    'to_shock_pct': results.iloc[i]['price_shock_pct'],
                    'risk_jump_pct': risk_increase_pct,
                    'from_pool_affected': prev_risk,
                    'to_pool_affected': curr_risk,
                    'absolute_increase': curr_risk - prev_risk,
                    'new_liquidations': (
                        results.iloc[i]['liquidatable_positions'] -
                        results.iloc[i-1]['liquidatable_positions']
                    )
                })

        return cliffs

    def get_liquidation_threshold(self, target_pct: float = 10.0) -> float:
        """
        Find the price shock that would liquidate target_pct of the pool

        Args:
            target_pct: Target percentage of pool debt to liquidate

        Returns:
            Price shock percentage (or None if not reached)
        """
        results = self.run_all_scenarios()

        for _, row in results.iterrows():
            if row['pct_pool_affected'] >= target_pct:
                return row['price_shock_pct']

        return None  # Target not reached even at worst scenario

    def analyze_cascading_risk(self) -> Dict:
        """
        Analyze potential for cascading liquidations

        Returns:
            Dict with cascading risk metrics
        """
        results = self.run_all_scenarios()
        cliffs = self.find_cliff_points(results)

        # Calculate velocity of risk increase
        if len(results) >= 2:
            avg_risk_increase = results['pct_pool_affected'].diff().mean()
            max_risk_increase = results['pct_pool_affected'].diff().max()
        else:
            avg_risk_increase = 0
            max_risk_increase = 0

        return {
            'cliff_points_count': len(cliffs),
            'avg_risk_increase_per_scenario': avg_risk_increase,
            'max_risk_increase_per_scenario': max_risk_increase,
            'has_severe_cliffs': len(cliffs) > 0,
            'worst_cliff': max(cliffs, key=lambda x: x['risk_jump_pct']) if cliffs else None
        }

    def generate_summary(self) -> str:
        """
        Generate comprehensive stress test summary

        Returns:
            Formatted string with stress test analysis
        """
        results = self.run_all_scenarios()
        cliffs = self.find_cliff_points(results)
        cascading = self.analyze_cascading_risk()

        summary = f"""
=== Stress Test Summary ===

Pool: {self.snapshot.pool_name}
Total Positions: {len(self.snapshot.positions)}
Total Debt: ${self.snapshot.total_debt_usd:,.2f}

--- Scenarios Tested ---
"""

        for _, row in results.iterrows():
            summary += f"""
{row['price_shock_pct']:+.0f}% shock:
  - Liquidatable positions: {row['liquidatable_positions']}
  - Debt at risk: ${row['debt_at_risk_usd']:,.2f} ({row['pct_pool_affected']:.1f}%)
  - Bad debt potential: ${row['bad_debt_potential_usd']:,.2f}
"""

        if cliffs:
            summary += "\n--- Cliff Points Detected ---\n"
            for cliff in cliffs:
                summary += f"""
Between {cliff['from_shock_pct']:.0f}% and {cliff['to_shock_pct']:.0f}%:
  - Risk jump: {cliff['risk_jump_pct']:.0f}%
  - New liquidations: {cliff['new_liquidations']}
  - Pool affected increased: {cliff['from_pool_affected']:.1f}% → {cliff['to_pool_affected']:.1f}%
"""

        summary += f"""
--- Cascading Risk Analysis ---
Cliff points found: {cascading['cliff_points_count']}
Severe cascading risk: {'YES' if cascading['has_severe_cliffs'] else 'NO'}
Average risk increase per scenario: {cascading['avg_risk_increase_per_scenario']:.2f}%
Maximum risk increase per scenario: {cascading['max_risk_increase_per_scenario']:.2f}%
"""

        return summary
