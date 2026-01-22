"""Tests for Threat Scorer"""
import numpy as np
import pytest
from engine.core.feature_store import FeatureStore
from engine.core.threat_scorer import ThreatScorer


@pytest.fixture
def scorer():
    return ThreatScorer()


def test_neutral_score(scorer):
    store = FeatureStore(ca="test_ca")
    result = scorer.score(store)
    assert 1.0 <= result.score <= 10.0
    assert result.grade in ("S", "A", "B", "C", "D", "F")


def test_high_risk_honeypot(scorer):
    store = FeatureStore(ca="test_ca")
    store.set("goplus_honeypot", 1.0)
    result = scorer.score(store)
    assert result.score >= 8.0
    assert "HONEYPOT_DETECTED" in result.flags


def test_top1_holder_flag(scorer):
    store = FeatureStore(ca="test_ca")
    store.set("top1_holder_pct", 60.0)
    result = scorer.score(store)
    assert "TOP1_HOLDER_OVER_50PCT" in result.flags


def test_safe_token(scorer):
    store = FeatureStore(ca="test_ca")
    store.set("top1_holder_pct", 5.0)
    store.set("top10_holder_pct", 30.0)
    store.set("jupiter_verified", 1.0)
    store.set("goplus_honeypot", 0.0)
    store.set("lp_locked", 1.0)
    store.set("token_age_days", 365)
    store.set("twitter_account_age_days", 500)
    store.set("github_commits_30d", 50)
    result = scorer.score(store)
    assert result.score < 5.0


def test_confidence_increases_with_data(scorer):
    store = FeatureStore(ca="test_ca")
    r1 = scorer.score(store)
    store.set("market_cap_usd", 1000000)
    store.set("liquidity_usd", 50000)
    store.set("holder_count", 500)
    r2 = scorer.score(store)
    assert r2.confidence > r1.confidence
