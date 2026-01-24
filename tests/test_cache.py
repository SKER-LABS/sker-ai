"""Tests for Cache Manager"""
import time
import pytest
from engine.utils.cache import CacheManager


def test_set_and_get():
    cache = CacheManager(max_size=10)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"


def test_ttl_expiration():
    cache = CacheManager(max_size=10, default_ttl=1)
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"
    time.sleep(1.1)
    assert cache.get("key1") is None


def test_lru_eviction():
    cache = CacheManager(max_size=3)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.set("d", 4)
    assert cache.get("a") is None
    assert cache.get("d") == 4


def test_stats():
    cache = CacheManager(max_size=10)
    cache.set("k", "v")
    cache.get("k")
    cache.get("missing")
    stats = cache.stats
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_invalidate():
    cache = CacheManager(max_size=10)
    cache.set("k", "v")
    assert cache.invalidate("k") is True
    assert cache.get("k") is None


def test_cleanup_expired():
    cache = CacheManager(max_size=10, default_ttl=1)
    cache.set("a", 1)
    cache.set("b", 2)
    time.sleep(1.1)
    removed = cache.cleanup_expired()
    assert removed == 2
