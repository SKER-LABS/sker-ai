"""Shared test fixtures"""
import pytest
from engine.core.feature_store import FeatureStore
from engine.core.threat_scorer import ThreatScorer
from engine.core.nlu_classifier import NLUClassifier


@pytest.fixture
def empty_store():
    return FeatureStore(ca="test_mint_address_placeholder_00000000000")


@pytest.fixture
def scorer():
    return ThreatScorer()


@pytest.fixture
def nlu():
    return NLUClassifier()
