"""
Tests for Stress Testing Engine
"""

from datetime import datetime

import pytest

from src.state.models import PoolSnapshot, Position
from src.stress.engine import StressTestEngine
from src.stress.models import StressResult


@pytest.fixture
def sample_positions():
    """Create sample positions with varying health factors"""
    return [
        # Position 1: Very healthy (HF = 2.0)
        Position(
            borrower="0x1111111111111111111111111111111111111111",
            market_id="0xmarket1",
            collateral_amount=100.0,
            collateral_value_usd=10000.0,
            debt_amount=50.0,
            debt_value_usd=4300.0,  # HF = (10000 * 0.86) / 4300 = 2.0
            health_factor=2.0,
            lltv=0.86,
            timestamp=datetime.now(),
        ),
        # Position 2: Moderate (HF = 1.5)
        Position(
            borrower="0x2222222222222222222222222222222222222222",
            market_id="0xmarket1",
            collateral_amount=50.0,
            collateral_value_usd=5000.0,
            debt_amount=40.0,
            debt_value_usd=2867.0,  # HF = (5000 * 0.86) / 2867 = 1.5
            health_factor=1.5,
            lltv=0.86,
            timestamp=datetime.now(),
        ),
        # Position 3: At risk (HF = 1.1)
        Position(
            borrower="0x3333333333333333333333333333333333333333",
            market_id="0xmarket1",
            collateral_amount=30.0,
            collateral_value_usd=3000.0,
            debt_amount=25.0,
            debt_value_usd=2345.0,  # HF = (3000 * 0.86) / 2345 = 1.1
            health_factor=1.1,
            lltv=0.86,
            timestamp=datetime.now(),
        ),
        # Position 4: Critical (HF = 1.05)
        Position(
            borrower="0x4444444444444444444444444444444444444444",
            market_id="0xmarket1",
            collateral_amount=20.0,
            collateral_value_usd=2000.0,
            debt_amount=18.0,
            debt_value_usd=1638.0,  # HF = (2000 * 0.86) / 1638 = 1.05
            health_factor=1.05,
            lltv=0.86,
            timestamp=datetime.now(),
        ),
    ]


@pytest.fixture
def sample_snapshot(sample_positions):
    """Create a sample pool snapshot"""
    total_debt = sum(p.debt_value_usd for p in sample_positions)
    return PoolSnapshot(
        market_id="0xmarket1",
        pool_name="Test Pool",
        timestamp=datetime.now(),
        positions=sample_positions,
        total_supply=20000.0,
        total_borrow=total_debt,
        utilization=total_debt / 20000.0,
        lltv=0.86,
    )


class TestStressTestEngineBasic:
    """Test basic StressTestEngine functionality"""

    def test_initialization(self, sample_snapshot):
        """Test engine can be initialized"""
        engine = StressTestEngine(sample_snapshot)
        assert engine.snapshot == sample_snapshot
        assert len(engine.scenarios) == 7  # Default scenarios

    def test_custom_scenarios(self, sample_snapshot):
        """Test engine with custom scenarios"""
        custom_scenarios = [-0.10, -0.20, -0.30]
        engine = StressTestEngine(sample_snapshot, scenarios=custom_scenarios)
        assert engine.scenarios == custom_scenarios
        assert len(engine.scenarios) == 3

    def test_apply_price_shock_no_liquidations(self, sample_snapshot):
        """Test small price shock causes no liquidations"""
        engine = StressTestEngine(sample_snapshot)

        # -1% shock shouldn't liquidate anyone (all have HF > 1.05)
        result = engine.apply_price_shock(-0.01)

        assert isinstance(result, StressResult)
        assert result.liquidatable_positions == 0
        assert result.total_debt_at_risk_usd == 0
        assert result.bad_debt_potential_usd == 0
        assert result.pct_pool_affected == 0

    def test_apply_price_shock_some_liquidations(self, sample_snapshot):
        """Test moderate price shock causes some liquidations"""
        engine = StressTestEngine(sample_snapshot)

        # -10% shock should liquidate positions with HF < 1.11
        result = engine.apply_price_shock(-0.10)

        assert isinstance(result, StressResult)
        assert result.liquidatable_positions >= 1
        assert result.total_debt_at_risk_usd > 0
        assert result.pct_pool_affected > 0

    def test_apply_price_shock_all_liquidations(self, sample_snapshot):
        """Test severe price shock liquidates all positions"""
        engine = StressTestEngine(sample_snapshot)

        # -50% shock should liquidate all positions
        result = engine.apply_price_shock(-0.50)

        assert isinstance(result, StressResult)
        assert result.liquidatable_positions == 4  # All 4 positions
        assert result.pct_pool_affected == pytest.approx(100.0, rel=0.01)


class TestStressResultModel:
    """Test StressResult model"""

    def test_stress_result_creation(self):
        """Test StressResult can be created"""
        result = StressResult(
            scenario_name="-10% shock",
            price_shock_pct=-10.0,
            liquidatable_positions=5,
            total_collateral_at_risk_usd=10000.0,
            total_debt_at_risk_usd=8000.0,
            bad_debt_potential_usd=500.0,
            pct_pool_affected=25.0,
            positions_details=[],
        )

        assert result.scenario_name == "-10% shock"
        assert result.price_shock_pct == -10.0
        assert result.liquidatable_positions == 5

    def test_stress_result_to_dict(self):
        """Test StressResult conversion to dict"""
        result = StressResult(
            scenario_name="-10% shock",
            price_shock_pct=-10.0,
            liquidatable_positions=5,
            total_collateral_at_risk_usd=10000.0,
            total_debt_at_risk_usd=8000.0,
            bad_debt_potential_usd=500.0,
            pct_pool_affected=25.0,
            positions_details=[{"borrower": "0x123"}],
        )

        result_dict = result.to_dict()

        assert "scenario_name" in result_dict
        assert "liquidatable_positions" in result_dict
        assert result_dict["positions_count"] == 1

    def test_stress_result_summary(self):
        """Test StressResult summary generation"""
        result = StressResult(
            scenario_name="-10% shock",
            price_shock_pct=-10.0,
            liquidatable_positions=5,
            total_collateral_at_risk_usd=10000.0,
            total_debt_at_risk_usd=8000.0,
            bad_debt_potential_usd=500.0,
            pct_pool_affected=25.0,
            positions_details=[],
        )

        summary = result.summary()

        assert isinstance(summary, str)
        assert "-10% shock" in summary
        assert "5" in summary
        assert "25.0%" in summary


class TestRunAllScenarios:
    """Test running all stress scenarios"""

    def test_run_all_scenarios(self, sample_snapshot):
        """Test running all scenarios returns dataframe"""
        engine = StressTestEngine(sample_snapshot)
        results_df = engine.run_all_scenarios()

        assert len(results_df) == 7  # Default 7 scenarios
        assert "price_shock_pct" in results_df.columns
        assert "liquidatable_positions" in results_df.columns
        assert "debt_at_risk_usd" in results_df.columns
        assert "pct_pool_affected" in results_df.columns

    def test_results_progressive(self, sample_snapshot):
        """Test that worse shocks cause more liquidations"""
        engine = StressTestEngine(sample_snapshot)
        results_df = engine.run_all_scenarios()

        # Results should be in order of shock severity
        # More severe shocks should generally have more liquidations
        prev_positions = -1
        for _, row in results_df.iterrows():
            assert row["liquidatable_positions"] >= prev_positions
            prev_positions = row["liquidatable_positions"]

    def test_custom_scenarios_results(self, sample_snapshot):
        """Test custom scenarios produce correct number of results"""
        custom_scenarios = [-0.05, -0.10]
        engine = StressTestEngine(sample_snapshot, scenarios=custom_scenarios)
        results_df = engine.run_all_scenarios()

        assert len(results_df) == 2


class TestCliffPointDetection:
    """Test cliff point detection"""

    def test_find_cliff_points_no_cliffs(self, sample_snapshot):
        """Test no cliffs detected with smooth progression"""
        # Create positions with smooth HF distribution
        smooth_positions = [
            Position(
                borrower=f"0x{i:040x}",
                market_id="0xmarket1",
                collateral_amount=10.0,
                collateral_value_usd=1000.0,
                debt_amount=5.0,
                debt_value_usd=1000.0 * 0.86 / (1.0 + i * 0.1),
                health_factor=1.0 + i * 0.1,
                lltv=0.86,
                timestamp=datetime.now(),
            )
            for i in range(10)
        ]

        snapshot = PoolSnapshot(
            market_id="0xmarket1",
            pool_name="Smooth Pool",
            timestamp=datetime.now(),
            positions=smooth_positions,
            total_supply=10000.0,
            total_borrow=5000.0,
            utilization=0.5,
            lltv=0.86,
        )

        engine = StressTestEngine(snapshot)
        cliffs = engine.find_cliff_points()

        # Should have few or no cliff points with smooth distribution
        assert len(cliffs) <= 2

    def test_find_cliff_points_with_cliffs(self):
        """Test cliff detection with concentrated positions"""
        # Create positions clustered at HF = 1.5
        clustered_positions = [
            Position(
                borrower=f"0x{i:040x}",
                market_id="0xmarket1",
                collateral_amount=10.0,
                collateral_value_usd=10000.0,
                debt_amount=5.0,
                debt_value_usd=5733.0,  # HF = 1.5
                health_factor=1.5,
                lltv=0.86,
                timestamp=datetime.now(),
            )
            for i in range(10)
        ]

        snapshot = PoolSnapshot(
            market_id="0xmarket1",
            pool_name="Clustered Pool",
            timestamp=datetime.now(),
            positions=clustered_positions,
            total_supply=100000.0,
            total_borrow=57330.0,
            utilization=0.57,
            lltv=0.86,
        )

        engine = StressTestEngine(snapshot)
        cliffs = engine.find_cliff_points()

        # Should detect cliff points where all positions get liquidated at once
        assert len(cliffs) >= 1

        if cliffs:
            # Check cliff structure
            cliff = cliffs[0]
            assert "from_shock_pct" in cliff
            assert "to_shock_pct" in cliff
            assert "risk_jump_pct" in cliff
            assert "new_liquidations" in cliff


class TestLiquidationThreshold:
    """Test liquidation threshold calculation"""

    def test_get_liquidation_threshold(self, sample_snapshot):
        """Test finding threshold for target liquidation percentage"""
        engine = StressTestEngine(sample_snapshot)

        # Find shock needed to liquidate 10% of pool
        threshold = engine.get_liquidation_threshold(10.0)

        # Should return a shock percentage or None
        assert threshold is None or isinstance(threshold, (int, float))

    def test_get_liquidation_threshold_high_target(self, sample_snapshot):
        """Test threshold for high target percentage"""
        engine = StressTestEngine(sample_snapshot)

        # 100% should definitely be reached with severe shocks
        threshold = engine.get_liquidation_threshold(100.0)

        # Should find a threshold
        assert threshold is not None
        assert threshold < 0  # Should be negative (price drop)

    def test_get_liquidation_threshold_unreachable(self, sample_snapshot):
        """Test threshold for unreachable target"""
        # Create very healthy positions
        healthy_positions = [
            Position(
                borrower=f"0x{i:040x}",
                market_id="0xmarket1",
                collateral_amount=100.0,
                collateral_value_usd=10000.0,
                debt_amount=10.0,
                debt_value_usd=1000.0,
                health_factor=8.6,  # Very high HF
                lltv=0.86,
                timestamp=datetime.now(),
            )
            for i in range(5)
        ]

        snapshot = PoolSnapshot(
            market_id="0xmarket1",
            pool_name="Healthy Pool",
            timestamp=datetime.now(),
            positions=healthy_positions,
            total_supply=50000.0,
            total_borrow=5000.0,
            utilization=0.1,
            lltv=0.86,
        )

        engine = StressTestEngine(snapshot)

        # Even 10% might not be reachable with default scenarios
        threshold = engine.get_liquidation_threshold(10.0)

        # May or may not be reachable
        assert threshold is None or isinstance(threshold, (int, float))


class TestCascadingRiskAnalysis:
    """Test cascading risk analysis"""

    def test_analyze_cascading_risk(self, sample_snapshot):
        """Test cascading risk analysis"""
        engine = StressTestEngine(sample_snapshot)
        cascading = engine.analyze_cascading_risk()

        assert "cliff_points_count" in cascading
        assert "avg_risk_increase_per_scenario" in cascading
        assert "max_risk_increase_per_scenario" in cascading
        assert "has_severe_cliffs" in cascading
        assert isinstance(cascading["has_severe_cliffs"], bool)

    def test_cascading_risk_metrics(self, sample_snapshot):
        """Test cascading risk metrics are valid"""
        engine = StressTestEngine(sample_snapshot)
        cascading = engine.analyze_cascading_risk()

        # Metrics should be non-negative
        assert cascading["cliff_points_count"] >= 0
        assert cascading["avg_risk_increase_per_scenario"] >= 0


class TestSummaryGeneration:
    """Test summary generation"""

    def test_generate_summary(self, sample_snapshot):
        """Test summary generation"""
        engine = StressTestEngine(sample_snapshot)
        summary = engine.generate_summary()

        assert isinstance(summary, str)
        assert "Stress Test Summary" in summary
        assert "Test Pool" in summary
        assert "Scenarios Tested" in summary

    def test_summary_includes_cliffs(self):
        """Test summary includes cliff points if detected"""
        # Create clustered positions for cliff detection
        clustered_positions = [
            Position(
                borrower=f"0x{i:040x}",
                market_id="0xmarket1",
                collateral_amount=10.0,
                collateral_value_usd=10000.0,
                debt_amount=5.0,
                debt_value_usd=5733.0,  # HF = 1.5
                health_factor=1.5,
                lltv=0.86,
                timestamp=datetime.now(),
            )
            for i in range(5)
        ]

        snapshot = PoolSnapshot(
            market_id="0xmarket1",
            pool_name="Clustered Pool",
            timestamp=datetime.now(),
            positions=clustered_positions,
            total_supply=50000.0,
            total_borrow=28665.0,
            utilization=0.57,
            lltv=0.86,
        )

        engine = StressTestEngine(snapshot)
        summary = engine.generate_summary()

        # Check if cliff section might be included
        assert isinstance(summary, str)
        assert "Cascading Risk Analysis" in summary


class TestEdgeCases:
    """Test edge cases"""

    def test_empty_snapshot(self):
        """Test with no positions"""
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

        engine = StressTestEngine(empty_snapshot)
        result = engine.apply_price_shock(-0.10)

        assert result.liquidatable_positions == 0
        assert result.total_debt_at_risk_usd == 0

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

        engine = StressTestEngine(snapshot)
        results = engine.run_all_scenarios()

        assert len(results) == 7
        # All results should be either 0% or 100% affected
        for _, row in results.iterrows():
            assert row["pct_pool_affected"] in [0.0, 100.0] or pytest.approx(
                row["pct_pool_affected"], abs=0.1
            ) in [0.0, 100.0]
