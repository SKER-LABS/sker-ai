"""Tests for Analysis Orchestrator"""
import pytest
from engine.pipeline.orchestrator import AnalysisOrchestrator


def test_orchestrator_init():
    orch = AnalysisOrchestrator()
    assert orch.classifier is not None
    assert orch.scorer is not None
    assert orch.onchain is not None


def test_cache_miss():
    orch = AnalysisOrchestrator()
    cached = orch._get_cached("nonexistent_ca")
    assert cached is None


def test_cache_set_and_get():
    from engine.pipeline.orchestrator import AnalysisReport
    from engine.core.threat_scorer import ThreatResult
    orch = AnalysisOrchestrator()
    report = AnalysisReport(
        ca="test_ca",
        threat=ThreatResult(score=5.0, grade="B", breakdown={}, flags=[], confidence=0.5),
        features={},
        timing_ms=100,
    )
    orch._set_cache("test_ca", report)
    cached = orch._get_cached("test_ca")
    assert cached is not None
    assert cached.ca == "test_ca"
