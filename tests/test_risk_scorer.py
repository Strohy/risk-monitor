"""
Tests for Risk Scoring Framework
"""

from datetime import datetime

import pytest

from src.metrics.core import RiskMetrics
from src.scoring.scorer import RiskScorer
from src.state.models import PoolSnapshot, Position
from src.stress.engine import StressTestEngine


@pytest.fixture
def healthy_positions():
    """Create healthy positions (low risk)"""
    return [
        Position(
            borrower=f"0x{i:040x}",
            market_id="0xmarket1",
            collateral_amount=100.0,
            collateral_value_usd=10000.0,
            debt_amount=20.0,
            debt_value_usd=2000.0,
            health_factor=4.3,  # Very healthy
            lltv=0.86,
            timestamp=datetime.now(),
        )
        for i in range(10)
    ]


@pytest.fixture
def risky_positions():
    """Create risky positions (high risk)"""
    return [
        Position(
            borrower=f"0x{i:040x}",
            market_id="0xmarket1",
            collateral_amount=10.0,
            collateral_value_usd=1000.0,
            debt_amount=9.0,
            debt_value_usd=900.0,
            health_factor=1.06,  # Close to liquidation
            lltv=0.86,
            timestamp=datetime.now(),
        )
        for i in range(10)
    ]


@pytest.fixture
def concentrated_positions():
    """Create positions with high concentration (one whale)"""
    positions = [
        # Whale position
        Position(
            borrower="0x1111111111111111111111111111111111111111",
            market_id="0xmarket1",
            collateral_amount=1000.0,
            collateral_value_usd=100000.0,
            debt_amount=500.0,
            debt_value_usd=50000.0,  # 90% of total debt
            health_factor=1.72,
            lltv=0.86,
            timestamp=datetime.now(),
        )
    ]
    # Add small positions
    for i in range(9):
        positions.append(
            Position(
                borrower=f"0x{i+2:040x}",
                market_id="0xmarket1",
                collateral_amount=10.0,
                collateral_value_usd=1000.0,
                debt_amount=5.0,
                debt_value_usd=555.0,  # ~10% of total debt total
                health_factor=1.55,
                lltv=0.86,
                timestamp=datetime.now(),
            )
        )
    return positions


@pytest.fixture
def healthy_snapshot(healthy_positions):
    """Create healthy pool snapshot"""
    total_debt = sum(p.debt_value_usd for p in healthy_positions)
    return PoolSnapshot(
        market_id="0xmarket1",
        pool_name="Healthy Pool",
        timestamp=datetime.now(),
        positions=healthy_positions,
        total_supply=100000.0,
        total_borrow=total_debt,
        utilization=total_debt / 100000.0,
        lltv=0.86,
    )


@pytest.fixture
def risky_snapshot(risky_positions):
    """Create risky pool snapshot"""
    total_debt = sum(p.debt_value_usd for p in risky_positions)
    return PoolSnapshot(
        market_id="0xmarket1",
        pool_name="Risky Pool",
        timestamp=datetime.now(),
        positions=risky_positions,
        total_supply=10000.0,
        total_borrow=total_debt,
        utilization=total_debt / 10000.0,
        lltv=0.86,
    )


@pytest.fixture
def concentrated_snapshot(concentrated_positions):
    """Create concentrated pool snapshot"""
    total_debt = sum(p.debt_value_usd for p in concentrated_positions)
    return PoolSnapshot(
        market_id="0xmarket1",
        pool_name="Concentrated Pool",
        timestamp=datetime.now(),
        positions=concentrated_positions,
        total_supply=100000.0,
        total_borrow=total_debt,
        utilization=total_debt / 100000.0,
        lltv=0.86,
    )


class TestRiskScorerBasic:
    """Test basic RiskScorer functionality"""

    def test_initialization(self, healthy_snapshot):
        """Test RiskScorer can be initialized"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        assert scorer.metrics == metrics
        assert scorer.stress_engine is None
        assert len(scorer.weights) == 4

    def test_initialization_with_stress_engine(self, healthy_snapshot):
        """Test initialization with stress engine"""
        metrics = RiskMetrics(healthy_snapshot)
        stress_engine = StressTestEngine(healthy_snapshot)
        scorer = RiskScorer(metrics, stress_engine)

        assert scorer.stress_engine == stress_engine

    def test_custom_weights(self, healthy_snapshot):
        """Test custom weights"""
        metrics = RiskMetrics(healthy_snapshot)
        custom_weights = {
            "utilization": 0.25,
            "health_factor": 0.25,
            "concentration": 0.25,
            "stress_sensitivity": 0.25,
        }
        scorer = RiskScorer(metrics, weights=custom_weights)

        assert scorer.weights == custom_weights

    def test_invalid_weights(self, healthy_snapshot):
        """Test that invalid weights raise error"""
        metrics = RiskMetrics(healthy_snapshot)
        invalid_weights = {
            "utilization": 0.5,
            "health_factor": 0.3,
            "concentration": 0.3,
            "stress_sensitivity": 0.3,  # Sum = 1.4
        }

        with pytest.raises(ValueError):
            RiskScorer(metrics, weights=invalid_weights)


class TestUtilizationScoring:
    """Test utilization scoring component"""

    def test_low_utilization(self, healthy_snapshot):
        """Test low utilization scores low"""
        # Set low utilization
        healthy_snapshot.utilization = 0.50
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        score = scorer._score_utilization(0.50)
        assert score < 50

    def test_moderate_utilization(self, healthy_snapshot):
        """Test moderate utilization"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        score = scorer._score_utilization(0.80)
        assert 50 <= score < 90

    def test_high_utilization(self, healthy_snapshot):
        """Test high utilization scores high"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        score = scorer._score_utilization(0.95)
        assert score >= 90

    def test_utilization_edge_cases(self, healthy_snapshot):
        """Test edge cases"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        # Zero utilization
        assert scorer._score_utilization(0.0) == 0

        # Full utilization
        score_100 = scorer._score_utilization(1.0)
        assert score_100 >= 90


class TestHealthFactorScoring:
    """Test health factor scoring component"""

    def test_healthy_hf(self, healthy_snapshot):
        """Test healthy HF scores low"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        weighted_hf = 3.0
        buffer_pct = 5.0

        score = scorer._score_health_factor(weighted_hf, buffer_pct)
        assert score < 50

    def test_risky_hf(self, risky_snapshot):
        """Test risky HF scores high"""
        metrics = RiskMetrics(risky_snapshot)
        scorer = RiskScorer(metrics)

        weighted_hf = 1.08
        buffer_pct = 80.0

        score = scorer._score_health_factor(weighted_hf, buffer_pct)
        assert score >= 70

    def test_critical_hf(self, healthy_snapshot):
        """Test critical HF"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        # Very low HF
        score = scorer._score_health_factor(1.05, 90.0)
        assert score >= 90


class TestConcentrationScoring:
    """Test concentration scoring component"""

    def test_low_concentration(self, healthy_snapshot):
        """Test low concentration scores low"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        # Equal distribution
        top_5_pct = 50.0
        herfindahl = 1000.0

        score = scorer._score_concentration(top_5_pct, herfindahl)
        assert score < 60

    def test_high_concentration(self, concentrated_snapshot):
        """Test high concentration scores high"""
        metrics = RiskMetrics(concentrated_snapshot)
        scorer = RiskScorer(metrics)

        concentration = metrics.concentration_metrics()
        top_5_pct = concentration["top_5_pct"]
        herfindahl = metrics.herfindahl_index()

        score = scorer._score_concentration(top_5_pct, herfindahl)
        # Should be high because of whale dominance
        assert score >= 50


class TestStressSensitivityScoring:
    """Test stress sensitivity scoring component"""

    def test_no_stress_engine(self, healthy_snapshot):
        """Test default score when no stress engine"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)  # No stress engine

        score = scorer._score_stress_sensitivity()
        assert score == 50  # Conservative default

    def test_resilient_pool(self, healthy_snapshot):
        """Test resilient pool scores low"""
        metrics = RiskMetrics(healthy_snapshot)
        stress_engine = StressTestEngine(healthy_snapshot)
        scorer = RiskScorer(metrics, stress_engine)

        score = scorer._score_stress_sensitivity()
        # Healthy pool should have low stress sensitivity
        assert score < 70

    def test_sensitive_pool(self, risky_snapshot):
        """Test sensitive pool scores high"""
        metrics = RiskMetrics(risky_snapshot)
        stress_engine = StressTestEngine(risky_snapshot)
        scorer = RiskScorer(metrics, stress_engine)

        score = scorer._score_stress_sensitivity()
        # Risky pool should have high stress sensitivity
        assert score >= 50


class TestCompositeScore:
    """Test composite score calculation"""

    def test_healthy_pool_score(self, healthy_snapshot):
        """Test healthy pool gets low score"""
        metrics = RiskMetrics(healthy_snapshot)
        stress_engine = StressTestEngine(healthy_snapshot)
        scorer = RiskScorer(metrics, stress_engine)

        composite = scorer.calculate_composite_score()
        assert 0 <= composite < 50  # Should be low risk

    def test_risky_pool_score(self, risky_snapshot):
        """Test risky pool gets high score"""
        metrics = RiskMetrics(risky_snapshot)
        stress_engine = StressTestEngine(risky_snapshot)
        scorer = RiskScorer(metrics, stress_engine)

        composite = scorer.calculate_composite_score()
        assert composite >= 50  # Should be higher risk

    def test_score_range(self, healthy_snapshot):
        """Test score is in valid range"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        composite = scorer.calculate_composite_score()
        assert 0 <= composite <= 100

    def test_component_scores(self, healthy_snapshot):
        """Test component scores are returned"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        components = scorer.get_component_scores()

        assert "utilization" in components
        assert "health_factor" in components
        assert "concentration" in components
        assert "stress_sensitivity" in components

        # All scores should be 0-100
        for score in components.values():
            assert 0 <= score <= 100


class TestRiskLevels:
    """Test risk level classification"""

    def test_minimal_risk(self, healthy_snapshot):
        """Test MINIMAL risk level"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        assert scorer.get_risk_level(10) == "MINIMAL"
        assert scorer.get_risk_level(20) == "MINIMAL"

    def test_low_risk(self, healthy_snapshot):
        """Test LOW risk level"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        assert scorer.get_risk_level(30) == "LOW"
        assert scorer.get_risk_level(40) == "LOW"

    def test_moderate_risk(self, healthy_snapshot):
        """Test MODERATE risk level"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        assert scorer.get_risk_level(50) == "MODERATE"
        assert scorer.get_risk_level(60) == "MODERATE"

    def test_high_risk(self, healthy_snapshot):
        """Test HIGH risk level"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        assert scorer.get_risk_level(70) == "HIGH"
        assert scorer.get_risk_level(75) == "HIGH"

    def test_critical_risk(self, healthy_snapshot):
        """Test CRITICAL risk level"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        assert scorer.get_risk_level(85) == "CRITICAL"
        assert scorer.get_risk_level(95) == "CRITICAL"

    def test_get_risk_level_no_score(self, healthy_snapshot):
        """Test get_risk_level calculates composite if no score provided"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        level = scorer.get_risk_level()  # No score provided
        assert level in ["MINIMAL", "LOW", "MODERATE", "HIGH", "CRITICAL"]


class TestRiskColors:
    """Test risk color coding"""

    def test_color_mapping(self, healthy_snapshot):
        """Test all risk levels have colors"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        assert scorer.get_risk_color(10) == "green"
        assert scorer.get_risk_color(30) == "lightgreen"
        assert scorer.get_risk_color(50) == "yellow"
        assert scorer.get_risk_color(70) == "orange"
        assert scorer.get_risk_color(90) == "red"


class TestReportGeneration:
    """Test report generation"""

    def test_generate_report(self, healthy_snapshot):
        """Test report generation"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        report = scorer.generate_report()

        assert isinstance(report, str)
        assert "Risk Score Report" in report
        assert "Composite Risk Score" in report
        assert "Component Scores" in report

    def test_report_includes_pool_name(self, healthy_snapshot):
        """Test report includes pool name"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        report = scorer.generate_report()
        assert "Healthy Pool" in report

    def test_report_includes_all_components(self, healthy_snapshot):
        """Test report includes all components"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        report = scorer.generate_report()

        assert "Utilization" in report
        assert "Health Factor" in report
        assert "Concentration" in report
        assert "Stress Sensitivity" in report

    def test_report_includes_interpretation(self, healthy_snapshot):
        """Test report includes interpretation"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        report = scorer.generate_report()
        assert "Interpretation" in report


class TestEdgeCases:
    """Test edge cases"""

    def test_empty_pool(self):
        """Test with empty pool"""
        empty_snapshot = PoolSnapshot(
            market_id="0xempty",
            pool_name="Empty Pool",
            timestamp=datetime.now(),
            positions=[],
            total_supply=0.0,
            total_borrow=0.0,
            utilization=0.0,
            lltv=0.86,
        )

        metrics = RiskMetrics(empty_snapshot)
        scorer = RiskScorer(metrics)

        # Should not crash
        composite = scorer.calculate_composite_score()
        assert 0 <= composite <= 100

    def test_single_position(self):
        """Test with single position"""
        single_position = [
            Position(
                borrower="0x1111111111111111111111111111111111111111",
                market_id="0xmarket1",
                collateral_amount=10.0,
                collateral_value_usd=1000.0,
                debt_amount=5.0,
                debt_value_usd=500.0,
                health_factor=1.72,
                lltv=0.86,
                timestamp=datetime.now(),
            )
        ]

        snapshot = PoolSnapshot(
            market_id="0xmarket1",
            pool_name="Single Position Pool",
            timestamp=datetime.now(),
            positions=single_position,
            total_supply=1000.0,
            total_borrow=500.0,
            utilization=0.5,
            lltv=0.86,
        )

        metrics = RiskMetrics(snapshot)
        scorer = RiskScorer(metrics)

        composite = scorer.calculate_composite_score()
        # Single position = 100% concentration, should have moderate score
        assert composite >= 30


class TestWeightedScoring:
    """Test that weights are properly applied"""

    def test_weights_sum_to_one(self, healthy_snapshot):
        """Test default weights sum to 1.0"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        weight_sum = sum(scorer.weights.values())
        assert weight_sum == pytest.approx(1.0, abs=0.01)

    def test_component_contribution(self, healthy_snapshot):
        """Test components contribute according to weights"""
        metrics = RiskMetrics(healthy_snapshot)
        scorer = RiskScorer(metrics)

        component_scores = scorer.get_component_scores()
        composite = scorer.calculate_composite_score()

        # Calculate expected composite
        expected = sum(
            component_scores[k] * scorer.weights[k] for k in component_scores
        )

        assert composite == pytest.approx(expected, abs=0.1)
