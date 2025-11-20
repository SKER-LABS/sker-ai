import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class RPCConfig(BaseModel):
    helius_url: str = os.getenv("HELIUS_RPC_URL", "")
    helius_api_key: str = os.getenv("HELIUS_API_KEY", "")
    fallback_rpc: str = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    max_retries: int = 3
    timeout_ms: int = 5000


class EngineConfig(BaseModel):
    rpc: RPCConfig = RPCConfig()
    debug: bool = os.getenv("ENGINE_DEBUG", "false").lower() == "true"


config = EngineConfig()
