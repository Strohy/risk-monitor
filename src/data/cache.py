"""Simple file-based cache for Dune data to reduce API calls"""

import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataCache:
    """Simple file-based cache for Dune data"""

    def __init__(self, cache_dir: Path = None, ttl_minutes: int = 60):
        """
        Initialize cache

        Args:
            cache_dir: Directory to store cache files (default: data/raw)
            ttl_minutes: Time-to-live for cache entries in minutes
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent.parent / "data" / "raw"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(minutes=ttl_minutes)
        logger.info(f"Initialized cache at {self.cache_dir} with {ttl_minutes}min TTL")

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for a key"""
        safe_key = key.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """
        Get cached data if valid

        Args:
            key: Cache key

        Returns:
            DataFrame if cache hit and valid, None otherwise
        """
        cache_file = self._get_cache_path(key)

        if not cache_file.exists():
            logger.debug(f"Cache miss: {key}")
            return None

        # Check if cache is still valid
        file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
        age = datetime.now() - file_time

        if age > self.ttl:
            logger.debug(f"Cache expired: {key} (age: {age})")
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            df = pd.DataFrame(data)
            logger.info(f"Cache hit: {key} ({len(df)} rows, age: {age})")
            return df

        except Exception as e:
            logger.warning(f"Error reading cache for {key}: {e}")
            return None

    def set(self, key: str, data: pd.DataFrame):
        """
        Cache data to file

        Args:
            key: Cache key
            data: DataFrame to cache
        """
        cache_file = self._get_cache_path(key)

        try:
            with open(cache_file, 'w') as f:
                json.dump(data.to_dict('records'), f, default=str)

            logger.info(f"Cached {len(data)} rows for key: {key}")

        except Exception as e:
            logger.warning(f"Error writing cache for {key}: {e}")

    def clear(self, key: Optional[str] = None):
        """
        Clear cache

        Args:
            key: Specific key to clear, or None to clear all
        """
        if key is None:
            # Clear all cache files
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Cleared all cache")
        else:
            cache_file = self._get_cache_path(key)
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"Cleared cache for: {key}")

    def get_cache_info(self) -> dict:
        """Get information about cache contents"""
        cache_files = list(self.cache_dir.glob("*.json"))

        info = {
            'cache_dir': str(self.cache_dir),
            'ttl_minutes': self.ttl.total_seconds() / 60,
            'num_files': len(cache_files),
            'files': []
        }

        for cache_file in cache_files:
            file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
            age = datetime.now() - file_time
            is_valid = age <= self.ttl

            info['files'].append({
                'name': cache_file.stem,
                'age_minutes': age.total_seconds() / 60,
                'is_valid': is_valid,
                'size_kb': cache_file.stat().st_size / 1024
            })

        return info
