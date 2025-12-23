"""
Security API Aggregator
External security API data aggregation

Sources:
- GoPlus: honeypot detection, tax check
- Rugcheck: rug score
- Jupiter: verified status
- CoinGecko: market data
- Birdeye: trading metrics
"""

from __future__ import annotations

import asyncio
from typing import Optional
import httpx
from loguru import logger

from ..core.feature_store import FeatureStore
from ..config import config


class SecurityAggregator:
    """Parallel query of 5 security APIs -> store in FeatureStore"""

    def __init__(self):
        self.timeout = 10
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def aggregate(self, ca: str, store: FeatureStore) -> None:
        """Query all security APIs in parallel"""
        logger.info(f"Security API collection started: {ca[:8]}...")

        results = await asyncio.gather(
            self._fetch_goplus(ca),
            self._fetch_rugcheck(ca),
            self._fetch_jupiter(ca),
            self._fetch_coingecko(ca),
            self._fetch_birdeye(ca),
            return_exceptions=True,
        )

        for i, result in enumerate(results):
            if isinstance(result, dict):
                store.bulk_set(result)
            elif isinstance(result, Exception):
                sources = ["goplus", "rugcheck", "jupiter", "coingecko", "birdeye"]
                # HACK: GoPlus has intermittent timeouts — no retry (prevents overall response delay)
                logger.warning(f"Security API {sources[i]} failed: {result}")

    async def _fetch_goplus(self, ca: str) -> dict[str, float]:
        """GoPlus Security API — honeypot, tax detection"""
        client = await self._get_client()

        resp = await client.get(
            f"https://api.gopluslabs.com/api/v1/solana/token_security/{ca}"
        )
        resp.raise_for_status()
        data = resp.json().get("result", {}).get(ca.lower(), {})

        if not data:
            return {}

        honeypot = data.get("is_honeypot", None)
        buy_tax = float(data.get("buy_tax", 0) or 0)
        sell_tax = float(data.get("sell_tax", 0) or 0)
        max_tax = max(buy_tax, sell_tax) * 100  # convert to percent

        return {
            "goplus_honeypot": 1.0 if str(honeypot) == "1" else 0.0,
            "goplus_tax_pct": max_tax,
        }

    async def _fetch_rugcheck(self, ca: str) -> dict[str, float]:
        """Rugcheck.xyz — rug pull risk score"""
        client = await self._get_client()

        resp = await client.get(f"https://api.rugcheck.xyz/v1/tokens/{ca}/report")
        resp.raise_for_status()
        data = resp.json()

        score = data.get("score", 0)

        # rugcheck score -> 0-100 normalized
        # lower = safer, higher = riskier
        normalized = min(max(score, 0), 100)

        return {
            "rugcheck_score": normalized,
        }

    async def _fetch_jupiter(self, ca: str) -> dict[str, float]:
        """Jupiter Verified Token List check"""
        client = await self._get_client()

        # Jupiter strict list
        resp = await client.get("https://token.jup.ag/strict")
        resp.raise_for_status()
        tokens = resp.json()

        is_verified = any(t.get("address") == ca for t in tokens)

        return {
            "jupiter_verified": 1.0 if is_verified else 0.0,
        }

    async def _fetch_coingecko(self, ca: str) -> dict[str, float]:
        """CoinGecko — market cap, volume"""
        client = await self._get_client()

        resp = await client.get(
            f"https://api.coingecko.com/api/v3/coins/solana/contract/{ca}"
        )

        if resp.status_code == 404:
            return {"coingecko_listed": 0.0}

        resp.raise_for_status()
        data = resp.json()

        market_data = data.get("market_data", {})
        mcap = market_data.get("market_cap", {}).get("usd", 0)
        volume = market_data.get("total_volume", {}).get("usd", 0)

        result = {"coingecko_listed": 1.0}

        if mcap:
            result["market_cap_usd"] = mcap
        if volume:
            result["volume_24h"] = volume

        return result

    async def _fetch_birdeye(self, ca: str) -> dict[str, float]:
        """Birdeye — trading metrics"""
        client = await self._get_client()

        # NOTE: Birdeye API key may be required
        resp = await client.get(
            f"https://public-api.birdeye.so/defi/token_overview",
            params={"address": ca},
            headers={"x-chain": "solana"},
        )

        if resp.status_code != 200:
            return {}

        data = resp.json().get("data", {})

        result = {}

        trade_24h = data.get("trade24h", 0)
        if trade_24h:
            result["birdeye_trade_count_24h"] = trade_24h

        unique_wallet = data.get("uniqueWallet24h", 0)
        if unique_wallet:
            result["birdeye_unique_wallets_24h"] = unique_wallet

        liquidity = data.get("liquidity", 0)
        if liquidity:
            result["liquidity_usd"] = liquidity

        mcap = data.get("mc", 0)
        if mcap and liquidity:
            result["liq_mcap_ratio"] = liquidity / mcap if mcap > 0 else 0

        buy_24h = data.get("buy24h", 0)
        sell_24h = data.get("sell24h", 0)
        if sell_24h > 0:
            result["buy_sell_ratio_24h"] = buy_24h / sell_24h

        return result

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
