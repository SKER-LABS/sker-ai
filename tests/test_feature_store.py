"""Tests for Feature Store"""
import numpy as np
import pytest
from engine.core.feature_store import FeatureStore, FEATURE_NAMES


def test_feature_count():
    assert len(FEATURE_NAMES) == 38


def test_set_and_get():
    store = FeatureStore(ca="test_ca")
    store.set("market_cap_usd", 1000000)
    assert store.get("market_cap_usd") == 1000000


def test_bulk_set():
    store = FeatureStore(ca="test_ca")
    store.bulk_set({"market_cap_usd": 500000, "liquidity_usd": 50000})
    assert store.get("market_cap_usd") == 500000
    assert store.get("liquidity_usd") == 50000


def test_fill_rate():
    store = FeatureStore(ca="test_ca")
    assert store.fill_rate == 0.0
    store.set("market_cap_usd", 100)
    assert store.fill_rate > 0


def test_normalize_nan_fill():
    store = FeatureStore(ca="test_ca")
    vec = store.normalize()
    assert not np.any(np.isnan(vec))
    assert np.allclose(vec, 0.5)


def test_missing_features():
    store = FeatureStore(ca="test_ca")
    assert len(store.missing_features) == 38
    store.set("market_cap_usd", 100)
    assert len(store.missing_features) == 37


def test_to_dict():
    store = FeatureStore(ca="test_ca")
    store.set("market_cap_usd", 100)
    d = store.to_dict()
    assert d["ca"] == "test_ca"
    assert d["features"]["market_cap_usd"] is not None
