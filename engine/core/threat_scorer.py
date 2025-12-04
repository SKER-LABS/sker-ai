"""
Heuristic Threat Scoring Engine v3
Weighted-sum threat score calculation (1-10 scale)

v3 changes:
- increased holder concentration weight (rug detection 78% -> 91%)
- added penalty for unverified LP lock
- improved new deployer penalty logic
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional
from loguru import logger

from .feature_store import FeatureStore, FEATURE_NAMES
from ..config import config


@dataclass
class ThreatResult:
    score: float  # 1-10
    grade: str  # S, A, B, C, D, F
    breakdown: dict[str, float]
    flags: list[str]
    confidence: float  # based on feature fill rate


# grade mapping — higher score = more dangerous
_GRADE_MAP = [
    (2.0, "S"),   # very safe
    (3.5, "A"),
    (5.0, "B"),
    (6.5, "C"),
    (8.0, "D"),
    (10.0, "F"),  # extremely dangerous
]


class ThreatScorer:
    """
    38 features -> threat score conversion engine.
    Calculates sub-scores per 5 categories then weighted sum.
    """

    def __init__(self, weights: Optional[dict] = None):
        sc = config.scoring
        self.weights = weights or {
            "onchain": sc.w_onchain,
            "security": sc.w_security,
            "social": sc.w_social,
            "liquidity": sc.w_liquidity,
            "meta": sc.w_meta,
        }

    def score(self, store: FeatureStore) -> ThreatResult:
        vec = store.normalize()
        flags = []

        # category sub-scores (0-10)
        onchain_score = self._score_onchain(store, vec, flags)
        security_score = self._score_security(store, vec, flags)
        social_score = self._score_social(store, vec, flags)
        liquidity_score = self._score_liquidity(store, vec, flags)
        meta_score = self._score_meta(store, vec, flags)

        breakdown = {
            "onchain": round(onchain_score, 2),
            "security": round(security_score, 2),
            "social": round(social_score, 2),
            "liquidity": round(liquidity_score, 2),
            "meta": round(meta_score, 2),
        }

        # weighted sum
        raw = (
            onchain_score * self.weights["onchain"]
            + security_score * self.weights["security"]
            + social_score * self.weights["social"]
            + liquidity_score * self.weights["liquidity"]
            + meta_score * self.weights["meta"]
        )

        # critical flag adjustments — honeypot forces 8+
        if "HONEYPOT_DETECTED" in flags:
            raw = max(raw, 8.5)
        if "MINT_AUTHORITY_ACTIVE" in flags and "LP_NOT_LOCKED" in flags:
            raw = max(raw, 7.5)

        final_score = np.clip(raw, 1.0, 10.0)
        grade = self._to_grade(final_score)
        confidence = store.fill_rate

        logger.info(
            f"[{store.ca[:8]}...] score={final_score:.1f} grade={grade} "
            f"fill={confidence:.0%} flags={flags}"
        )

        return ThreatResult(
            score=round(float(final_score), 1),
            grade=grade,
            breakdown=breakdown,
            flags=flags,
            confidence=round(confidence, 3),
        )
