"""
Rate Limiter
API call rate control (token bucket algorithm)

Usage:
- Helius RPC: 50 req/s
- Twitter API: 15 req/15min (app level)
- GoPlus: 30 req/min
- Per-user scan limits (tier-based)
"""

from __future__ import annotations

import time
import asyncio
from typing import Optional
from loguru import logger


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, rate: float, burst: int, name: str = "default"):
        """
        Args:
            rate: allowed requests per second
            burst: maximum burst size
            name: identifier name
        """
        self.rate = rate
        self.burst = burst
        self.name = name
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self._total_requests = 0
        self._total_throttled = 0

    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """Consume 1 token. Waits if insufficient."""
        async with self._lock:
            self._refill()

            if self._tokens >= 1:
                self._tokens -= 1
                self._total_requests += 1
                return True

            # insufficient tokens — calculate wait time
            wait_time = (1 - self._tokens) / self.rate

            if timeout is not None and wait_time > timeout:
                self._total_throttled += 1
                logger.warning(f"[{self.name}] rate limit exceeded (wait={wait_time:.1f}s > timeout={timeout}s)")
                return False

        # wait outside lock (prevent blocking other requests)
        await asyncio.sleep(wait_time)

        async with self._lock:
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                self._total_requests += 1
                return True

            self._total_throttled += 1
            return False

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_refill = now

    @property
    def available(self) -> float:
        """Currently available tokens"""
        self._refill()
        return self._tokens

    @property
    def stats(self) -> dict:
        return {
            "name": self.name,
            "rate": self.rate,
            "burst": self.burst,
            "available": round(self.available, 1),
            "total_requests": self._total_requests,
            "total_throttled": self._total_throttled,
        }


# presets — per-service rate limiters
# HACK: hardcoded rate limits — should dynamically read from API response headers
HELIUS_LIMITER = RateLimiter(rate=50, burst=50, name="helius")
TWITTER_LIMITER = RateLimiter(rate=0.016, burst=1, name="twitter")  # 15req/15min
GOPLUS_LIMITER = RateLimiter(rate=0.5, burst=5, name="goplus")
BIRDEYE_LIMITER = RateLimiter(rate=2, burst=10, name="birdeye")
