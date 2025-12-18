"""Tests for Position and PoolSnapshot models"""

import pytest
from datetime import datetime
from src.state.models import Position, PoolSnapshot


class TestPosition:
    """Test suite for Position model"""

    @pytest.fixture
    def sample_position(self):
        """Create a sample position for testing"""
        return Position(
            borrower="0x1234567890123456789012345678901234567890",
            market_id="0xabc",
            collateral_amount=10.0,
            collateral_value_usd=20000.0,
            debt_amount=15000.0,
            debt_value_usd=15000.0,
            health_factor=1.15,  # (20000 * 0.86) / 15000
            lltv=0.86,
            timestamp=datetime(2024, 1, 1)
        )

    def test_position_creation(self, sample_position):
        """Test basic position creation"""
        assert sample_position.borrower == "0x1234567890123456789012345678901234567890"
        assert sample_position.market_id == "0xabc"
        assert sample_position.collateral_amount == 10.0
        assert sample_position.debt_value_usd == 15000.0
        assert sample_position.health_factor == 1.15

    def test_liquidation_price(self, sample_position):
        """Test liquidation price calculation"""
        # At liquidation: HF = 1.0
        # (collateral_value * LLTV) / debt_value = 1.0
        # collateral_value = debt_value / LLTV
        # liquidation_price = debt_value / (LLTV * collateral_amount)
        expected = 15000.0 / (0.86 * 10.0)

        assert abs(sample_position.liquidation_price - expected) < 0.01

    def test_liquidation_price_zero_collateral(self):
        """Test liquidation price with zero collateral"""
        position = Position(
            borrower="0x123",
            market_id="0xabc",
            collateral_amount=0.0,
            collateral_value_usd=0.0,
            debt_amount=1000.0,
            debt_value_usd=1000.0,
            health_factor=0.0,
            lltv=0.86,
            timestamp=datetime.now()
        )

        assert position.liquidation_price == 0.0

    def test_is_healthy_true(self, sample_position):
        """Test is_healthy property for healthy position"""
        assert sample_position.is_healthy is True

    def test_is_healthy_false(self):
        """Test is_healthy property for unhealthy position"""
        position = Position(
            borrower="0x123",
            market_id="0xabc",
            collateral_amount=1.0,
            collateral_value_usd=1000.0,
            debt_amount=1200.0,
            debt_value_usd=1200.0,
            health_factor=0.72,  # (1000 * 0.86) / 1200
            lltv=0.86,
            timestamp=datetime.now()
        )

        assert position.is_healthy is False

    def test_liquidation_buffer(self, sample_position):
        """Test liquidation buffer calculation"""
        # HF = 1.15, so buffer = 0.15 (15%)
        assert abs(sample_position.liquidation_buffer - 0.15) < 0.01

    def test_liquidation_buffer_infinite(self):
        """Test liquidation buffer with infinite HF"""
        position = Position(
            borrower="0x123",
            market_id="0xabc",
            collateral_amount=10.0,
            collateral_value_usd=20000.0,
            debt_amount=0.0,
            debt_value_usd=0.0,
            health_factor=float('inf'),
            lltv=0.86,
            timestamp=datetime.now()
        )

        assert position.liquidation_buffer == float('inf')

    def test_health_factor_after_shock_negative(self, sample_position):
        """Test health factor calculation after negative price shock"""
        # -10% shock
        new_hf = sample_position.health_factor_after_shock(-0.10)

        # New collateral value = 20000 * 0.90 = 18000
        # New HF = (18000 * 0.86) / 15000 = 1.032
        expected = (20000.0 * 0.90 * 0.86) / 15000.0

        assert abs(new_hf - expected) < 0.01

    def test_health_factor_after_shock_positive(self, sample_position):
        """Test health factor calculation after positive price shock"""
        # +20% shock
        new_hf = sample_position.health_factor_after_shock(0.20)

        # New collateral value = 20000 * 1.20 = 24000
        # New HF = (24000 * 0.86) / 15000
        expected = (20000.0 * 1.20 * 0.86) / 15000.0

        assert abs(new_hf - expected) < 0.01

    def test_health_factor_after_shock_zero_debt(self):
        """Test health factor after shock with zero debt"""
        position = Position(
            borrower="0x123",
            market_id="0xabc",
            collateral_amount=10.0,
            collateral_value_usd=20000.0,
            debt_amount=0.0,
            debt_value_usd=0.0,
            health_factor=float('inf'),
            lltv=0.86,
            timestamp=datetime.now()
        )

        new_hf = position.health_factor_after_shock(-0.50)
        assert new_hf == float('inf')

    def test_liquidation_price_drop_pct(self, sample_position):
        """Test liquidation price drop percentage"""
        # HF = 1.15
        # Price drop needed = 1 - (1 / 1.15) = 1 - 0.8696 = 0.1304 (13.04%)
        drop_pct = sample_position.liquidation_price_drop_pct()
        expected = 1.0 - (1.0 / 1.15)

        assert abs(drop_pct - expected) < 0.001

    def test_liquidation_price_drop_pct_already_liquidatable(self):
        """Test liquidation price drop for already liquidatable position"""
        position = Position(
            borrower="0x123",
            market_id="0xabc",
            collateral_amount=1.0,
            collateral_value_usd=1000.0,
            debt_amount=1200.0,
            debt_value_usd=1200.0,
            health_factor=0.72,
            lltv=0.86,
            timestamp=datetime.now()
        )

        assert position.liquidation_price_drop_pct() == 0.0

    def test_to_dict(self, sample_position):
        """Test position serialization to dictionary"""
        result = sample_position.to_dict()

        assert isinstance(result, dict)
        assert result['borrower'] == sample_position.borrower
        assert result['market_id'] == sample_position.market_id
        assert result['collateral_amount'] == sample_position.collateral_amount
        assert result['health_factor'] == sample_position.health_factor
        assert result['is_healthy'] is True
        assert 'liquidation_price' in result
        assert 'liquidation_buffer' in result
        assert 'timestamp' in result


class TestPoolSnapshot:
    """Test suite for PoolSnapshot model"""

    @pytest.fixture
    def sample_positions(self):
        """Create sample positions for testing"""
        return [
            Position(
                borrower="0x111",
                market_id="0xabc",
                collateral_amount=10.0,
                collateral_value_usd=20000.0,
                debt_amount=15000.0,
                debt_value_usd=15000.0,
                health_factor=1.15,
                lltv=0.86,
                timestamp=datetime.now()
            ),
            Position(
                borrower="0x222",
                market_id="0xabc",
                collateral_amount=5.0,
                collateral_value_usd=10000.0,
                debt_amount=8000.0,
                debt_value_usd=8000.0,
                health_factor=1.075,
                lltv=0.86,
                timestamp=datetime.now()
            ),
            Position(
                borrower="0x333",
                market_id="0xabc",
                collateral_amount=2.0,
                collateral_value_usd=4000.0,
                debt_amount=5000.0,
                debt_value_usd=5000.0,
                health_factor=0.688,
                lltv=0.86,
                timestamp=datetime.now()
            )
        ]

    @pytest.fixture
    def sample_snapshot(self, sample_positions):
        """Create a sample pool snapshot"""
        return PoolSnapshot(
            market_id="0xabc",
            pool_name="Test Pool",
            timestamp=datetime(2024, 1, 1),
            positions=sample_positions,
            total_supply=100000.0,
            total_borrow=50000.0,
            utilization=0.5,
            lltv=0.86
        )

    def test_snapshot_creation(self, sample_snapshot):
        """Test basic snapshot creation"""
        assert sample_snapshot.market_id == "0xabc"
        assert sample_snapshot.pool_name == "Test Pool"
        assert sample_snapshot.num_positions == 3
        assert sample_snapshot.utilization == 0.5

    def test_total_collateral_usd(self, sample_snapshot):
        """Test total collateral calculation"""
        expected = 20000.0 + 10000.0 + 4000.0
        assert sample_snapshot.total_collateral_usd == expected

    def test_total_debt_usd(self, sample_snapshot):
        """Test total debt calculation"""
        expected = 15000.0 + 8000.0 + 5000.0
        assert sample_snapshot.total_debt_usd == expected

    def test_num_positions(self, sample_snapshot):
        """Test position count"""
        assert sample_snapshot.num_positions == 3

    def test_num_healthy_positions(self, sample_snapshot):
        """Test healthy position count"""
        # HF > 1.0: positions 0 and 1
        assert sample_snapshot.num_healthy_positions == 2

    def test_num_unhealthy_positions(self, sample_snapshot):
        """Test unhealthy position count"""
        # HF <= 1.0: position 2
        assert sample_snapshot.num_unhealthy_positions == 1

    def test_avg_health_factor(self, sample_snapshot):
        """Test simple average health factor"""
        # (1.15 + 1.075 + 0.688) / 3 = 0.971
        expected = (1.15 + 1.075 + 0.688) / 3
        assert abs(sample_snapshot.avg_health_factor - expected) < 0.01

    def test_weighted_avg_health_factor(self, sample_snapshot):
        """Test debt-weighted average health factor"""
        # (1.15 * 15000 + 1.075 * 8000 + 0.688 * 5000) / 28000
        total_debt = 15000.0 + 8000.0 + 5000.0
        weighted_sum = (1.15 * 15000.0) + (1.075 * 8000.0) + (0.688 * 5000.0)
        expected = weighted_sum / total_debt

        assert abs(sample_snapshot.weighted_avg_health_factor - expected) < 0.01

    def test_get_positions_by_health_factor_min(self, sample_snapshot):
        """Test filtering positions by minimum HF"""
        positions = sample_snapshot.get_positions_by_health_factor(min_hf=1.0)

        assert len(positions) == 2
        assert all(p.health_factor >= 1.0 for p in positions)

    def test_get_positions_by_health_factor_max(self, sample_snapshot):
        """Test filtering positions by maximum HF"""
        positions = sample_snapshot.get_positions_by_health_factor(max_hf=1.0)

        assert len(positions) == 1
        assert all(p.health_factor <= 1.0 for p in positions)

    def test_get_positions_by_health_factor_range(self, sample_snapshot):
        """Test filtering positions by HF range"""
        positions = sample_snapshot.get_positions_by_health_factor(min_hf=1.0, max_hf=1.1)

        assert len(positions) == 1
        assert all(1.0 <= p.health_factor <= 1.1 for p in positions)

    def test_get_top_borrowers(self, sample_snapshot):
        """Test getting top borrowers"""
        top_2 = sample_snapshot.get_top_borrowers(n=2)

        assert len(top_2) == 2
        assert top_2[0].debt_value_usd == 15000.0  # Largest
        assert top_2[1].debt_value_usd == 8000.0   # Second largest

    def test_get_top_borrowers_all(self, sample_snapshot):
        """Test getting all borrowers as top N"""
        top_10 = sample_snapshot.get_top_borrowers(n=10)

        # Should return all 3 even though we asked for 10
        assert len(top_10) == 3

    def test_to_dict(self, sample_snapshot):
        """Test snapshot serialization to dictionary"""
        result = sample_snapshot.to_dict()

        assert isinstance(result, dict)
        assert result['market_id'] == "0xabc"
        assert result['pool_name'] == "Test Pool"
        assert result['num_positions'] == 3
        assert result['utilization'] == 0.5
        assert 'total_collateral_usd' in result
        assert 'total_debt_usd' in result
        assert 'avg_health_factor' in result
        assert 'weighted_avg_health_factor' in result
        assert 'num_healthy_positions' in result
        assert 'num_unhealthy_positions' in result

    def test_empty_snapshot(self):
        """Test snapshot with no positions"""
        snapshot = PoolSnapshot(
            market_id="0xabc",
            pool_name="Empty Pool",
            timestamp=datetime.now(),
            positions=[],
            total_supply=0.0,
            total_borrow=0.0,
            utilization=0.0,
            lltv=0.86
        )

        assert snapshot.num_positions == 0
        assert snapshot.total_collateral_usd == 0.0
        assert snapshot.total_debt_usd == 0.0
        assert snapshot.num_healthy_positions == 0
        assert snapshot.num_unhealthy_positions == 0
        assert snapshot.avg_health_factor == float('inf')
        assert snapshot.weighted_avg_health_factor == float('inf')

    def test_snapshot_with_infinite_health_factors(self):
        """Test snapshot with positions having infinite HF"""
        positions = [
            Position(
                borrower="0x111",
                market_id="0xabc",
                collateral_amount=10.0,
                collateral_value_usd=20000.0,
                debt_amount=0.0,
                debt_value_usd=0.0,
                health_factor=float('inf'),
                lltv=0.86,
                timestamp=datetime.now()
            ),
            Position(
                borrower="0x222",
                market_id="0xabc",
                collateral_amount=5.0,
                collateral_value_usd=10000.0,
                debt_amount=0.0,
                debt_value_usd=0.0,
                health_factor=float('inf'),
                lltv=0.86,
                timestamp=datetime.now()
            )
        ]

        snapshot = PoolSnapshot(
            market_id="0xabc",
            pool_name="Test Pool",
            timestamp=datetime.now(),
            positions=positions,
            total_supply=100000.0,
            total_borrow=0.0,
            utilization=0.0,
            lltv=0.86
        )

        assert snapshot.avg_health_factor == float('inf')
        assert snapshot.weighted_avg_health_factor == float('inf')
