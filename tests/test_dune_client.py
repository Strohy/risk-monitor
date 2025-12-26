"""Tests for Dune Analytics client"""

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from src.data.dune_client import MorphoDataFetcher


@pytest.fixture
def mock_dune_client():
    """Fixture to create a mocked Dune client"""
    with patch('src.data.dune_client.DuneClient') as mock_client:
        yield mock_client


@pytest.fixture
def fetcher(mock_dune_client):
    """Fixture to create MorphoDataFetcher with mocked client"""
    return MorphoDataFetcher(api_key="test_api_key")


class TestMorphoDataFetcher:
    """Test suite for MorphoDataFetcher"""

    def test_init(self, mock_dune_client):
        """Test initialization"""
        fetcher = MorphoDataFetcher(api_key="test_key")

        assert fetcher.client is not None
        assert fetcher.queries_dir.exists()
        mock_dune_client.assert_called_once_with("test_key")

    def test_load_query_success(self, fetcher):
        """Test loading a query file successfully"""
        query = fetcher._load_query("pool_state")

        assert isinstance(query, str)
        assert len(query) > 0
        assert "SELECT" in query.upper()

    def test_load_query_not_found(self, fetcher):
        """Test loading a non-existent query file"""
        with pytest.raises(FileNotFoundError):
            fetcher._load_query("nonexistent_query")

    def test_format_market_ids(self, fetcher):
        """Test market ID formatting for SQL"""
        market_ids = [
            "0xc54d7acf14de29e0e5527cabd7a576506870346a78a11a6762e2cca66322ec41",
            "b323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc"
        ]

        result = fetcher._format_market_ids(market_ids)

        print(result)
        assert "0xc54d7acf14de29e0e5527cabd7a576506870346a78a11a6762e2cca66322ec41" in result
        assert "0xb323495f7e4148be5643a4ea4a8221eef163e4bccfdedc2a6f4696baacbc86cc" in result
        assert "," in result

    def test_format_addresses(self, fetcher):
        """Test address formatting for SQL"""
        addresses = [
            "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0",
            "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
        ]

        result = fetcher._format_addresses(addresses)

        # Should be lowercase
        assert "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0" in result
        assert "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48" in result
        assert "," in result

    def test_fetch_pool_state_success(self, fetcher, mock_dune_client):
        """Test successful pool state fetch"""
        # Mock the response
        mock_result = MagicMock()
        mock_result.result.rows = [
            {
                'market_id': '0xabc',
                'call_block_time': '2024-01-01',
                'output_totalSupplyAssets': 1000000,
                'output_totalBorrowAssets': 500000
            }
        ]
        fetcher.client.run_query.return_value = mock_result

        market_ids = ['0xabc']
        result = fetcher.fetch_pool_state(market_ids)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]['market_id'] == '0xabc'
        assert result.iloc[0]['utilization'] == 0.5

    def test_fetch_pool_state_error(self, fetcher, mock_dune_client):
        """Test pool state fetch with error"""
        fetcher.client.run_query.side_effect = Exception("API Error")

        market_ids = ['0xabc']

        with pytest.raises(Exception, match="API Error"):
            fetcher.fetch_pool_state(market_ids)

    def test_fetch_positions_success(self, fetcher, mock_dune_client):
        """Test successful positions fetch"""
        mock_result = MagicMock()
        mock_result.result.rows = [
            {
                'market_id': '0xabc',
                'borrower': '0x123',
                'active_borrow_shares': 100,
                'active_borrow_assets': 1000,
                'last_borrow_time': '2024-01-01'
            }
        ]
        fetcher.client.run_query.return_value = mock_result

        result = fetcher.fetch_positions(['0xabc'])

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]['borrower'] == '0x123'

    def test_fetch_collateral_success(self, fetcher, mock_dune_client):
        """Test successful collateral fetch"""
        mock_result = MagicMock()
        mock_result.result.rows = [
            {
                'market_id': '0xabc',
                'borrower': '0x123',
                'collateral': 5000,
                'block_time': '2024-01-01'
            }
        ]
        fetcher.client.run_query.return_value = mock_result

        result = fetcher.fetch_collateral(['0xabc'])

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]['collateral'] == 5000

    def test_fetch_liquidations_success(self, fetcher, mock_dune_client):
        """Test successful liquidations fetch"""
        mock_result = MagicMock()
        mock_result.result.rows = [
            {
                'evt_block_time': '2024-01-01',
                'market_id': '0xabc',
                'borrower': '0x123',
                'seized_assets': 1000,
                'repaid_assets': 900
            }
        ]
        fetcher.client.run_query.return_value = mock_result

        result = fetcher.fetch_liquidations(['0xabc'], days=90)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert result.iloc[0]['seized_assets'] == 1000

    def test_fetch_prices_success(self, fetcher, mock_dune_client):
        """Test successful price fetch"""
        mock_result = MagicMock()
        mock_result.result.rows = [
            {
                'contract_address': '0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0',
                'symbol': 'wstETH',
                'decimals': 18,
                'price': 2500.50,
                'minute': '2024-01-01 12:00:00'
            },
            {
                'contract_address': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
                'symbol': 'USDC',
                'decimals': 6,
                'price': 1.0,
                'minute': '2024-01-01 12:00:00'
            }
        ]
        fetcher.client.run_query.return_value = mock_result

        addresses = [
            '0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0',
            '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
        ]
        result = fetcher.fetch_prices(addresses)

        assert isinstance(result, dict)
        assert len(result) == 2
        assert result['0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0'] == 2500.50
        assert result['0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'] == 1.0

    def test_fetch_prices_empty_result(self, fetcher, mock_dune_client):
        """Test price fetch with empty result"""
        mock_result = MagicMock()
        mock_result.result.rows = []
        fetcher.client.run_query.return_value = mock_result

        result = fetcher.fetch_prices(['0xabc'])

        assert isinstance(result, dict)
        assert len(result) == 0

    def test_fetch_prices_deduplicate(self, fetcher, mock_dune_client):
        """Test that prices are deduplicated (most recent kept)"""
        mock_result = MagicMock()
        mock_result.result.rows = [
            {
                'contract_address': '0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0',
                'symbol': 'wstETH',
                'decimals': 18,
                'price': 2600.00,  # Most recent
                'timestamp': '2024-01-01 13:00:00'
            },
            {
                'contract_address': '0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0',
                'symbol': 'wstETH',
                'decimals': 18,
                'price': 2500.50,  # Older
                'timestamp': '2024-01-01 12:00:00'
            }
        ]
        fetcher.client.run_query.return_value = mock_result

        result = fetcher.fetch_prices(['0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0'])

        # Should only have one entry with the most recent price
        assert len(result) == 1
        assert result['0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0'] == 2600.00

    def test_fetch_all_data_success(self, fetcher, mock_dune_client):
        """Test fetching all data at once"""
        # Mock all fetch methods
        fetcher.fetch_pool_state = Mock(return_value=pd.DataFrame([{'state': 1}]))
        fetcher.fetch_positions = Mock(return_value=pd.DataFrame([{'position': 1}]))
        fetcher.fetch_collateral = Mock(return_value=pd.DataFrame([{'collateral': 1}]))
        fetcher.fetch_liquidations = Mock(return_value=pd.DataFrame([{'liquidation': 1}]))
        fetcher.fetch_prices = Mock(return_value={'0xabc': 1000.0})

        market_ids = ['0xabc']
        token_addresses = ['0x123']

        result = fetcher.fetch_all_data(market_ids, token_addresses)

        assert isinstance(result, dict)
        assert 'pool_state' in result
        assert 'positions' in result
        assert 'collateral' in result
        assert 'liquidations' in result
        assert 'prices' in result

        # Verify all methods were called
        fetcher.fetch_pool_state.assert_called_once_with(market_ids)
        fetcher.fetch_positions.assert_called_once_with(market_ids)
        fetcher.fetch_collateral.assert_called_once_with(market_ids)
        fetcher.fetch_liquidations.assert_called_once_with(market_ids)
        fetcher.fetch_prices.assert_called_once_with(token_addresses)


class TestQueryFileIntegrity:
    """Test that all query files are valid"""

    def test_all_query_files_exist(self):
        """Test that all expected query files exist"""
        queries_dir = Path(__file__).parent.parent / "queries"

        expected_queries = [
            'pool_state.sql',
            'positions.sql',
            'collateral.sql',
            'liquidations.sql',
            'prices.sql'
        ]

        for query_file in expected_queries:
            query_path = queries_dir / query_file
            assert query_path.exists(), f"Query file missing: {query_file}"

    def test_query_files_contain_select(self):
        """Test that all query files contain SELECT statements"""
        queries_dir = Path(__file__).parent.parent / "queries"

        for query_file in queries_dir.glob("*.sql"):
            with open(query_file, 'r') as f:
                content = f.read()

            assert "SELECT" in content.upper(), f"No SELECT in {query_file.name}"

    def test_query_files_contain_placeholders(self):
        """Test that query files contain expected placeholders"""
        queries_dir = Path(__file__).parent.parent / "queries"

        placeholder_requirements = {
            'pool_state.sql': ['{{market_ids}}'],
            'positions.sql': ['{{market_ids}}'],
            'collateral.sql': ['{{market_ids}}'],
            'liquidations.sql': ['{{market_ids}}'],
            'prices.sql': ['{{token_addresses}}']
        }

        for query_file, placeholders in placeholder_requirements.items():
            query_path = queries_dir / query_file

            with open(query_path, 'r') as f:
                content = f.read()

            for placeholder in placeholders:
                assert placeholder in content, \
                    f"Missing placeholder {placeholder} in {query_file}"
