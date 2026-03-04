"""
Cache Manager
Analysis result caching (in-memory + Redis)

TODO: Redis integration — currently in-memory only
Redis required for multi-instance deployments
"""

from __future__ import annotations

import time
from typing import Any, Optional
from collections import OrderedDict
from loguru import logger

from ..config import config


class CacheManager:
    """LRU-based in-memory cache. Temporary implementation before Redis integration."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self._store: OrderedDict[str, tuple[Any, float, int]] = OrderedDict()
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            self._misses += 1
            return None

        value, ts, ttl = self._store[key]

        # TTL expiration check
        if time.time() - ts > ttl:
            del self._store[key]
            self._misses += 1
            return None

        # LRU: move accessed item to end
        self._store.move_to_end(key)
        self._hits += 1
        return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if ttl is None:
            ttl = self.default_ttl

        # update existing key
        if key in self._store:
            self._store.move_to_end(key)
            self._store[key] = (value, time.time(), ttl)
            return

        # evict oldest when over capacity
        while len(self._store) >= self.max_size:
            evicted_key, _ = self._store.popitem(last=False)
            logger.debug(f"Cache evicted: {evicted_key[:16]}...")

        self._store[key] = (value, time.time(), ttl)

    def invalidate(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> int:
        count = len(self._store)
        self._store.clear()
        return count

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "size": len(self._store),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 3),
        }

    def cleanup_expired(self) -> int:
        """Batch cleanup of expired entries. Called periodically by background task."""
        now = time.time()
        expired = [
            k for k, (_, ts, ttl) in self._store.items()
            if now - ts > ttl
        ]
        for k in expired:
            del self._store[k]
        if expired:
            logger.debug(f"Expired cache cleaned: {len(expired)} entries")
        return len(expired)

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return key in self._store and not self._is_expired(key)

    def _is_expired(self, key: str) -> bool:
        if key not in self._store:
            return True
        _, ts, ttl = self._store[key]
        return time.time() - ts > ttl


# WIP: Redis backend integration
# class RedisCacheBackend:
#     """Production cache backend using Redis.
#     Replaces in-memory LRU for multi-instance deployments."""
#     def __init__(self, redis_url: str, prefix: str = "sker:cache:"):
#         self.prefix = prefix
#         # TODO: implement redis connection pool
#         pass
