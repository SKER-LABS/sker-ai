"""Tests for Rate Limiter"""
import asyncio
import pytest
from engine.utils.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_acquire_within_burst():
    limiter = RateLimiter(rate=10, burst=5, name="test")
    for _ in range(5):
        assert await limiter.acquire()


@pytest.mark.asyncio
async def test_timeout_exceeded():
    limiter = RateLimiter(rate=0.1, burst=1, name="test")
    await limiter.acquire()
    result = await limiter.acquire(timeout=0.01)
    assert result is False


def test_stats():
    limiter = RateLimiter(rate=10, burst=10, name="test")
    stats = limiter.stats
    assert stats["name"] == "test"
    assert stats["rate"] == 10
    assert stats["burst"] == 10
