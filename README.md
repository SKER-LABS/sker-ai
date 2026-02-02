<div align="center">

<img src="assets/banner.png" alt="SKER Protocol" width="100%" />

# SKER Engine

### Cognitive Threat Analysis System for Solana

**38 data point token threat analysis engine**

[![Website](https://img.shields.io/badge/Website-sker.fun-0a0a0a?style=for-the-badge&logo=google-chrome&logoColor=5eead4)](https://sker.fun/)
[![Twitter](https://img.shields.io/badge/@skerdotfun-000000?style=for-the-badge&logo=x&logoColor=white)](https://x.com/skerdotfun)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)

</div>

---

## Overview

SKER Engine performs real-time threat analysis on Solana tokens. It collects on-chain data, OSINT intelligence, and external security API results in parallel, normalizes 38 features, and produces a quantitative threat score (1-10) via weighted heuristic scoring.

## Architecture

```
Input (Contract Address)
  │
  ├─ NLU Classifier ─── Input routing (CA / wallet / question / chat)
  │
  ├─ On-chain Pipeline ────────→ Helius DAS API
  │                                ├─ Token supply & holder distribution
  │                                ├─ Deployer forensics (age, deploy count, rug history)
  │                                ├─ Bundle detection (multiple buys in same block)
  │                                ├─ LP lock verification
  │                                └─ Sell pressure analysis
  │
  ├─ OSINT Crawler ────────────→ Intelligence Layer
  │                                ├─ Twitter audit (followers, account age, engagement)
  │                                ├─ GitHub depth analysis
  │                                ├─ Telegram group scan
  │                                └─ Scam DB cross-reference
  │
  ├─ Security APIs ────────────→ Verification Layer
  │                                ├─ GoPlus (honeypot detection)
  │                                ├─ Rugcheck (rug score)
  │                                ├─ Jupiter (verified status)
  │                                ├─ CoinGecko (market data)
  │                                └─ Birdeye (trading metrics)
  │
  └─ Feature Store (38 points) → Heuristic Threat Engine
                                     ├─ Weighted scoring (1-10)
                                     ├─ Sector classification
                                     └─ Copycat detection
```

## Project Structure

```
engine/
├── __init__.py
├── config.py                # Engine config (RPC, API keys, scoring weights)
├── requirements.txt         # Dependencies
├── server.py                # FastAPI internal API server
├── core/
│   ├── feature_store.py     # 38-dim feature vector normalization
│   ├── threat_scorer.py     # Weighted heuristic threat scoring v3
│   └── nlu_classifier.py    # NLU input classifier
├── pipeline/
│   ├── onchain.py           # Helius DAS on-chain data ingestion
│   ├── osint.py             # OSINT crawler (Twitter, GitHub, scam DB)
│   ├── security.py          # Security API aggregator (GoPlus, Rugcheck, Jupiter)
│   └── orchestrator.py      # Pipeline orchestrator
├── models/
│   ├── sector_classifier.py # Token sector classification (meme/defi/gaming/nft)
│   └── copycat_detector.py  # Copycat token detection (Levenshtein + Jaro-Winkler)
└── utils/
    ├── cache.py             # LRU in-memory cache (TTL-based)
    └── rate_limiter.py      # Token bucket rate limiter
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Framework | FastAPI + Uvicorn |
| ML | scikit-learn, XGBoost |
| Data | NumPy, Pandas |
| Blockchain | Helius DAS API, Solana RPC |
| Security | GoPlus, Rugcheck, Jupiter, CoinGecko, Birdeye |
| Cache | Redis (production) / In-memory LRU (dev) |
| Task Queue | Celery |

## Getting Started

### Prerequisites

- Python 3.11+
- Solana RPC endpoint (Helius recommended)

### Installation

```bash
git clone https://github.com/SKER-LABS/sker-engine.git
cd sker-engine
pip install -r engine/requirements.txt
```

### Environment Variables

```env
HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
HELIUS_API_KEY=YOUR_KEY
TWITTER_BEARER_TOKEN=...
REDIS_URL=redis://localhost:6379
```

### Run

```bash
# Development
uvicorn engine.server:app --reload --port 8000

# Production
uvicorn engine.server:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Endpoints

```
POST /analyze        # Token threat analysis
POST /classify       # NLU input classification
GET  /health         # Health check
```

## Threat Scoring

Threat score is a weighted sum across 6 categories:

| Category | Weight | Metrics |
|----------|--------|---------|
| Holder Risk | 0.25 | Top holder %, concentration HHI |
| Deployer Risk | 0.20 | Account age, past rug count, deploy patterns |
| LP Risk | 0.20 | Lock status, duration, burn status |
| Security Flags | 0.15 | Honeypot, mint authority, freeze |
| Social Trust | 0.12 | Twitter age, GitHub depth, bot ratio |
| Market Signal | 0.08 | Volume anomalies, sell pressure, bundle ratio |

## Data Partners

<div align="center">

Helius · Jupiter · DexScreener · GoPlus · Rugcheck · CoinGecko · Birdeye · Solana

</div>

## License

Proprietary. All rights reserved.
