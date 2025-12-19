"""
Tests for Risk Metrics Engine
"""

import pytest
from datetime import datetime
from src.state.models import Position, PoolSnapshot
from src.metrics.core import RiskMetrics


@pytest.fixture
def sample_positions():
    """Create sample positions for testing"""
    return [
        Position(
            borrower="0x1111111111111111111111111111111111111111",
            market_id="0xmarket1",
            collateral_amount=100.0,
            collateral_value_usd=10000.0,
            debt_amount=50.0,
            debt_value_usd=5000.0,
            health_factor=1.72,  # (10000 * 0.86) / 5000 = 1.72
            lltv=0.86,
            timestamp=datetime.now()
        ),
        Position(
            borrower="0x2222222222222222222222222222222222222222",
            market_id="0xmarket1",
            collateral_amount=50.0,
            collateral_value_usd=5000.0,
            debt_amount=40.0,
            debt_value_usd=4000.0,
            health_factor=1.075,  # Critical
            lltv=0.86,
            timestamp=datetime.now()
        ),
        Position(
            borrower="0x3333333333333333333333333333333333333333",
            market_id="0xmarket1",
            collateral_amount=30.0,
            collateral_value_usd=3000.0,
            debt_amount=20.0,
            debt_value_usd=2000.0,
            health_factor=1.29,
            lltv=0.86,
            timestamp=datetime.now()
        ),
        Position(
            borrower="0x4444444444444444444444444444444444444444",
            market_id="0xmarket1",
            collateral_amount=20.0,
            collateral_value_usd=2000.0,
            debt_amount=10.0,
            debt_value_usd=1000.0,
            health_factor=1.72,
            lltv=0.86,
            timestamp=datetime.now()
        ),
        Position(
            borrower="0x5555555555555555555555555555555555555555",
            market_id="0xmarket1",
            collateral_amount=500.0,
            collateral_value_usd=50000.0,
            debt_amount=400.0,
            debt_value_usd=40000.0,
            health_factor=1.075,  # Whale at risk
            lltv=0.86,
            timestamp=datetime.now()
        ),
    ]


@pytest.fixture
def sample_snapshot(sample_positions):
    """Create a sample pool snapshot"""
    return PoolSnapshot(
        market_id="0xmarket1",
        pool_name="Test Pool",
        timestamp=datetime.now(),
        positions=sample_positions,
        total_supply=100000.0,
        total_borrow=52000.0,  # Sum of all debt
        utilization=0.52,
        lltv=0.86
    )


class TestRiskMetricsBasic:
    """Test basic RiskMetrics initialization and simple methods"""

    def test_initialization(self, sample_snapshot):
        """Test RiskMetrics can be initialized"""
        metrics = RiskMetrics(sample_snapshot)
        assert metrics.snapshot == sample_snapshot
        assert metrics.positions == sample_snapshot.positions

    def test_utilization_rate(self, sample_snapshot):
        """Test utilization rate calculation"""
        metrics = RiskMetrics(sample_snapshot)
        assert metrics.utilization_rate() == 0.52

    def test_empty_snapshot(self):
        """Test metrics with empty snapshot"""
        empty_snapshot = PoolSnapshot(
            market_id="0xempty",
            pool_name="Empty Pool",
            timestamp=datetime.now(),
            positions=[],
            total_supply=0.0,
            total_borrow=0.0,
            utilization=0.0,
            lltv=0.86
        )
        metrics = RiskMetrics(empty_snapshot)

        assert metrics.concentration_metrics()['top_5_pct'] == 0
        assert metrics.gini_coefficient() == 0.0
        assert metrics.herfindahl_index() == 0.0
        assert metrics.weighted_avg_health_factor() == float('inf')
        assert metrics.liquidation_buffer_percentage() == 0.0


class TestConcentrationMetrics:
    """Test concentration risk metrics"""

    def test_concentration_metrics(self, sample_snapshot):
        """Test top N concentration calculation"""
        metrics = RiskMetrics(sample_snapshot)
        concentration = metrics.concentration_metrics()

        # Total debt = 52000
        # Top 1: 40000 (76.9%)
        # Top 5: 52000 (100%)
        assert concentration['top_5_debt_usd'] == 52000.0
        assert concentration['top_10_debt_usd'] == 52000.0
        assert concentration['top_5_pct'] == pytest.approx(100.0, rel=0.01)
        assert concentration['top_10_pct'] == pytest.approx(100.0, rel=0.01)

    def test_top_5_concentration(self, sample_snapshot):
        """Test that top 5 is correctly calculated"""
        metrics = RiskMetrics(sample_snapshot)
        concentration = metrics.concentration_metrics()

        # Sorted by debt: 40000, 5000, 4000, 2000, 1000
        # Top 5 should be all positions (only 5 positions)
        assert 'top_5_pct' in concentration
        assert 'top_5_debt_usd' in concentration

    def test_gini_coefficient(self, sample_snapshot):
        """Test Gini coefficient calculation"""
        metrics = RiskMetrics(sample_snapshot)
        gini = metrics.gini_coefficient()

        # Gini should be between 0 and 1
        assert 0 <= gini <= 1
        # With unequal distribution, should be > 0
        assert gini > 0

    def test_gini_equal_distribution(self):
        """Test Gini with perfectly equal distribution"""
        equal_positions = [
            Position(
                borrower=f"0x{i:040x}",
                market_id="0xmarket1",
                collateral_amount=10.0,
                collateral_value_usd=1000.0,
                debt_amount=5.0,
                debt_value_usd=500.0,
                health_factor=1.72,
                lltv=0.86,
                timestamp=datetime.now()
            )
            for i in range(10)
        ]

        snapshot = PoolSnapshot(
            market_id="0xmarket1",
            pool_name="Equal Pool",
            timestamp=datetime.now(),
            positions=equal_positions,
            total_supply=10000.0,
            total_borrow=5000.0,
            utilization=0.5,
            lltv=0.86
        )

        metrics = RiskMetrics(snapshot)
        gini = metrics.gini_coefficient()

        # Equal distribution should have very low Gini (close to 0)
        assert gini < 0.1

    def test_herfindahl_index(self, sample_snapshot):
        """Test Herfindahl-Hirschman Index"""
        metrics = RiskMetrics(sample_snapshot)
        hhi = metrics.herfindahl_index()

        # HHI should be between 0 and 10000
        assert 0 <= hhi <= 10000
        # With concentrated positions, HHI should be high
        assert hhi > 1000

    def test_herfindahl_monopoly(self):
        """Test HHI with complete concentration (monopoly)"""
        monopoly_positions = [
            Position(
                borrower="0x1111111111111111111111111111111111111111",
                market_id="0xmarket1",
                collateral_amount=100.0,
                collateral_value_usd=10000.0,
                debt_amount=50.0,
                debt_value_usd=10000.0,
                health_factor=0.86,
                lltv=0.86,
                timestamp=datetime.now()
            )
        ]

        snapshot = PoolSnapshot(
            market_id="0xmarket1",
            pool_name="Monopoly Pool",
            timestamp=datetime.now(),
            positions=monopoly_positions,
            total_supply=10000.0,
            total_borrow=10000.0,
            utilization=1.0,
            lltv=0.86
        )

        metrics = RiskMetrics(snapshot)
        hhi = metrics.herfindahl_index()

        # Complete monopoly should have HHI = 10000
        assert hhi == pytest.approx(10000.0, rel=0.01)


class TestHealthFactorAnalysis:
    """Test health factor analysis methods"""

    def test_weighted_avg_health_factor(self, sample_snapshot):
        """Test weighted average health factor"""
        metrics = RiskMetrics(sample_snapshot)
        weighted_hf = metrics.weighted_avg_health_factor()

        # Should be finite
        assert weighted_hf != float('inf')
        # Should be positive
        assert weighted_hf > 0

        # Calculate manually
        # (5000*1.72 + 4000*1.075 + 2000*1.29 + 1000*1.72 + 40000*1.075) / 52000
        expected = (5000*1.72 + 4000*1.075 + 2000*1.29 + 1000*1.72 + 40000*1.075) / 52000
        assert weighted_hf == pytest.approx(expected, rel=0.01)

    def test_health_factor_distribution(self, sample_snapshot):
        """Test health factor distribution buckets"""
        metrics = RiskMetrics(sample_snapshot)
        hf_dist = metrics.health_factor_distribution()

        # Check all buckets exist
        assert 'hf_below_1.05' in hf_dist
        assert 'hf_1.05_to_1.1' in hf_dist
        assert 'hf_1.1_to_1.2' in hf_dist
        assert 'hf_1.2_to_1.5' in hf_dist
        assert 'hf_above_1.5' in hf_dist

        # All percentages should sum to ~100%
        total_pct = sum(hf_dist.values())
        assert total_pct == pytest.approx(100.0, rel=0.01)

        # We have 2 positions with HF = 1.075 (in 1.05-1.1 bucket)
        # Debt: 4000 + 40000 = 44000 out of 52000 = 84.6%
        assert hf_dist['hf_1.05_to_1.1'] == pytest.approx(84.6, rel=0.1)

    def test_liquidation_buffer_percentage(self, sample_snapshot):
        """Test liquidation buffer calculation"""
        metrics = RiskMetrics(sample_snapshot)

        # Threshold 1.1: positions with HF < 1.1
        # HF 1.075: 4000 + 40000 = 44000 debt
        buffer_1_1 = metrics.liquidation_buffer_percentage(1.1)
        assert buffer_1_1 == pytest.approx(84.6, rel=0.1)

        # Threshold 1.5: positions with HF < 1.5
        # HF 1.075, 1.29: 44000 + 2000 = 46000 debt
        buffer_1_5 = metrics.liquidation_buffer_percentage(1.5)
        assert buffer_1_5 == pytest.approx(88.5, rel=0.1)

    def test_positions_at_risk(self, sample_snapshot):
        """Test positions at risk identification"""
        metrics = RiskMetrics(sample_snapshot)

        # Threshold 1.1
        at_risk = metrics.positions_at_risk(1.1)
        assert len(at_risk) == 2  # 2 positions with HF = 1.075

        # Should be sorted by health factor
        assert at_risk[0].health_factor <= at_risk[1].health_factor

        # All should be below threshold
        for pos in at_risk:
            assert pos.health_factor < 1.1

    def test_positions_at_risk_high_threshold(self, sample_snapshot):
        """Test positions at risk with high threshold"""
        metrics = RiskMetrics(sample_snapshot)

        # Very high threshold should catch all positions
        at_risk = metrics.positions_at_risk(10.0)
        assert len(at_risk) == 5  # All positions


class TestPositionDistribution:
    """Test position size distribution"""

    def test_position_size_distribution(self, sample_snapshot):
        """Test position size bucketing"""
        metrics = RiskMetrics(sample_snapshot)
        size_dist = metrics.position_size_distribution()

        # Check all buckets exist
        assert 'micro_below_10k' in size_dist
        assert 'small_10k_to_100k' in size_dist
        assert 'medium_100k_to_1m' in size_dist
        assert 'large_1m_to_10m' in size_dist
        assert 'whale_above_10m' in size_dist

        # Total should equal number of positions
        total_positions = sum(size_dist.values())
        assert total_positions == 5

        # Our sample has:
        # - 1 micro: 1000
        # - 3 small: 2000, 4000, 5000
        # - 1 whale: 40000
        assert size_dist['micro_below_10k'] == 1
        assert size_dist['small_10k_to_100k'] == 3
        assert size_dist['whale_above_10m'] == 1

    def test_position_size_distribution_diverse(self):
        """Test position size distribution with diverse sizes"""
        positions = [
            # Micro
            Position("0x1", "0xm", 1, 500, 1, 500, 0.86, 0.86, datetime.now()),
            # Small
            Position("0x2", "0xm", 10, 50000, 5, 25000, 1.72, 0.86, datetime.now()),
            # Medium
            Position("0x3", "0xm", 100, 500000, 50, 250000, 1.72, 0.86, datetime.now()),
            # Large
            Position("0x4", "0xm", 1000, 5000000, 500, 2500000, 1.72, 0.86, datetime.now()),
            # Whale
            Position("0x5", "0xm", 10000, 50000000, 5000, 25000000, 1.72, 0.86, datetime.now()),
        ]

        snapshot = PoolSnapshot(
            market_id="0xm",
            pool_name="Diverse Pool",
            timestamp=datetime.now(),
            positions=positions,
            total_supply=55750000.0,
            total_borrow=27775000.0,
            utilization=0.5,
            lltv=0.86
        )

        metrics = RiskMetrics(snapshot)
        size_dist = metrics.position_size_distribution()

        assert size_dist['micro_below_10k'] == 1
        assert size_dist['small_10k_to_100k'] == 1
        assert size_dist['medium_100k_to_1m'] == 1
        assert size_dist['large_1m_to_10m'] == 1
        assert size_dist['whale_above_10m'] == 1


class TestSummaryMethods:
    """Test summary and report generation methods"""

    def test_compute_all_metrics(self, sample_snapshot):
        """Test compute_all_metrics returns all expected keys"""
        metrics = RiskMetrics(sample_snapshot)
        all_metrics = metrics.compute_all_metrics()

        # Pool-level metrics
        assert 'utilization_rate' in all_metrics
        assert 'total_positions' in all_metrics
        assert 'total_debt_usd' in all_metrics
        assert 'total_collateral_usd' in all_metrics

        # Concentration metrics
        assert 'top_5_concentration_pct' in all_metrics
        assert 'top_10_concentration_pct' in all_metrics
        assert 'gini_coefficient' in all_metrics
        assert 'herfindahl_index' in all_metrics

        # Health factor metrics
        assert 'weighted_avg_health_factor' in all_metrics
        assert 'debt_below_hf_1_05_pct' in all_metrics
        assert 'debt_below_hf_1_1_pct' in all_metrics
        assert 'liquidation_buffer_10pct' in all_metrics
        assert 'positions_at_risk_count' in all_metrics

        # Position size distribution
        assert 'micro_positions' in all_metrics
        assert 'small_positions' in all_metrics
        assert 'medium_positions' in all_metrics
        assert 'large_positions' in all_metrics
        assert 'whale_positions' in all_metrics

    def test_compute_all_metrics_values(self, sample_snapshot):
        """Test compute_all_metrics returns correct values"""
        metrics = RiskMetrics(sample_snapshot)
        all_metrics = metrics.compute_all_metrics()

        assert all_metrics['total_positions'] == 5
        assert all_metrics['utilization_rate'] == 0.52
        assert all_metrics['total_debt_usd'] == 52000.0
        assert all_metrics['positions_at_risk_count'] == 2

    def test_summary_report(self, sample_snapshot):
        """Test summary report generation"""
        metrics = RiskMetrics(sample_snapshot)
        report = metrics.summary_report()

        # Check report is a string
        assert isinstance(report, str)

        # Check report contains key sections
        assert "Risk Metrics Summary" in report
        assert "Pool Overview" in report
        assert "Concentration Risk" in report
        assert "Health Factor Analysis" in report
        assert "Position Distribution" in report

        # Check report contains pool name
        assert "Test Pool" in report

        # Check report contains some metrics
        assert "Total Positions: 5" in report
        assert "Utilization Rate:" in report

    def test_summary_report_formatting(self, sample_snapshot):
        """Test summary report is properly formatted"""
        metrics = RiskMetrics(sample_snapshot)
        report = metrics.summary_report()

        # Should have multiple lines
        lines = report.split('\n')
        assert len(lines) > 10

        # Should have proper separators
        assert any('===' in line for line in lines)
        assert any('---' in line for line in lines)


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_single_position(self):
        """Test with single position"""
        positions = [
            Position(
                borrower="0x1111111111111111111111111111111111111111",
                market_id="0xmarket1",
                collateral_amount=100.0,
                collateral_value_usd=10000.0,
                debt_amount=50.0,
                debt_value_usd=5000.0,
                health_factor=1.72,
                lltv=0.86,
                timestamp=datetime.now()
            )
        ]

        snapshot = PoolSnapshot(
            market_id="0xmarket1",
            pool_name="Single Position Pool",
            timestamp=datetime.now(),
            positions=positions,
            total_supply=10000.0,
            total_borrow=5000.0,
            utilization=0.5,
            lltv=0.86
        )

        metrics = RiskMetrics(snapshot)

        # Concentration should be 100%
        concentration = metrics.concentration_metrics()
        assert concentration['top_5_pct'] == 100.0

        # Gini should be 0 (perfect equality with one borrower)
        assert metrics.gini_coefficient() == 0.0

        # HHI should be 10000 (complete concentration)
        assert metrics.herfindahl_index() == pytest.approx(10000.0, rel=0.01)

    def test_zero_debt_positions(self):
        """Test with positions that have zero debt"""
        positions = [
            Position(
                borrower=f"0x{i:040x}",
                market_id="0xmarket1",
                collateral_amount=10.0,
                collateral_value_usd=1000.0,
                debt_amount=0.0,
                debt_value_usd=0.0,
                health_factor=float('inf'),
                lltv=0.86,
                timestamp=datetime.now()
            )
            for i in range(5)
        ]

        snapshot = PoolSnapshot(
            market_id="0xmarket1",
            pool_name="Zero Debt Pool",
            timestamp=datetime.now(),
            positions=positions,
            total_supply=5000.0,
            total_borrow=0.0,
            utilization=0.0,
            lltv=0.86
        )

        metrics = RiskMetrics(snapshot)

        # Should handle gracefully
        assert metrics.weighted_avg_health_factor() == float('inf')
        assert metrics.liquidation_buffer_percentage() == 0.0
        assert len(metrics.positions_at_risk()) == 0

    def test_all_positions_at_risk(self):
        """Test when all positions are at risk"""
        positions = [
            Position(
                borrower=f"0x{i:040x}",
                market_id="0xmarket1",
                collateral_amount=10.0,
                collateral_value_usd=1000.0,
                debt_amount=9.5,
                debt_value_usd=950.0,
                health_factor=1.05,  # Just above liquidation
                lltv=0.86,
                timestamp=datetime.now()
            )
            for i in range(5)
        ]

        snapshot = PoolSnapshot(
            market_id="0xmarket1",
            pool_name="Risky Pool",
            timestamp=datetime.now(),
            positions=positions,
            total_supply=5000.0,
            total_borrow=4750.0,
            utilization=0.95,
            lltv=0.86
        )

        metrics = RiskMetrics(snapshot)

        # All positions should be at risk with threshold 1.1
        at_risk = metrics.positions_at_risk(1.1)
        assert len(at_risk) == 5

        # Liquidation buffer should be 100%
        buffer = metrics.liquidation_buffer_percentage(1.1)
        assert buffer == pytest.approx(100.0, rel=0.01)
