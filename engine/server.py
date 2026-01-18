"""
CTAS Engine FastAPI Server
Internal service called from frontend API routes

Endpoints:
- POST /analyze — token threat analysis
- POST /classify — NLU input classification
- GET /health — health check
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from loguru import logger

from .pipeline.orchestrator import AnalysisOrchestrator


orchestrator: AnalysisOrchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator
    orchestrator = AnalysisOrchestrator()
    logger.info("CTAS engine initialized")
    yield
    if orchestrator:
        await orchestrator.close()
    logger.info("CTAS engine shutdown")


app = FastAPI(
    title="SKER CTAS Engine",
    version="0.3.0",
    lifespan=lifespan,
)


class AnalyzeRequest(BaseModel):
    ca: str
    force_refresh: bool = False


class ClassifyRequest(BaseModel):
    text: str


@app.post("/analyze")
async def analyze_token(req: AnalyzeRequest):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Engine initializing")

    if len(req.ca) < 32 or len(req.ca) > 44:
        raise HTTPException(status_code=400, detail="Invalid CA")

    try:
        report = await orchestrator.analyze(req.ca, force_refresh=req.force_refresh)
        return {
            "success": True,
            "data": {
                "ca": report.ca,
                "score": report.threat.score,
                "grade": report.threat.grade,
                "breakdown": report.threat.breakdown,
                "flags": report.threat.flags,
                "confidence": report.threat.confidence,
                "features": report.features,
                "timing_ms": report.timing_ms,
                "cached": report.cached,
            },
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis error")


@app.post("/classify")
async def classify_input(req: ClassifyRequest):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Engine initializing")

    result = orchestrator.classifier.classify(req.text)
    return {
        "type": result.input_type.value,
        "confidence": result.confidence,
        "address": result.extracted_address,
        "keywords": result.detected_keywords,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.3.0"}
