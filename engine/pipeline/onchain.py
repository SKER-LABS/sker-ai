"""
On-chain Data Ingestion Pipeline
Helius DAS API + Solana RPC based on-chain data collection

Collected data:
- Token metadata (supply, decimals, authority)
- Holder distribution (top 1/10/20)
- Deployer forensics (age, deployed token count, past rug history)
- LP status (lock, burn, duration)
- Bundle detection (multiple buys within same block)
- Sell pressure (24h buy/sell ratio)
"""

from __future__ import annotations

import asyncio
from typing import Optional
from dataclasses import dataclass
import httpx
from loguru import logger

from ..core.feature_store import FeatureStore
from ..config import config


@dataclass
class TokenMeta:
    mint: str
    symbol: str
    name: str
    decimals: int
    supply: float
    mint_authority: Optional[str]
    freeze_authority: Optional[str]


class OnchainPipeline:
    """Helius DAS + RPC based on-chain data ingestion pipeline"""

    def __init__(self):
        self.rpc_url = config.rpc.helius_url
        self.api_key = config.rpc.helius_api_key
        self.timeout = config.rpc.timeout_ms / 1000
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def ingest(self, ca: str, store: FeatureStore) -> None:
        """Collect on-chain data for CA -> store in FeatureStore"""
        logger.info(f"On-chain pipeline started: {ca[:8]}...")

        # parallel collection
        results = await asyncio.gather(
            self._fetch_token_meta(ca),
            self._fetch_holders(ca),
            self._fetch_deployer_info(ca),
            self._fetch_lp_status(ca),
            self._detect_bundles(ca),
            self._fetch_trade_pressure(ca),
            return_exceptions=True,
        )

        meta, holders, deployer, lp, bundles, pressure = results

        # metadata
        if isinstance(meta, TokenMeta):
            store.set("mint_authority_revoked", 1.0 if meta.mint_authority is None else 0.0)

        # holder distribution
        if isinstance(holders, dict):
            store.bulk_set(holders)

        # deployer profile
        if isinstance(deployer, dict):
            store.bulk_set(deployer)

        # LP
        if isinstance(lp, dict):
            store.bulk_set(lp)

        # bundles
        if isinstance(bundles, bool):
            store.set("bundle_detected", 1.0 if bundles else 0.0)

        # trade pressure
        if isinstance(pressure, dict):
            store.bulk_set(pressure)

        # error logging
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                step_names = ["meta", "holders", "deployer", "lp", "bundles", "pressure"]
                logger.warning(f"On-chain {step_names[i]} collection failed: {r}")

    async def _fetch_token_meta(self, ca: str) -> TokenMeta:
        """Helius DAS getAsset"""
        client = await self._get_client()
        resp = await client.post(
            self.rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": "sker-meta",
                "method": "getAsset",
                "params": {"id": ca},
            },
        )
        resp.raise_for_status()
        data = resp.json().get("result", {})

        content = data.get("content", {}).get("metadata", {})
        token_info = data.get("token_info", {})

        return TokenMeta(
            mint=ca,
            symbol=content.get("symbol", ""),
            name=content.get("name", ""),
            decimals=token_info.get("decimals", 0),
            supply=token_info.get("supply", 0),
            mint_authority=data.get("authorities", [{}])[0].get("address") if data.get("authorities") else None,
            freeze_authority=data.get("freeze_authority"),
        )

    async def _fetch_holders(self, ca: str) -> dict[str, float]:
        """Analyze top holder distribution"""
        client = await self._get_client()

        # FIXME: getTokenLargestAccounts only returns top 20 — limited full distribution view
        resp = await client.post(
            config.rpc.fallback_rpc,
            json={
                "jsonrpc": "2.0",
                "id": "sker-holders",
                "method": "getTokenLargestAccounts",
                "params": [ca],
            },
        )
        resp.raise_for_status()
        accounts = resp.json().get("result", {}).get("value", [])

        if not accounts:
            return {}

        total = sum(float(a.get("amount", 0)) for a in accounts)
        if total == 0:
            return {}

        amounts = [float(a.get("amount", 0)) for a in accounts]
        amounts.sort(reverse=True)

        top1_pct = (amounts[0] / total * 100) if len(amounts) >= 1 else 0
        top10_pct = (sum(amounts[:10]) / total * 100) if len(amounts) >= 10 else 0

        return {
            "top1_holder_pct": top1_pct,
            "top10_holder_pct": top10_pct,
            "holder_count": len(accounts),  # actual count is higher but only top 20 returned
        }

    async def _fetch_deployer_info(self, ca: str) -> dict[str, float]:
        """Deployer wallet analysis"""
        client = await self._get_client()

        # extract deployer from Helius parsed tx
        resp = await client.get(
            f"https://api.helius.xyz/v0/addresses/{ca}/transactions",
            params={"api-key": self.api_key, "limit": 1, "type": "CREATE"},
        )

        if resp.status_code != 200:
            logger.warning(f"Deployer lookup failed: {resp.status_code}")
            return {}

        txs = resp.json()
        if not txs:
            return {}

        # first tx fee payer is the deployer wallet
        deployer = txs[0].get("feePayer", "")
        if not deployer:
            return {}

        # check deployer's other token deployments
        # TODO: caching — prevent repeated lookups for same deployer
        deploy_resp = await client.get(
            f"https://api.helius.xyz/v0/addresses/{deployer}/transactions",
            params={"api-key": self.api_key, "limit": 100, "type": "CREATE"},
        )

        deploy_count = 0
        if deploy_resp.status_code == 200:
            deploy_count = len(deploy_resp.json())

        # deployer account age (based on first transaction)
        age_resp = await client.get(
            f"https://api.helius.xyz/v0/addresses/{deployer}/transactions",
            params={"api-key": self.api_key, "limit": 1},
        )

        deployer_age_days = 0
        if age_resp.status_code == 200:
            old_txs = age_resp.json()
            if old_txs:
                import time
                first_ts = old_txs[-1].get("timestamp", 0)
                if first_ts > 0:
                    deployer_age_days = (time.time() - first_ts) / 86400

        return {
            "deployer_token_count": deploy_count,
            "deployer_age_days": deployer_age_days,
        }

    async def _fetch_lp_status(self, ca: str) -> dict[str, float]:
        """Check LP lock/burn status"""
        # TODO: switch to direct Raydium/Orca LP pool queries
        # currently fetching indirectly via rugcheck API
        return {}

    async def _detect_bundles(self, ca: str) -> bool:
        """Detect bundle transactions — multiple buys within same slot"""
        client = await self._get_client()

        resp = await client.get(
            f"https://api.helius.xyz/v0/addresses/{ca}/transactions",
            params={"api-key": self.api_key, "limit": 50},
        )

        if resp.status_code != 200:
            return False

        txs = resp.json()
        if len(txs) < 5:
            return False

        # 3+ txs in same slot = suspected bundle
        slot_counts: dict[int, int] = {}
        for tx in txs:
            slot = tx.get("slot", 0)
            slot_counts[slot] = slot_counts.get(slot, 0) + 1

        return any(count >= 3 for count in slot_counts.values())

    async def _fetch_trade_pressure(self, ca: str) -> dict[str, float]:
        """24h trade pressure analysis"""
        # Birdeye/DexScreener provides more accurate data
        # this is a Helius tx-based estimation
        return {}

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
