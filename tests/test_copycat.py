"""Tests for Copycat Detector"""
import pytest
from engine.models.copycat_detector import CopycatDetector


@pytest.fixture
def detector():
    return CopycatDetector()


def test_exact_match_not_copycat(detector):
    result = detector.detect("Bonk", "BONK")
    assert not result.is_copycat


def test_baby_prefix_copycat(detector):
    result = detector.detect("BabyBonk", "BBONK")
    assert result.score > 0.5


def test_completely_different(detector):
    result = detector.detect("RandomToken", "RND")
    assert not result.is_copycat
    assert result.score < 0.3


def test_suffix_variant(detector):
    result = detector.detect("SolanaV2", "SOLV2")
    assert result.score > 0.4


def test_string_similarity(detector):
    assert detector._string_similarity("bonk", "bonk") == 1.0
    assert detector._string_similarity("bonk", "bink") > 0.5
    assert detector._string_similarity("abc", "xyz") < 0.5
