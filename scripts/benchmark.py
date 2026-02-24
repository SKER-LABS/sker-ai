"""
Quick benchmark for scoring engine throughput.
Generates random feature vectors and measures score() latency.
"""

import time
import numpy as np
from engine.core.feature_store import FeatureStore, FEATURE_NAMES
from engine.core.threat_scorer import ThreatScorer


def run_benchmark(iterations: int = 1000):
    scorer = ThreatScorer()
    latencies = []

    for _ in range(iterations):
        store = FeatureStore(ca="benchmark_test_ca")
        # fill random features
        for name in FEATURE_NAMES:
            if np.random.random() > 0.3:  # 70% fill rate
                store.set(name, np.random.random() * 100)

        start = time.perf_counter()
        scorer.score(store)
        elapsed = (time.perf_counter() - start) * 1000
        latencies.append(elapsed)

    latencies = np.array(latencies)
    print(f"Iterations: {iterations}")
    print(f"Mean:   {latencies.mean():.3f}ms")
    print(f"Median: {np.median(latencies):.3f}ms")
    print(f"P95:    {np.percentile(latencies, 95):.3f}ms")
    print(f"P99:    {np.percentile(latencies, 99):.3f}ms")
    print(f"Max:    {latencies.max():.3f}ms")


if __name__ == "__main__":
    run_benchmark()
