"""Build a small public serving bundle after measured research evaluation."""

import json

import numpy as np

from .data import REPORTS, ROOT, sha, write
from .model import encode
from .train import ART, Research, seed


def main():
    seed()
    if not (REPORTS / "metrics.json").exists():
        raise SystemExit("Run measured evaluation before building a research release.")
    report = json.loads((REPORTS / "metrics.json").read_text())
    if any(sha(ART / f) != digest for f, digest in report["artifacts"].items()):
        raise SystemExit("Artifacts no longer match evaluation; refuse release.")
    if report["provenance"]["protocol"] != sha(REPORTS / "protocol.md"):
        raise SystemExit("Protocol changed after evaluation; refuse release.")
    research = Research().load()
    catalog = json.loads((ROOT / "catalog/demo.json").read_text())
    np.save(
        ART / "demo-vectors.npy",
        encode(research.model, research.prep.transform(catalog)),
        allow_pickle=False,
    )
    baseline = json.loads((ART / "research-baselines.json").read_text())
    # No source article IDs, text, click counts or research item vectors enter the public bundle.
    write(ART / "baselines.json", {k: baseline[k] for k in ["tfidf_vocab", "idf", "prior"]})
    selection = json.loads((ART / "selection.json").read_text())
    files = ["encoder.pt", "demo-vectors.npy", "baselines.json", "ranker.json", "selection.json"]
    write(
        ART / "release.json",
        {
            "model_version": "feedrank-v1-" + sha(ART / "encoder.pt")[:12],
            "policy_version": "category-cap-v1",
            "selected": selection["selected"],
            "catalog_sha256": sha(ROOT / "catalog/demo.json"),
            "files": {f: sha(ART / f) for f in files},
            "protocol_sha256": sha(REPORTS / "protocol.md"),
            "metrics_sha256": sha(REPORTS / "metrics.json"),
            "data_manifest_sha256": sha(REPORTS / "data-manifest.json"),
            "feature_definitions": [
                "tower_cosine",
                "content_cosine",
                "category_affinity",
                "log_popularity",
                "log_history_length",
            ],
        },
    )
    print("Public bundle ready; research data remain private.")


if __name__ == "__main__":
    main()
