"""
Analysis Orchestrator
Controls the full analysis pipeline

Flow:
1. NLU classification -> CA extraction
2. Cache check (5min TTL)
3. Parallel collection: on-chain + OSINT + security APIs
4. Feature Store normalization
5. Threat Scoring
6. Cache result + return
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional
from dataclasses import dataclass
from loguru import logger

from ..core.feature_store import FeatureStore
from ..core.threat_scorer import ThreatScorer, ThreatResult
from ..core.nlu_classifier import NLUClassifier, InputType
from .onchain import OnchainPipeline
from .osint import OSINTCrawler
from .security import SecurityAggregator
from ..config import config


@dataclass
class AnalysisReport:
    ca: str
    threat: ThreatResult
    features: dict
    timing_ms: int
    cached: bool = False


# in-memory cache — TODO: migrate to Redis
_cache: dict[str, tuple[AnalysisReport, float]] = {}


class AnalysisOrchestrator:
    """
    Controls the full analysis pipeline flow.
    Single entry point: analyze(ca) -> AnalysisReport
    """

    def __init__(self):
        self.classifier = NLUClassifier()
        self.onchain = OnchainPipeline()
        self.osint = OSINTCrawler()
        self.security = SecurityAggregator()
        self.scorer = ThreatScorer()

    async def analyze(self, ca: str, force_refresh: bool = False) -> AnalysisReport:
        """Main analysis entry point"""
        start = time.monotonic()

        # cache check
        if not force_refresh:
            cached = self._get_cached(ca)
            if cached:
                logger.info(f"Cache hit: {ca[:8]}...")
                return cached

        logger.info(f"Full analysis started: {ca[:8]}...")

        # initialize Feature Store
        store = FeatureStore(ca=ca)

        # run 3 pipelines in parallel
        # NOTE: OSINT needs token name from on-chain data
        # collect CA-based data first, supplement name after on-chain pipeline completes
        await asyncio.gather(
            self.onchain.ingest(ca, store),
            self.security.aggregate(ca, store),
            return_exceptions=True,
        )

        # OSINT runs after on-chain meta collection (needs token name)
        # TODO: improve parallelization — fetch on-chain meta first, then parallel the rest
        await self.osint.crawl(
            token_name=ca[:8],  # fallback — actually fetched from meta
            token_symbol=ca[:4],
            store=store,
        )

        # scoring
        threat = self.scorer.score(store)

        elapsed = int((time.monotonic() - start) * 1000)

        report = AnalysisReport(
            ca=ca,
            threat=threat,
            features=store.to_dict(),
            timing_ms=elapsed,
        )

        # cache
        self._set_cache(ca, report)

        logger.info(
            f"Analysis complete: {ca[:8]}... "
            f"score={threat.score} grade={threat.grade} "
            f"fill={store.fill_rate:.0%} "
            f"time={elapsed}ms"
        )

        return report

    async def analyze_from_text(self, text: str) -> Optional[AnalysisReport]:
        """Extract CA from user input text and analyze"""
        result = self.classifier.classify(text)

        if result.input_type != InputType.CA_SCAN or not result.extracted_address:
            return None

        return await self.analyze(result.extracted_address)

    def _get_cached(self, ca: str) -> Optional[AnalysisReport]:
        if ca in _cache:
            report, ts = _cache[ca]
            if time.time() - ts < config.redis.cache_ttl_sec:
                report.cached = True
                return report
            else:
                del _cache[ca]
        return None

    def _set_cache(self, ca: str, report: AnalysisReport) -> None:
        _cache[ca] = (report, time.time())
        # cache size limit — prevent memory leak
        if len(_cache) > 500:
            # simple half-eviction instead of LRU — FIXME: implement proper LRU
            oldest_keys = sorted(_cache.keys(), key=lambda k: _cache[k][1])[:250]
            for k in oldest_keys:
                del _cache[k]

    async def close(self):
        await asyncio.gather(
            self.onchain.close(),
            self.osint.close(),
            self.security.close(),
        )
