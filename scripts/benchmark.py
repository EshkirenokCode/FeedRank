"""Local single-client measurements; not a production SLA."""

import json
import platform
import time
from pathlib import Path

import httpx
import numpy as np
import psutil
import torch

from feedrank.serving import Service

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
    with httpx.Client(
        base_url="http://127.0.0.1:8000", headers={"X-FeedRank": "1", "X-FeedRank-QA": "1"}
    ) as c:
        c.post("/api/sessions").raise_for_status()
        for n in range(107):
            start = time.perf_counter()
            c.get("/api/recommendations").raise_for_status()
            elapsed = (time.perf_counter() - start) * 1000
            if n >= 7:
                latencies.append(elapsed)
result["http"] = {
    "p50_ms": float(np.percentile(latencies, 50)),
    "p95_ms": float(np.percentile(latencies, 95)),
    "measurements": len(latencies),
    "transport": "localhost TCP; one client; includes SQLite served logging",
    "history_length": 0,
    "warmup_per_session": 7,
}
result["process_rss_bytes"] = psutil.Process().memory_info().rss
(root / "reports/benchmark.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
