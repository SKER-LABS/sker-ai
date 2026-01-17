"""
CTAS Engine FastAPI Server
Internal service called from frontend API routes
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="SKER CTAS Engine",
    version="0.3.0",
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.3.0"}
