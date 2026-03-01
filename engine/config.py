import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class RPCConfig(BaseModel):
    helius_url: str = os.getenv("HELIUS_RPC_URL", "")
    helius_api_key: str = os.getenv("HELIUS_API_KEY", "")
    fallback_rpc: str = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    max_retries: int = 3
    timeout_ms: int = 8000


class OSINTConfig(BaseModel):
    twitter_bearer: str = os.getenv("X_BEARER_TOKEN", "")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    # NOTE: telegram scraper runs as separate process — rate limit concerns
    telegram_api_id: str = os.getenv("TELEGRAM_API_ID", "")
    max_concurrent_crawls: int = 5
    crawl_timeout_sec: int = 15


class ScoringConfig(BaseModel):
    # weights — v3 bumped holder concentration weight (rug detection 78% -> 91%)
    w_onchain: float = 0.35
    w_security: float = 0.25
    w_social: float = 0.20
    w_liquidity: float = 0.15
    w_meta: float = 0.05
    # threshold
    high_risk_threshold: float = 7.0
    medium_risk_threshold: float = 4.0


class RedisConfig(BaseModel):
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cache_ttl_sec: int = 300  # 5min — balance between freshness and API rate limits
    signal_ttl_sec: int = 3600


class EngineConfig(BaseModel):
    rpc: RPCConfig = RPCConfig()
    osint: OSINTConfig = OSINTConfig()
    scoring: ScoringConfig = ScoringConfig()
    redis: RedisConfig = RedisConfig()
    debug: bool = os.getenv("ENGINE_DEBUG", "false").lower() == "true"


config = EngineConfig()
