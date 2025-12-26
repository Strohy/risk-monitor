"""Tests for StateReconstructor"""

import pytest
import pandas as pd
import tempfile
import json
from pathlib import Path
from datetime import datetime
from src.state.reconstructor import StateReconstructor
from src.state.models import Position, PoolSnapshot


@pytest.fixture
def pool_config():
    """Sample pool configuration"""
    return {
        'name': 'wstETH/USDC',
        'market_id': '0xabc123',
        'collateral': 'wstETH',
        'collateral_address': '0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0',
        'loan': 'USDC',
        'loan_address': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
        'lltv': 0.86
    }


@pytest.fixture
def prices():
    """Sample token prices"""
    return {
        '0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0': 2500.0,  # wstETH
        '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 1.0      # USDC
    }


@pytest.fixture
def positions_df():
    """Sample positions DataFrame"""
    return pd.DataFrame([
        {
            'market_id': '0xabc123',
            'borrower': '0x111',
            'active_borrow_assets': 10000.0,
            'last_borrow_time': '2024-01-01 12:00:00'
        },
        {
            'market_id': '0xabc123',
            'borrower': '0x222',
            'active_borrow_assets': 5000.0,
            'last_borrow_time': '2024-01-01 12:00:00'
        }
    ])


@pytest.fixture
def collateral_df():
    """Sample collateral DataFrame"""
    return pd.DataFrame([
        {
            'market_id': '0xabc123',
            'borrower': '0x111',
            'collateral': 10.0,  # 10 wstETH
            'block_time': '2024-01-01 12:00:00'
        },
        {
            'market_id': '0xabc123',
            'borrower': '0x222',
            'collateral': 5.0,   # 5 wstETH
            'block_time': '2024-01-01 12:00:00'
        }
    ])


@pytest.fixture
def pool_state_df():
    """Sample pool state DataFrame"""
    return pd.DataFrame([
        {
            'market_id': '0xabc123',
            'call_block_time': '2024-01-01 12:00:00',
            'output_totalSupplyAssets': 100000.0,
            'output_totalBorrowAssets': 50000.0
        }
    ])


@pytest.fixture
def reconstructor(pool_config, prices):
    """Create StateReconstructor instance"""
    return StateReconstructor(pool_config, prices)


class TestStateReconstructor:
    """Test suite for StateReconstructor"""

    def test_init(self, pool_config, prices):
        """Test reconstructor initialization"""
        reconstructor = StateReconstructor(pool_config, prices)

        assert reconstructor.pool_config == pool_config
        # Prices should be normalized to lowercase
        assert '0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0' in reconstructor.prices

    def test_get_token_price_found(self, reconstructor):
        """Test getting token price that exists"""
        price = reconstructor._get_token_price('0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0')
        assert price == 2500.0

    def test_get_token_price_not_found(self, reconstructor):
        """Test getting token price that doesn't exist"""
        price = reconstructor._get_token_price('0xdeadbeef')
        assert price == 0.0

    def test_get_token_price_case_insensitive(self, reconstructor):
        """Test that price lookup is case insensitive"""
        price1 = reconstructor._get_token_price('0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0')
        price2 = reconstructor._get_token_price('0X7F39C581F595B53C5CB19BD0B3F8DA6C935E2CA0')
        assert price1 == price2 == 2500.0

    def test_reconstruct_positions_success(self, reconstructor, positions_df, collateral_df):
        """Test successful position reconstruction"""
        positions = reconstructor.reconstruct_positions(positions_df, collateral_df)

        assert len(positions) == 2
        assert all(isinstance(p, Position) for p in positions)

        # Check first position
        pos1 = positions[0]
        assert pos1.borrower == '0x111'
        assert pos1.collateral_amount == 10.0
        assert pos1.collateral_value_usd == 10.0 * 2500.0  # 25000
        assert pos1.debt_value_usd == 10000.0

        # Health factor = (25000 * 0.86) / 10000 = 2.15
        expected_hf = (25000.0 * 0.86) / 10000.0
        assert abs(pos1.health_factor - expected_hf) < 0.01

    def test_reconstruct_positions_empty(self, reconstructor):
        """Test reconstruction with empty DataFrame"""
        empty_df = pd.DataFrame()
        positions = reconstructor.reconstruct_positions(empty_df, empty_df)

        assert len(positions) == 0

    def test_reconstruct_positions_missing_collateral(self, reconstructor, positions_df):
        """Test reconstruction when some positions lack collateral"""
        # Collateral only for one borrower
        partial_collateral = pd.DataFrame([
            {
                'market_id': '0xabc123',
                'borrower': '0x111',
                'collateral': 10.0,
                'block_time': '2024-01-01'
            }
        ])

        positions = reconstructor.reconstruct_positions(positions_df, partial_collateral)

        # Should still get 2 positions (missing collateral filled with 0)
        assert len(positions) == 2

        # Position 0x222 should have 0 collateral
        pos_222 = [p for p in positions if p.borrower == '0x222'][0]
        assert pos_222.collateral_amount == 0.0

    def test_reconstruct_positions_zero_debt(self, reconstructor, collateral_df):
        """Test reconstruction with zero debt (infinite HF)"""
        zero_debt_df = pd.DataFrame([
            {
                'market_id': '0xabc123',
                'borrower': '0x111',
                'active_borrow_assets': 0.0,
                'last_borrow_time': '2024-01-01'
            }
        ])

        positions = reconstructor.reconstruct_positions(zero_debt_df, collateral_df)

        assert len(positions) == 1
        assert positions[0].health_factor == float('inf')

    def test_create_snapshot_success(self, reconstructor, positions_df, collateral_df, pool_state_df):
        """Test successful snapshot creation"""
        snapshot = reconstructor.create_snapshot(
            positions_df,
            collateral_df,
            pool_state_df,
            timestamp=datetime(2024, 1, 1)
        )

        assert isinstance(snapshot, PoolSnapshot)
        assert snapshot.market_id == '0xabc123'
        assert snapshot.pool_name == 'wstETH/USDC'
        assert snapshot.num_positions == 2
        assert snapshot.total_supply == 100000.0
        assert snapshot.total_borrow == 50000.0
        assert snapshot.utilization == 0.5

    def test_create_snapshot_with_timestamp(self, reconstructor, positions_df, collateral_df, pool_state_df):
        """Test snapshot creation with custom timestamp"""
        custom_time = datetime(2024, 6, 15, 10, 30)
        snapshot = reconstructor.create_snapshot(
            positions_df,
            collateral_df,
            pool_state_df,
            timestamp=custom_time
        )

        assert snapshot.timestamp == custom_time

    def test_create_snapshot_empty_pool_state(self, reconstructor, positions_df, collateral_df):
        """Test snapshot creation with empty pool state"""
        empty_pool_state = pd.DataFrame()

        snapshot = reconstructor.create_snapshot(
            positions_df,
            collateral_df,
            empty_pool_state
        )

        # Should still create snapshot with aggregated values
        assert isinstance(snapshot, PoolSnapshot)
        assert snapshot.num_positions == 2
        # Total supply/borrow will be derived from positions
        assert snapshot.total_collateral_usd > 0

    def test_save_and_load_snapshot(self, reconstructor, positions_df, collateral_df, pool_state_df):
        """Test saving and loading snapshot to/from file"""
        # Create snapshot
        snapshot = reconstructor.create_snapshot(
            positions_df,
            collateral_df,
            pool_state_df,
            timestamp=datetime(2024, 1, 1)
        )

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name

        try:
            reconstructor.save_snapshot(snapshot, temp_path)

            # Verify file exists and contains data
            assert Path(temp_path).exists()

            with open(temp_path, 'r') as f:
                data = json.load(f)

            assert 'snapshot' in data
            assert 'positions' in data
            assert len(data['positions']) == 2

            # Load snapshot back
            loaded_snapshot = reconstructor.load_snapshot(temp_path)

            assert isinstance(loaded_snapshot, PoolSnapshot)
            assert loaded_snapshot.market_id == snapshot.market_id
            assert loaded_snapshot.pool_name == snapshot.pool_name
            assert loaded_snapshot.num_positions == snapshot.num_positions
            assert len(loaded_snapshot.positions) == len(snapshot.positions)

            # Check positions were reconstructed
            for orig, loaded in zip(snapshot.positions, loaded_snapshot.positions):
                assert loaded.borrower == orig.borrower
                assert loaded.health_factor == orig.health_factor
                assert loaded.debt_value_usd == orig.debt_value_usd

        finally:
            # Cleanup
            if Path(temp_path).exists():
                Path(temp_path).unlink()

    def test_save_snapshot_creates_directory(self, reconstructor, positions_df, collateral_df, pool_state_df):
        """Test that save_snapshot creates parent directories"""
        snapshot = reconstructor.create_snapshot(
            positions_df,
            collateral_df,
            pool_state_df
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = Path(temp_dir) / "subdir1" / "subdir2" / "snapshot.json"

            reconstructor.save_snapshot(snapshot, str(nested_path))

            assert nested_path.exists()

    def test_reconstruct_positions_health_factor_calculation(self, reconstructor):
        """Test that health factors are calculated correctly"""
        positions_df = pd.DataFrame([
            {
                'market_id': '0xabc123',
                'borrower': '0x111',
                'active_borrow_assets': 10000.0,
                'last_borrow_time': '2024-01-01'
            }
        ])

        collateral_df = pd.DataFrame([
            {
                'market_id': '0xabc123',
                'borrower': '0x111',
                'collateral': 5.0,  # 5 wstETH at $2500 = $12500
                'block_time': '2024-01-01'
            }
        ])

        positions = reconstructor.reconstruct_positions(positions_df, collateral_df)

        # Health factor = (12500 * 0.86) / 10000 = 1.075
        expected_hf = (5.0 * 2500.0 * 0.86) / 10000.0

        assert len(positions) == 1
        assert abs(positions[0].health_factor - expected_hf) < 0.001

    def test_reconstruct_positions_with_malformed_data(self, reconstructor):
        """Test reconstruction handles malformed data gracefully"""
        # Missing required fields
        bad_positions = pd.DataFrame([
            {
                'market_id': '0xabc123',
                'borrower': '0x111',
                # Missing active_borrow_assets
            }
        ])

        bad_collateral = pd.DataFrame([
            {
                'market_id': '0xabc123',
                'borrower': '0x111',
                'collateral': 10.0
            }
        ])

        # Should handle gracefully and return empty or partial results
        positions = reconstructor.reconstruct_positions(bad_positions, bad_collateral)

        # Should either skip bad records or use defaults
        assert isinstance(positions, list)

    def test_snapshot_aggregates_match_positions(self, reconstructor, positions_df, collateral_df, pool_state_df):
        """Test that snapshot aggregates match sum of positions"""
        snapshot = reconstructor.create_snapshot(
            positions_df,
            collateral_df,
            pool_state_df
        )

        # Sum up position values
        total_collateral = sum(p.collateral_value_usd for p in snapshot.positions)
        total_debt = sum(p.debt_value_usd for p in snapshot.positions)

        assert snapshot.total_collateral_usd == total_collateral
        assert snapshot.total_debt_usd == total_debt

    def test_positions_have_correct_lltv(self, reconstructor, positions_df, collateral_df):
        """Test that reconstructed positions have correct LLTV"""
        positions = reconstructor.reconstruct_positions(positions_df, collateral_df)

        assert all(p.lltv == 0.86 for p in positions)

    def test_positions_have_timestamps(self, reconstructor, positions_df, collateral_df):
        """Test that positions have timestamps"""
        positions = reconstructor.reconstruct_positions(positions_df, collateral_df)

        assert all(p.timestamp is not None for p in positions)
        assert all(isinstance(p.timestamp, datetime) for p in positions)
