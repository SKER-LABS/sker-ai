"""
NLU Input Classifier
Routes user input to the appropriate pipeline

Classification categories:
- CA_SCAN: Solana contract address detected -> on-chain pipeline
- WALLET_CHECK: Wallet address / analysis request
- CRYPTO_QUESTION: General crypto-related question
- GENERAL_CHAT: Casual conversation
- SNIPER_CONFIG: Sniper configuration related
"""

from __future__ import annotations

import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from loguru import logger


class InputType(Enum):
    CA_SCAN = "ca_scan"
    WALLET_CHECK = "wallet_check"
    CRYPTO_QUESTION = "crypto_question"
    GENERAL_CHAT = "general_chat"
    SNIPER_CONFIG = "sniper_config"


@dataclass
class ClassificationResult:
    input_type: InputType
    confidence: float
    extracted_address: Optional[str] = None
    detected_keywords: list[str] = None

    def __post_init__(self):
        if self.detected_keywords is None:
            self.detected_keywords = []


# base58 — solana address/tx pattern
_SOL_ADDR_PATTERN = re.compile(r'[1-9A-HJ-NP-Za-km-z]{32,44}')

# pump.fun CA pattern (always ends with pump suffix)
_PUMP_CA_PATTERN = re.compile(r'[1-9A-HJ-NP-Za-km-z]{30,44}pump')

# keyword dictionaries
_SCAN_KEYWORDS = {"scan", "check", "analyze", "analysis", "rug", "scam", "safe", "audit", "report", "inspect"}
_WALLET_KEYWORDS = {"wallet", "balance", "portfolio", "holdings", "address"}
_SNIPER_KEYWORDS = {"sniper", "alert", "filter", "monitor", "notify", "watch"}

# crypto domain keywords
_CRYPTO_KEYWORDS = {
    "bitcoin", "ethereum", "solana", "token", "defi", "airdrop",
    "staking", "liquidity", "minting", "nft", "dex", "cex", "pump",
    "dump", "bullish", "bearish", "chart", "volume", "mcap",
    "blockchain", "gas", "phantom", "raydium", "jupiter",
    "swap", "yield", "farming", "bridge", "validator",
}


class NLUClassifier:
    """Rule-based NLU classifier. Speed-first — <1ms classification without LLM calls."""

    def classify(self, text: str) -> ClassificationResult:
        text_lower = text.lower().strip()

        # priority 1: CA detection (if address present, always scan)
        addr = self._extract_address(text)
        if addr:
            logger.debug(f"CA detected: {addr[:8]}...")
            return ClassificationResult(
                input_type=InputType.CA_SCAN,
                confidence=0.95,
                extracted_address=addr,
            )

        # priority 2: keyword-based classification
        words = set(re.findall(r'[\w]+', text_lower))

        wallet_hits = words & _WALLET_KEYWORDS
        if wallet_hits:
            return ClassificationResult(
                input_type=InputType.WALLET_CHECK,
                confidence=0.85,
                detected_keywords=list(wallet_hits),
            )

        sniper_hits = words & _SNIPER_KEYWORDS
        if sniper_hits:
            return ClassificationResult(
                input_type=InputType.SNIPER_CONFIG,
                confidence=0.80,
                detected_keywords=list(sniper_hits),
            )

        scan_hits = words & _SCAN_KEYWORDS
        crypto_hits = words & _CRYPTO_KEYWORDS

        if scan_hits and crypto_hits:
            return ClassificationResult(
                input_type=InputType.CRYPTO_QUESTION,
                confidence=0.80,
                detected_keywords=list(scan_hits | crypto_hits),
            )

        if crypto_hits:
            return ClassificationResult(
                input_type=InputType.CRYPTO_QUESTION,
                confidence=0.70,
                detected_keywords=list(crypto_hits),
            )

        # fallback
        return ClassificationResult(
            input_type=InputType.GENERAL_CHAT,
            confidence=0.50,
        )

    def _extract_address(self, text: str) -> Optional[str]:
        """Extract Solana address from text. Prioritizes pump.fun CAs."""
        # pump CA first
        pump_match = _PUMP_CA_PATTERN.search(text)
        if pump_match:
            return pump_match.group()

        # standard solana address
        matches = _SOL_ADDR_PATTERN.findall(text)
        if not matches:
            return None

        # return longest match (CAs are typically 43-44 chars)
        # TODO: add base58 checksum validation
        candidates = [m for m in matches if len(m) >= 32]
        if candidates:
            return max(candidates, key=len)

        return None
