"""Local single-client measurements; not a production SLA."""

import json
import platform
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import numpy as np
import psutil
import torch

from feedrank.serving import Service

base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
if urlparse(base_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("Benchmark only supports a local development server.")
root = Path(__file__).resolve().parents[1]
s = Service()
history = [i["id"] for i in s.items[:5]]


def measure(fn):
    for _ in range(20):
        fn()
    samples = []
    for _ in range(300):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return {
        "p50_ms": float(np.percentile(samples, 50)),
        "p95_ms": float(np.percentile(samples, 95)),
        "measurements": 300,
    }


result = {
    "platform": platform.platform(),
    "python": platform.python_version(),
    "batch_size": 1,
    "catalog_items": len(s.items),
    "history_length": 5,
    "threads": torch.get_num_threads(),
    "warmup": 20,
    "mode": "research-release" if s.ready else "explicit-demo-fallback",
    "content_and_user_features": measure(lambda: s.features(history, [])),
    "serving_without_storage": measure(lambda: s.recommend(history, [], set(), "personalized")),
}
if s.ready:
    features = s.prep.transform(s.items[:1])

    def item_encode():
        with torch.inference_mode():
            return s.model.item(*features)

    user = s.vectors[:5].mean(0)
    x = s.features(history, [])
    result["item_encoder"] = measure(item_encode)
    result["exact_search"] = measure(lambda: np.argsort(-(s.vectors @ user))[:50])
    result["ranker"] = measure(lambda: s.scores(x, "ranker"))
    result["vector_bytes"] = s.vectors.nbytes
else:
    result["research_stages"] = "Unavailable until a measured research release is installed."
# Three QA sessions keep each under the per-session request limit.
latencies = []
for _ in range(3):
    with httpx.Client(base_url=base_url, headers={"X-FeedRank": "1", "X-FeedRank-QA": "1"}) as c:
        c.post("/api/sessions").raise_for_status()
        for n in range(107):
            # Respect the local reverse proxy's request limit. Pacing is excluded
            # from the measured request latency; this is not a throughput test.
            time.sleep(0.11)
            start = time.perf_counter()
            response = c.get("/api/recommendations")
            response.raise_for_status()
            if response.json()["model_version"] != s.version:
                raise SystemExit("HTTP and local model versions differ; refuse comparison.")
            elapsed = (time.perf_counter() - start) * 1000
            if n >= 7:
                latencies.append(elapsed)
result["http"] = {
    "p50_ms": float(np.percentile(latencies, 50)),
    "p95_ms": float(np.percentile(latencies, 95)),
    "measurements": len(latencies),
    "target": base_url,
    "pacing_seconds": 0.11,
    "transport": "localhost TCP; one client; includes SQLite served logging",
    "history_length": 0,
    "warmup_per_session": 7,
}
result["process_rss_bytes"] = psutil.Process().memory_info().rss
result["rss_scope"] = "Benchmark runner including local Service; not the API worker."
(root / "reports/benchmark.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
