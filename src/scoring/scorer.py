"""
Risk Scoring Framework - Calculates composite risk scores
"""

from typing import Dict
import pandas as pd
from ..metrics.core import RiskMetrics
from ..stress.engine import StressTestEngine


class RiskScorer:
    """Calculates composite risk score for a pool (0-100, higher = riskier)"""

    # Configurable weights for different risk components
    DEFAULT_WEIGHTS = {
        'utilization': 0.15,
        'health_factor': 0.30,
        'concentration': 0.25,
        'stress_sensitivity': 0.30
    }

    def __init__(
        self,
        metrics: RiskMetrics,
        stress_engine: StressTestEngine = None,
        weights: Dict[str, float] = None
    ):
        """
        Initialize risk scorer

        Args:
            metrics: RiskMetrics instance with calculated metrics
            stress_engine: StressTestEngine instance (optional)
            weights: Custom weights for risk components (optional)
        """
        self.metrics = metrics
        self.stress_engine = stress_engine
        self.weights = weights or self.DEFAULT_WEIGHTS

        # Validate weights sum to 1.0
        weight_sum = sum(self.weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {weight_sum}")

    def _score_utilization(self, utilization: float) -> float:
        """
        Score utilization (0-100, higher = riskier)

        Scoring logic:
        - >90% = very risky (90-100 points)
        - 70-90% = moderate risk (50-90 points)
        - <70% = low risk (0-50 points)

        Args:
            utilization: Utilization rate as decimal (e.g., 0.85)

        Returns:
            Risk score (0-100)
        """
        if utilization > 0.90:
            # Very risky: scale from 90 to 100
            return 90 + min((utilization - 0.90) * 100, 10)
        elif utilization > 0.70:
            # Moderate: scale from 50 to 90
            return 50 + (utilization - 0.70) * 200
        else:
            # Low risk: linear scale from 0 to 50
            return utilization * 71.4

    def _score_health_factor(self, weighted_hf: float, buffer_pct: float) -> float:
        """
        Score health factor metrics (0-100, higher = riskier)

        Combines weighted average HF and liquidation buffer

        Args:
            weighted_hf: Weighted average health factor
            buffer_pct: Percentage of debt with HF < 1.1

        Returns:
            Risk score (0-100)
        """
        # Score based on weighted HF
        if weighted_hf == float('inf'):
            hf_score = 0
        elif weighted_hf < 1.1:
            hf_score = 100  # Critical
        elif weighted_hf < 1.3:
            hf_score = 80  # High risk
        elif weighted_hf < 1.5:
            hf_score = 60  # Moderate
        elif weighted_hf < 2.0:
            hf_score = 40  # Low
        else:
            hf_score = max(0, 40 - (weighted_hf - 2.0) * 10)

        # Score based on liquidation buffer
        if buffer_pct > 30:
            buffer_score = 100
        elif buffer_pct > 20:
            buffer_score = 80
        elif buffer_pct > 10:
            buffer_score = 60
        elif buffer_pct > 5:
            buffer_score = 40
        else:
            buffer_score = buffer_pct * 8  # Linear scale

        # Combine (60% HF, 40% buffer)
        return hf_score * 0.6 + buffer_score * 0.4

    def _score_concentration(self, top_5_pct: float, herfindahl: float) -> float:
        """
        Score concentration risk (0-100, higher = riskier)

        Uses both top borrower concentration and Herfindahl index

        Args:
            top_5_pct: Percentage of debt held by top 5 borrowers
            herfindahl: Herfindahl-Hirschman Index (0-10000)

        Returns:
            Risk score (0-100)
        """
        # Score based on top 5 concentration
        if top_5_pct > 80:
            top5_score = 100
        elif top_5_pct > 60:
            top5_score = 70 + (top_5_pct - 60) * 1.5
        elif top_5_pct > 40:
            top5_score = 40 + (top_5_pct - 40) * 1.5
        else:
            top5_score = top_5_pct

        # Score based on HHI (normalize from 0-10000 to 0-100)
        # HHI > 2500 = highly concentrated
        # HHI > 1500 = moderately concentrated
        # HHI < 1500 = not concentrated
        if herfindahl > 2500:
            hhi_score = 70 + min((herfindahl - 2500) / 75, 30)
        elif herfindahl > 1500:
            hhi_score = 40 + (herfindahl - 1500) / 33.3
        else:
            hhi_score = herfindahl / 37.5

        # Combine (70% top5, 30% HHI)
        return top5_score * 0.7 + hhi_score * 0.3

    def _score_stress_sensitivity(self) -> float:
        """
        Score stress test sensitivity (0-100, higher = riskier)

        Analyzes how the pool responds to price shocks

        Returns:
            Risk score (0-100)
        """
        if self.stress_engine is None:
            # No stress test available, use conservative default
            return 50

        # Run stress tests
        results_df = self.stress_engine.run_all_scenarios()
        cascading = self.stress_engine.analyze_cascading_risk()

        # Score based on 10% price shock impact
        shock_10_row = results_df[results_df['price_shock_pct'] == -10.0]
        if len(shock_10_row) > 0:
            pct_affected_10 = shock_10_row.iloc[0]['pct_pool_affected']
        else:
            pct_affected_10 = 0

        # Score based on 20% price shock impact
        shock_20_row = results_df[results_df['price_shock_pct'] == -20.0]
        if len(shock_20_row) > 0:
            pct_affected_20 = shock_20_row.iloc[0]['pct_pool_affected']
        else:
            pct_affected_20 = 0

        # Sensitivity score based on 10% shock
        if pct_affected_10 > 30:
            sensitivity_score = 90
        elif pct_affected_10 > 15:
            sensitivity_score = 70
        elif pct_affected_10 > 5:
            sensitivity_score = 50
        else:
            sensitivity_score = pct_affected_10 * 10

        # Cliff penalty
        if cascading['has_severe_cliffs']:
            cliff_penalty = min(cascading['cliff_points_count'] * 10, 30)
        else:
            cliff_penalty = 0

        return min(sensitivity_score + cliff_penalty, 100)

    def calculate_composite_score(self) -> float:
        """
        Calculate composite risk score (0-100, higher = riskier)

        Weighted combination of all risk components

        Returns:
            Composite risk score
        """
        # Get metrics
        all_metrics = self.metrics.compute_all_metrics()
        concentration = self.metrics.concentration_metrics()

        # Calculate component scores
        scores = {
            'utilization': self._score_utilization(all_metrics['utilization_rate']),
            'health_factor': self._score_health_factor(
                all_metrics['weighted_avg_health_factor'],
                all_metrics['liquidation_buffer_10pct']
            ),
            'concentration': self._score_concentration(
                concentration['top_5_pct'],
                all_metrics['herfindahl_index']
            ),
            'stress_sensitivity': self._score_stress_sensitivity()
        }

        # Weighted average
        composite = sum(scores[k] * self.weights[k] for k in scores)

        return round(composite, 2)

    def get_component_scores(self) -> Dict[str, float]:
        """
        Get individual component scores for transparency

        Returns:
            Dict with score for each component
        """
        all_metrics = self.metrics.compute_all_metrics()
        concentration = self.metrics.concentration_metrics()

        return {
            'utilization': self._score_utilization(all_metrics['utilization_rate']),
            'health_factor': self._score_health_factor(
                all_metrics['weighted_avg_health_factor'],
                all_metrics['liquidation_buffer_10pct']
            ),
            'concentration': self._score_concentration(
                concentration['top_5_pct'],
                all_metrics['herfindahl_index']
            ),
            'stress_sensitivity': self._score_stress_sensitivity()
        }

    def get_risk_level(self, score: float = None) -> str:
        """
        Convert numeric score to risk level label

        Args:
            score: Risk score (if None, calculates composite score)

        Returns:
            Risk level label (MINIMAL/LOW/MODERATE/HIGH/CRITICAL)
        """
        if score is None:
            score = self.calculate_composite_score()

        if score >= 80:
            return "CRITICAL"
        elif score >= 65:
            return "HIGH"
        elif score >= 45:
            return "MODERATE"
        elif score >= 25:
            return "LOW"
        else:
            return "MINIMAL"

    def get_risk_color(self, score: float = None) -> str:
        """
        Get color code for risk level (for UI display)

        Args:
            score: Risk score (if None, calculates composite score)

        Returns:
            Color name (red/orange/yellow/green)
        """
        level = self.get_risk_level(score)

        color_map = {
            'CRITICAL': 'red',
            'HIGH': 'orange',
            'MODERATE': 'yellow',
            'LOW': 'lightgreen',
            'MINIMAL': 'green'
        }

        return color_map.get(level, 'gray')

    def generate_report(self) -> str:
        """
        Generate comprehensive risk scoring report

        Returns:
            Formatted string with all scores and explanations
        """
        composite_score = self.calculate_composite_score()
        component_scores = self.get_component_scores()
        risk_level = self.get_risk_level(composite_score)

        report = f"""
=== Risk Score Report ===

Pool: {self.metrics.snapshot.pool_name}

--- Composite Risk Score ---
Overall Score: {composite_score:.1f} / 100
Risk Level: {risk_level}

--- Component Scores ---
"""

        for component, score in component_scores.items():
            weight = self.weights[component] * 100
            contribution = score * self.weights[component]
            report += f"{component.replace('_', ' ').title()}: {score:.1f} / 100 (weight: {weight:.0f}%, contributes {contribution:.1f})\n"

        report += f"""
--- Risk Level Guidelines ---
MINIMAL (0-25): Very low risk, healthy pool
LOW (25-45): Low risk, generally safe
MODERATE (45-65): Moderate risk, monitor closely
HIGH (65-80): High risk, intervention recommended
CRITICAL (80-100): Critical risk, immediate action required

--- Interpretation ---
"""

        # Add interpretations based on scores
        if composite_score >= 80:
            report += "⚠ CRITICAL: This pool has severe risk factors that require immediate attention.\n"
        elif composite_score >= 65:
            report += "⚠ HIGH RISK: This pool has significant risk factors. Close monitoring recommended.\n"
        elif composite_score >= 45:
            report += "⚡ MODERATE RISK: This pool has some risk factors. Regular monitoring advised.\n"
        elif composite_score >= 25:
            report += "✓ LOW RISK: This pool appears relatively healthy with minor risk factors.\n"
        else:
            report += "✓ MINIMAL RISK: This pool appears very healthy.\n"

        # Highlight top risk factors
        sorted_components = sorted(component_scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_components[0][1] > 60:
            report += f"\nTop risk factor: {sorted_components[0][0].replace('_', ' ').title()} (score: {sorted_components[0][1]:.1f})\n"

        return report
