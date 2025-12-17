"""Tests for data cache"""

import pytest
import pandas as pd
from pathlib import Path
import tempfile
import shutil
import time
from datetime import datetime
from src.data.cache import DataCache


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def cache(temp_cache_dir):
    """Create a DataCache instance with temp directory"""
    return DataCache(cache_dir=temp_cache_dir, ttl_minutes=1)


class TestDataCache:
    """Test suite for DataCache"""

    def test_init(self, temp_cache_dir):
        """Test cache initialization"""
        cache = DataCache(cache_dir=temp_cache_dir, ttl_minutes=60)

        assert cache.cache_dir == temp_cache_dir
        assert cache.ttl.total_seconds() == 60 * 60
        assert cache.cache_dir.exists()

    def test_init_default_dir(self):
        """Test cache initialization with default directory"""
        cache = DataCache()

        expected_dir = Path(__file__).parent.parent / "data" / "raw"
        assert cache.cache_dir == expected_dir

    def test_get_cache_path(self, cache):
        """Test cache path generation"""
        key = "test_key"
        path = cache._get_cache_path(key)

        assert path.name == "test_key.json"
        assert path.parent == cache.cache_dir

    def test_get_cache_path_safe_characters(self, cache):
        """Test that cache path handles special characters"""
        key = "test/key:with:special"
        path = cache._get_cache_path(key)

        # Should replace / and : with _
        assert "/" not in path.name
        assert ":" not in path.name
        assert path.name == "test_key_with_special.json"

    def test_set_and_get_success(self, cache):
        """Test setting and getting cache"""
        key = "test_data"
        data = pd.DataFrame({
            'col1': [1, 2, 3],
            'col2': ['a', 'b', 'c']
        })

        # Set cache
        cache.set(key, data)

        # Get cache
        result = cache.get(key)

        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert list(result.columns) == ['col1', 'col2']
        pd.testing.assert_frame_equal(result, data)

    def test_get_cache_miss(self, cache):
        """Test getting non-existent cache"""
        result = cache.get("nonexistent_key")

        assert result is None

    def test_get_cache_expired(self, cache):
        """Test that expired cache returns None"""
        key = "test_data"
        data = pd.DataFrame({'col': [1, 2, 3]})

        # Set cache
        cache.set(key, data)

        # Manually modify file time to be older than TTL
        cache_file = cache._get_cache_path(key)
        old_time = time.time() - (2 * 60)  # 2 minutes ago (TTL is 1 minute)
        cache_file.touch()
        cache_file.stat()  # Force stat update

        # Modify mtime
        import os
        os.utime(cache_file, (old_time, old_time))

        # Should return None because cache is expired
        result = cache.get(key)

        assert result is None

    def test_get_cache_valid(self, cache):
        """Test that valid cache is returned"""
        key = "test_data"
        data = pd.DataFrame({'col': [1, 2, 3]})

        # Set cache
        cache.set(key, data)

        # Should return data because cache is fresh
        result = cache.get(key)

        assert result is not None
        pd.testing.assert_frame_equal(result, data)

    def test_clear_specific_key(self, cache):
        """Test clearing specific cache key"""
        key1 = "test_data_1"
        key2 = "test_data_2"
        data = pd.DataFrame({'col': [1]})

        cache.set(key1, data)
        cache.set(key2, data)

        # Clear only key1
        cache.clear(key1)

        assert cache.get(key1) is None
        assert cache.get(key2) is not None

    def test_clear_all(self, cache):
        """Test clearing all cache"""
        key1 = "test_data_1"
        key2 = "test_data_2"
        data = pd.DataFrame({'col': [1]})

        cache.set(key1, data)
        cache.set(key2, data)

        # Clear all
        cache.clear()

        assert cache.get(key1) is None
        assert cache.get(key2) is None

    def test_get_cache_info(self, cache):
        """Test getting cache information"""
        # Set some cache entries
        cache.set("key1", pd.DataFrame({'col': [1]}))
        cache.set("key2", pd.DataFrame({'col': [2, 3]}))

        info = cache.get_cache_info()

        assert 'cache_dir' in info
        assert 'ttl_minutes' in info
        assert 'num_files' in info
        assert 'files' in info

        assert info['num_files'] == 2
        assert info['ttl_minutes'] == 1.0
        assert len(info['files']) == 2

        # Check file info
        file_names = [f['name'] for f in info['files']]
        assert 'key1' in file_names
        assert 'key2' in file_names

        # Check that files are marked as valid
        for file_info in info['files']:
            assert file_info['is_valid'] is True
            assert file_info['age_minutes'] < 1.0  # Should be fresh
            assert file_info['size_kb'] > 0

    def test_cache_with_datetime(self, cache):
        """Test caching DataFrame with datetime objects"""
        key = "datetime_data"
        data = pd.DataFrame({
            'timestamp': [datetime.now()],
            'value': [100]
        })

        # Should handle datetime serialization
        cache.set(key, data)
        result = cache.get(key)

        assert result is not None
        assert len(result) == 1

    def test_cache_with_empty_dataframe(self, cache):
        """Test caching empty DataFrame"""
        key = "empty_data"
        data = pd.DataFrame()

        cache.set(key, data)
        result = cache.get(key)

        assert result is not None
        assert len(result) == 0

    def test_cache_file_creation(self, cache):
        """Test that cache file is actually created"""
        key = "test_file"
        data = pd.DataFrame({'col': [1]})

        cache.set(key, data)

        cache_file = cache._get_cache_path(key)
        assert cache_file.exists()
        assert cache_file.suffix == '.json'

    def test_cache_resilience_to_corrupted_file(self, cache):
        """Test that cache handles corrupted files gracefully"""
        key = "corrupted_data"
        cache_file = cache._get_cache_path(key)

        # Create a corrupted cache file
        with open(cache_file, 'w') as f:
            f.write("not valid json {{{")

        # Should return None instead of crashing
        result = cache.get(key)
        assert result is None
