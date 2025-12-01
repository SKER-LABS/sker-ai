"""
Feature Store — 38 data point normalization and storage
Transforms on-chain + OSINT + security API data into unified feature vectors
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger


# feature index — changing order will break model compatibility
FEATURE_NAMES = [
    # on-chain (0-11)
    "market_cap_usd",
    "liquidity_usd",
    "liq_mcap_ratio",
    "volume_24h",
    "vol_mcap_ratio",
    "buy_sell_ratio_24h",
    "holder_count",
    "top1_holder_pct",
    "top10_holder_pct",
    "deployer_token_count",
    "deployer_age_days",
    "bundle_detected",
    # liquidity (12-16)
    "lp_locked",
    "lp_lock_duration_days",
    "lp_burned_pct",
    "sell_pressure_score",
    "mint_authority_revoked",
    # security api (17-23)
    "goplus_honeypot",
    "goplus_tax_pct",
    "rugcheck_score",
    "jupiter_verified",
    "birdeye_trade_count_24h",
    "birdeye_unique_wallets_24h",
    "coingecko_listed",
    # social / osint (24-33)
    "twitter_followers",
    "twitter_account_age_days",
    "twitter_engagement_rate",
    "twitter_bot_follower_pct",
    "github_commits_30d",
    "github_contributors",
    "github_has_real_code",
    "telegram_member_count",
    "telegram_active_ratio",
    "scam_db_match",
    # meta (34-37)
    "token_age_days",
    "pair_age_days",
    "sector_code",
    "copycat_score",
]

assert len(FEATURE_NAMES) == 38, f"Feature count mismatch: {len(FEATURE_NAMES)}"


@dataclass
class FeatureStore:
    """Manages 38-dim feature vector. Each pipeline stage fills via set()."""

    ca: str
    _vector: np.ndarray = field(default_factory=lambda: np.full(38, np.nan))
    _filled: set = field(default_factory=set)

    def set(self, name: str, value: float) -> None:
        idx = FEATURE_NAMES.index(name)
        self._vector[idx] = value
        self._filled.add(name)

    def get(self, name: str) -> float:
        idx = FEATURE_NAMES.index(name)
        return self._vector[idx]

    def bulk_set(self, data: dict[str, float]) -> None:
        for k, v in data.items():
            if k in FEATURE_NAMES:
                self.set(k, v)
            else:
                logger.warning(f"Unknown feature ignored: {k}")

    @property
    def vector(self) -> np.ndarray:
        return self._vector.copy()

    @property
    def fill_rate(self) -> float:
        filled = np.count_nonzero(~np.isnan(self._vector))
        return filled / len(FEATURE_NAMES)

    @property
    def missing_features(self) -> list[str]:
        return [
            name for i, name in enumerate(FEATURE_NAMES)
