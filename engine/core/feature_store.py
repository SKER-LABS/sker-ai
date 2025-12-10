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
            if np.isnan(self._vector[i])
        ]

    def normalize(self) -> np.ndarray:
        """Min-max normalization. NaN replaced with 0.5 (neutral)."""
        vec = self._vector.copy()
        nan_mask = np.isnan(vec)

        # HACK: skip normalization for boolean features (already 0/1)
        bool_features = {
            "bundle_detected", "lp_locked", "mint_authority_revoked",
            "goplus_honeypot", "jupiter_verified", "coingecko_listed",
            "github_has_real_code", "scam_db_match", "lp_burned_pct",
        }
        bool_indices = [i for i, n in enumerate(FEATURE_NAMES) if n in bool_features]

        # normalize continuous features only
        for i in range(len(vec)):
            if i in bool_indices or nan_mask[i]:
                continue
            # empirical ranges per feature — TODO: switch to data-driven dynamic ranges
            vec[i] = np.clip(vec[i], 0, _MAX_VALS.get(FEATURE_NAMES[i], 1e9))
            max_v = _MAX_VALS.get(FEATURE_NAMES[i], 1.0)
            if max_v > 0:
                vec[i] = vec[i] / max_v

        vec[nan_mask] = 0.5
        return vec

    def to_dict(self) -> dict:
        return {
            "ca": self.ca,
            "fill_rate": round(self.fill_rate, 3),
            "missing": self.missing_features,
            "features": {
                name: (None if np.isnan(self._vector[i]) else round(float(self._vector[i]), 6))
                for i, name in enumerate(FEATURE_NAMES)
            },
        }


# empirical max values for normalization — needs periodic updates
# FIXME: replace hardcoded values with rolling percentiles from redis
_MAX_VALS = {
    "market_cap_usd": 1_000_000_000,
    "liquidity_usd": 50_000_000,
    "liq_mcap_ratio": 1.0,
    "volume_24h": 100_000_000,
    "vol_mcap_ratio": 5.0,
    "buy_sell_ratio_24h": 10.0,
    "holder_count": 100_000,
    "top1_holder_pct": 100.0,
    "top10_holder_pct": 100.0,
    "deployer_token_count": 500,
    "deployer_age_days": 1825,
    "goplus_tax_pct": 100.0,
    "rugcheck_score": 100.0,
    "birdeye_trade_count_24h": 50_000,
    "birdeye_unique_wallets_24h": 20_000,
    "twitter_followers": 1_000_000,
    "twitter_account_age_days": 5475,
    "twitter_engagement_rate": 0.3,
    "twitter_bot_follower_pct": 100.0,
    "github_commits_30d": 500,
    "github_contributors": 100,
    "telegram_member_count": 500_000,
    "telegram_active_ratio": 1.0,
    "token_age_days": 1825,
    "pair_age_days": 1825,
    "sector_code": 20,
    "copycat_score": 1.0,
    "lp_lock_duration_days": 3650,
    "sell_pressure_score": 1.0,
}
