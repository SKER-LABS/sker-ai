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

    def _score_onchain(self, store: FeatureStore, vec: np.ndarray, flags: list) -> float:
        """On-chain data risk. Holder concentration is the key signal."""
        score = 5.0  # default (neutral when no data)

        top1 = store.get("top1_holder_pct")
        top10 = store.get("top10_holder_pct")

        if not np.isnan(top1):
            # top1 > 50% is high rug pull risk
            if top1 > 50:
                score += 3.5
                flags.append("TOP1_HOLDER_OVER_50PCT")
            elif top1 > 30:
                score += 2.0
                flags.append("TOP1_HOLDER_OVER_30PCT")
            elif top1 > 15:
                score += 0.8

        if not np.isnan(top10):
            if top10 > 80:
                score += 2.0
                flags.append("TOP10_CONCENTRATION_CRITICAL")
            elif top10 > 60:
                score += 1.0

        # bundle detection
        bundle = store.get("bundle_detected")
        if not np.isnan(bundle) and bundle > 0:
            score += 1.5
            flags.append("BUNDLE_DETECTED")

        # deployer profile
        deployer_count = store.get("deployer_token_count")
        deployer_age = store.get("deployer_age_days")

        if not np.isnan(deployer_count) and deployer_count > 10:
            score += 1.0
            flags.append("SERIAL_DEPLOYER")

        if not np.isnan(deployer_age) and deployer_age < 7:
            score += 0.8
            flags.append("NEW_DEPLOYER")

        # buy/sell ratio
        bs_ratio = store.get("buy_sell_ratio_24h")
        if not np.isnan(bs_ratio) and bs_ratio < 0.3:
            score += 1.2
            flags.append("HEAVY_SELL_PRESSURE")

        return np.clip(score, 1.0, 10.0)

    def _score_security(self, store: FeatureStore, vec: np.ndarray, flags: list) -> float:
        """Security API results (GoPlus, Rugcheck, Jupiter)"""
        score = 4.0

        honeypot = store.get("goplus_honeypot")
        if not np.isnan(honeypot) and honeypot > 0:
            score += 5.0
            flags.append("HONEYPOT_DETECTED")

        tax = store.get("goplus_tax_pct")
        if not np.isnan(tax):
            if tax > 10:
                score += 2.5
                flags.append("HIGH_TAX")
            elif tax > 5:
                score += 1.0

        rugcheck = store.get("rugcheck_score")
        if not np.isnan(rugcheck):
            # higher rugcheck score = more dangerous (0-100)
            score += (rugcheck / 100) * 3.0

        jupiter = store.get("jupiter_verified")
        if not np.isnan(jupiter) and jupiter > 0:
            score -= 1.5  # Jupiter verified = risk reduction

        mint = store.get("mint_authority_revoked")
        if not np.isnan(mint) and mint < 1:
            score += 1.5
            flags.append("MINT_AUTHORITY_ACTIVE")

        return np.clip(score, 1.0, 10.0)

    def _score_social(self, store: FeatureStore, vec: np.ndarray, flags: list) -> float:
        """OSINT social trust score"""
        score = 5.0

        followers = store.get("twitter_followers")
        age = store.get("twitter_account_age_days")
        engagement = store.get("twitter_engagement_rate")
        bot_pct = store.get("twitter_bot_follower_pct")

        # follower vs account age — detect rapid follower growth
        if not np.isnan(followers) and not np.isnan(age):
            if age > 0:
                growth_rate = followers / age
                if growth_rate > 500 and age < 90:
                    score += 2.0
                    flags.append("SUSPICIOUS_FOLLOWER_GROWTH")

        if not np.isnan(bot_pct) and bot_pct > 40:
            score += 2.0
            flags.append("HIGH_BOT_FOLLOWERS")

        if not np.isnan(engagement) and engagement < 0.005:
            score += 1.0  # very low engagement = ghost account

        # GitHub
        commits = store.get("github_commits_30d")
        has_code = store.get("github_has_real_code")

        if not np.isnan(has_code) and has_code < 1:
            score += 1.0
            flags.append("NO_REAL_CODE")
        elif not np.isnan(commits) and commits > 20:
            score -= 1.5  # active development = positive signal

        # scam DB
        scam = store.get("scam_db_match")
        if not np.isnan(scam) and scam > 0:
            score += 3.0
            flags.append("SCAM_DB_MATCH")

        return np.clip(score, 1.0, 10.0)

    def _score_liquidity(self, store: FeatureStore, vec: np.ndarray, flags: list) -> float:
        """Liquidity health assessment"""
        score = 4.0

        liq_ratio = store.get("liq_mcap_ratio")
        if not np.isnan(liq_ratio):
            if liq_ratio < 0.03:
                score += 3.0
                flags.append("EXTREMELY_LOW_LIQUIDITY")
            elif liq_ratio < 0.1:
                score += 1.5

        lp_locked = store.get("lp_locked")
        if not np.isnan(lp_locked) and lp_locked < 1:
            score += 2.0
            flags.append("LP_NOT_LOCKED")

        lp_duration = store.get("lp_lock_duration_days")
        if not np.isnan(lp_duration) and lp_duration < 30:
            score += 1.0
            flags.append("SHORT_LP_LOCK")

        sell_pressure = store.get("sell_pressure_score")
        if not np.isnan(sell_pressure) and sell_pressure > 0.7:
            score += 1.5

        vol_ratio = store.get("vol_mcap_ratio")
        if not np.isnan(vol_ratio):
            # abnormal volume — potential wash trading
            if vol_ratio > 3.0:
                score += 1.5
                flags.append("ABNORMAL_VOLUME")

        return np.clip(score, 1.0, 10.0)

    def _score_meta(self, store: FeatureStore, vec: np.ndarray, flags: list) -> float:
        """Meta information (token age, copycat, etc.)"""
        score = 3.0

        token_age = store.get("token_age_days")
        if not np.isnan(token_age):
            if token_age < 1:
                score += 2.5
                flags.append("BRAND_NEW_TOKEN")
            elif token_age < 7:
                score += 1.5
            elif token_age > 180:
                score -= 1.0  # older token = relatively safer

        copycat = store.get("copycat_score")
        if not np.isnan(copycat) and copycat > 0.7:
            score += 2.0
            flags.append("COPYCAT_SUSPECTED")

        return np.clip(score, 1.0, 10.0)

    @staticmethod
    def _to_grade(score: float) -> str:
        for threshold, grade in _GRADE_MAP:
            if score <= threshold:
                return grade
        return "F"
