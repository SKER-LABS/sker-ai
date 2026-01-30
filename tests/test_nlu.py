"""Tests for NLU classifier"""
import pytest
from engine.core.nlu_classifier import NLUClassifier, InputType


@pytest.fixture
def classifier():
    return NLUClassifier()


def test_ca_detection(classifier):
    result = classifier.classify("check 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU")
    assert result.input_type == InputType.CA_SCAN
    assert result.extracted_address is not None
    assert result.confidence >= 0.9


def test_wallet_query(classifier):
    result = classifier.classify("show my wallet balance")
    assert result.input_type == InputType.WALLET_CHECK


def test_crypto_question(classifier):
    result = classifier.classify("what is solana staking yield")
    assert result.input_type == InputType.CRYPTO_QUESTION


def test_general_chat(classifier):
    result = classifier.classify("hello how are you")
    assert result.input_type == InputType.GENERAL_CHAT


def test_pump_ca_priority(classifier):
    result = classifier.classify("scan 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgpump")
    assert result.input_type == InputType.CA_SCAN
    assert "pump" in result.extracted_address
