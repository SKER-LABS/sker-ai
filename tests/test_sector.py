"""Tests for Sector Classifier"""
import pytest
from engine.models.sector_classifier import SectorClassifier


@pytest.fixture
def classifier():
    return SectorClassifier()


def test_meme_detection(classifier):
    result = classifier.classify("Pepe The Frog", "PEPE", "the ultimate meme coin")
    assert result.label == "meme"


def test_defi_detection(classifier):
    result = classifier.classify("YieldSwap", "YSWAP", "decentralized AMM protocol")
    assert result.label == "defi"


def test_unknown_fallback(classifier):
    result = classifier.classify("Mystery", "MST", "")
    assert result.label == "unknown"


def test_ai_sector(classifier):
    result = classifier.classify("NeuralNet", "NNET", "AI inference compute network")
    assert result.label == "ai_ml"


def test_gaming_sector(classifier):
    result = classifier.classify("QuestArena", "QUEST", "blockchain RPG battle game")
    assert result.label == "gaming"
