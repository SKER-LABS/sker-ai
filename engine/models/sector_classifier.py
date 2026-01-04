"""
Token Sector Classifier
Classifies tokens into sector categories

Sectors:
0: unknown
1: meme
2: defi
3: gaming
4: nft_related
5: infrastructure
6: ai_ml
7: social
8: rwa
9: governance
10: stablecoin

v2: keyword-based -> TF-IDF + simple rule hybrid
"""

from __future__ import annotations

import re
from typing import Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class SectorResult:
    code: int
    label: str
    confidence: float
    matched_keywords: list[str]


SECTORS = {
    0: "unknown",
    1: "meme",
    2: "defi",
    3: "gaming",
    4: "nft_related",
    5: "infrastructure",
    6: "ai_ml",
    7: "social",
    8: "rwa",
    9: "governance",
    10: "stablecoin",
}

# sector keywords with weights
# (keyword, weight) tuples
_SECTOR_KEYWORDS: dict[int, list[tuple[str, float]]] = {
    1: [  # meme
        ("meme", 2.0), ("doge", 1.5), ("pepe", 1.5), ("shib", 1.5),
        ("moon", 1.0), ("inu", 1.5), ("cat", 0.8), ("dog", 0.8),
        ("frog", 1.0), ("wojak", 1.5), ("chad", 1.0), ("based", 0.8),
        ("bonk", 1.5), ("wif", 1.5), ("popcat", 1.5), ("boden", 1.0),
        ("trump", 1.0), ("elon", 1.0),
    ],
    2: [  # defi
        ("swap", 1.5), ("lend", 1.5), ("yield", 1.5), ("vault", 1.5),
        ("stake", 1.2), ("liquidity", 1.5), ("amm", 2.0), ("dex", 2.0),
        ("borrow", 1.5), ("margin", 1.5), ("perp", 1.5), ("leverage", 1.2),
        ("farm", 1.2), ("pool", 1.0), ("protocol", 0.8), ("finance", 1.0),
    ],
    3: [  # gaming
        ("game", 1.5), ("play", 1.0), ("nft", 0.5), ("metaverse", 1.5),
        ("quest", 1.2), ("rpg", 2.0), ("battle", 1.2), ("arena", 1.0),
        ("guild", 1.5), ("loot", 1.0), ("craft", 1.0), ("pixel", 1.0),
    ],
    5: [  # infrastructure
        ("bridge", 1.5), ("oracle", 2.0), ("layer", 1.5), ("chain", 1.0),
        ("validator", 2.0), ("node", 1.2), ("rpc", 2.0), ("sdk", 1.5),
        ("network", 0.8), ("protocol", 0.8), ("infra", 2.0),
    ],
    6: [  # ai/ml
        ("ai", 2.0), ("gpt", 1.5), ("llm", 2.0), ("neural", 2.0),
        ("machine", 1.0), ("learn", 0.8), ("model", 0.8), ("agent", 1.5),
        ("compute", 1.5), ("gpu", 1.5), ("inference", 2.0), ("train", 1.0),
        ("cognitive", 1.5), ("intelligence", 1.5),
    ],
    10: [  # stablecoin
        ("usd", 2.0), ("stable", 2.0), ("peg", 2.0), ("dollar", 1.5),
        ("usdc", 2.0), ("usdt", 2.0), ("dai", 2.0),
    ],
}


class SectorClassifier:
    """Keyword weighted-sum sector classifier"""

    def classify(
        self,
        name: str,
        symbol: str,
        description: str = "",
        twitter_bio: str = "",
    ) -> SectorResult:
        """Classify token sector based on metadata"""
        # combine input text
        text = f"{name} {symbol} {description} {twitter_bio}".lower()
        words = set(re.findall(r'[a-z0-9]+', text))

        best_sector = 0
        best_score = 0.0
        best_keywords: list[str] = []

        for sector_code, keywords in _SECTOR_KEYWORDS.items():
            score = 0.0
            matched = []

            for keyword, weight in keywords:
                if keyword in words or keyword in text:
                    score += weight
                    matched.append(keyword)

            if score > best_score:
                best_score = score
                best_sector = sector_code
                best_keywords = matched

        # below minimum threshold = unknown
        # FIXME: tighten threshold — current false positive rate is a bit high
        if best_score < 1.5:
            return SectorResult(code=0, label="unknown", confidence=0.0, matched_keywords=[])

        # confidence: based on match score (0-1)
        confidence = min(best_score / 5.0, 1.0)

        label = SECTORS.get(best_sector, "unknown")
        logger.debug(f"Sector classified: {label} (score={best_score:.1f}, keywords={best_keywords})")

        return SectorResult(
            code=best_sector,
            label=label,
            confidence=round(confidence, 2),
            matched_keywords=best_keywords,
        )
