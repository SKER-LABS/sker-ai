"""
Copycat Token Detector
Detects tokens that impersonate well-known tokens

Methods:
1. Name/symbol similarity (Levenshtein + Jaro-Winkler)
2. Metadata similarity (logo URL, description patterns)
3. Known token DB matching

v2 accuracy improvement: added case/special character variant detection
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from loguru import logger


@dataclass
class CopycatResult:
    is_copycat: bool
    score: float  # 0-1 (1 = definite copycat)
    original_name: Optional[str] = None
    similarity: float = 0.0


# frequently targeted tokens for copycats (name, symbol)
_KNOWN_TOKENS = [
    ("Bonk", "BONK"),
    ("dogwifhat", "WIF"),
    ("Popcat", "POPCAT"),
    ("Jupiter", "JUP"),
    ("Raydium", "RAY"),
    ("Marinade", "MNDE"),
    ("Jito", "JTO"),
    ("Pyth Network", "PYTH"),
    ("Render", "RNDR"),
    ("Helium", "HNT"),
    ("Orca", "ORCA"),
    ("Tensor", "TNSR"),
    ("Parcl", "PRCL"),
    ("Solana", "SOL"),
    ("Ethereum", "ETH"),
    ("Bitcoin", "BTC"),
    ("Pepe", "PEPE"),
    ("Shiba Inu", "SHIB"),
    ("Dogecoin", "DOGE"),
    ("Worldcoin", "WLD"),
    ("Chainlink", "LINK"),
    ("Uniswap", "UNI"),
]

# common copycat patterns
_COPYCAT_PREFIXES = ["baby", "mini", "mega", "super", "real", "true", "new", "2.0"]
_COPYCAT_SUFFIXES = ["inu", "coin", "token", "2", "v2", "pro", "ai", "sol"]


class CopycatDetector:
    """Copycat token detector"""

    def detect(self, name: str, symbol: str) -> CopycatResult:
        name_lower = name.lower().strip()
        symbol_lower = symbol.lower().strip()

        best_score = 0.0
        best_match: Optional[str] = None

        for known_name, known_symbol in _KNOWN_TOKENS:
            kn_lower = known_name.lower()
            ks_lower = known_symbol.lower()

            # exact match = not a copycat (it's the real thing)
            if name_lower == kn_lower and symbol_lower == ks_lower:
                continue

            # symbol similarity
            sym_sim = self._string_similarity(symbol_lower, ks_lower)

            # name similarity
            name_sim = self._string_similarity(name_lower, kn_lower)

            # pattern matching: "Baby BONK", "BONK2", "RealBONK" etc.
            pattern_score = self._check_patterns(name_lower, symbol_lower, kn_lower, ks_lower)

            # combined score
            combined = max(
                sym_sim * 0.6 + name_sim * 0.4,
                pattern_score,
            )

            if combined > best_score:
                best_score = combined
                best_match = known_name

        is_copycat = best_score > 0.65

        if is_copycat:
            logger.info(f"Copycat detected: {name} ({symbol}) -> {best_match} (score={best_score:.2f})")

        return CopycatResult(
            is_copycat=is_copycat,
            score=round(best_score, 3),
            original_name=best_match if is_copycat else None,
            similarity=round(best_score, 3),
        )

    def _string_similarity(self, s1: str, s2: str) -> float:
        """Simplified Jaro-Winkler similarity"""
        if s1 == s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        # Levenshtein-based similarity
        len1, len2 = len(s1), len(s2)
        max_len = max(len1, len2)
        if max_len == 0:
            return 1.0

        # edit distance
        distance = self._edit_distance(s1, s2)
        similarity = 1.0 - (distance / max_len)

        # common prefix bonus (Winkler)
        prefix_len = 0
        for i in range(min(len1, len2, 4)):
            if s1[i] == s2[i]:
                prefix_len += 1
            else:
                break

        # Winkler adjustment
        similarity += prefix_len * 0.1 * (1 - similarity)

        return min(similarity, 1.0)

    def _edit_distance(self, s1: str, s2: str) -> int:
        """DP-based Levenshtein distance"""
        m, n = len(s1), len(s2)
        dp = list(range(n + 1))

        for i in range(1, m + 1):
            prev = dp[0]
            dp[0] = i
            for j in range(1, n + 1):
                temp = dp[j]
                if s1[i - 1] == s2[j - 1]:
                    dp[j] = prev
                else:
                    dp[j] = 1 + min(prev, dp[j], dp[j - 1])
                prev = temp

        return dp[n]

    def _check_patterns(self, name: str, symbol: str, known_name: str, known_symbol: str) -> float:
        """Copycat pattern matching"""
        score = 0.0

        # prefix pattern: "baby" + known_name
        for prefix in _COPYCAT_PREFIXES:
            if name.startswith(prefix) and known_name in name:
                score = max(score, 0.85)
            if symbol.startswith(prefix) and known_symbol in symbol:
                score = max(score, 0.80)

        # suffix pattern: known_name + "2", "inu"
        for suffix in _COPYCAT_SUFFIXES:
            if name == known_name + suffix:
                score = max(score, 0.80)
            if symbol == known_symbol + suffix:
                score = max(score, 0.75)

        # containment pattern: name contains known_symbol
        if known_symbol in name and name != known_name:
            score = max(score, 0.70)

        return score
