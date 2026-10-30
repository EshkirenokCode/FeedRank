import json
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.feature_extraction.text import TfidfVectorizer

from .data import ROOT, sha
from .model import MAX_HISTORY, Preprocessor, TwoTower, diversify, encode


class Service:
    def __init__(self, artifacts=None):
        torch.set_num_threads(2)
        self.items = json.loads((ROOT / "catalog/demo.json").read_text())
        self.index = {x["id"]: i for i, x in enumerate(self.items)}
        self.categories = sorted({x["category"] for x in self.items})
        self.ready = False
        self.reason = "Research release is not installed. Showing a balanced demo fallback."
        self.version = "demo-fallback-v1"
        self.selected = "content"
        self.policy = "category-cap-v1"
        self.prior = 0.05
        self.pop = np.full(len(self.items), self.prior)
        self.tf = TfidfVectorizer(sublinear_tf=True)
        self.text = self.tf.fit_transform([x["title"] + " " + x["abstract"] for x in self.items])
        self.artifacts = Path(artifacts or ROOT / "artifacts")
        manifest_path = self.artifacts / "release.json"
        if not manifest_path.exists():
            return
        try:
            manifest = json.loads(manifest_path.read_text())
            for file, checksum in manifest["files"].items():
                if Path(file).name != file or sha(self.artifacts / file) != checksum:
                    raise ValueError("Artifact checksum mismatch")
            if manifest["catalog_sha256"] != sha(ROOT / "catalog/demo.json"):
                raise ValueError("Catalog changed; rebuild vector snapshot")
            checkpoint = torch.load(
                self.artifacts / "encoder.pt", weights_only=True, map_location="cpu"
            )
            self.prep = Preprocessor(**checkpoint["preprocessing"])
            self.model = TwoTower(**checkpoint["config"])
            self.model.load_state_dict(checkpoint["state_dict"])
            self.model.eval()
            self.vectors = np.load(self.artifacts / "demo-vectors.npy", allow_pickle=False)
            actual = encode(self.model, self.prep.transform(self.items))
            if self.vectors.shape != actual.shape or not np.allclose(
                self.vectors, actual, atol=1e-6
            ):
                raise ValueError("Encoder/vector snapshot mismatch")
            self.ranker = json.loads((self.artifacts / "ranker.json").read_text())
            baseline = json.loads((self.artifacts / "baselines.json").read_text())
            self.tf = TfidfVectorizer(vocabulary=baseline["tfidf_vocab"], sublinear_tf=True)
            self.tf.fit([" ".join(self.prep.vocab)])
            self.tf.idf_ = np.array(baseline["idf"])
            self.text = self.tf.transform([x["title"] + " " + x["abstract"] for x in self.items])
            self.prior = baseline["prior"]
            self.pop = np.full(len(self.items), self.prior)
            self.version, self.selected = manifest["model_version"], manifest["selected"]
            self.ready, self.reason = True, None
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            self.reason = f"Research release could not be loaded ({type(exc).__name__}). Demo fallback is active."

    def features(self, history, interests):
        ix = [self.index[i] for i in history if i in self.index][-MAX_HISTORY:]
        selected = set(interests)
        affinity = np.array(
            [
                sum(self.items[j]["category"] == x["category"] for j in ix) / max(1, len(ix))
                for x in self.items
            ]
        )
        if selected:
            affinity += np.array(
                [0.35 * (x["category"] in selected) / len(selected) for x in self.items]
            )
        if ix:
            profile = np.asarray(self.text[ix].sum(axis=0)).ravel()
            content = np.asarray(self.text @ (profile / max(np.linalg.norm(profile), 1e-8))).ravel()
        else:
            content = np.zeros(len(self.items))
        if not self.ready:
            return np.column_stack(
                [
                    content,
                    content,
                    affinity,
                    np.log(self.pop),
                    np.full(len(self.items), np.log1p(len(ix))),
                ]
            )
        with torch.inference_mode():
            h = (
                torch.from_numpy(self.vectors[ix][None])
                if ix
                else torch.zeros(1, 1, self.vectors.shape[1])
            )
            mask = (
                torch.ones(1, len(ix), dtype=torch.bool)
                if ix
                else torch.zeros(1, 1, dtype=torch.bool)
            )
            cats = [self.prep.categories.get(c, 0) for c in interests]
            iv = self.model.interest(torch.tensor(cats)).mean(0, keepdim=True) if cats else None
            user = self.model.user(h, mask, iv).numpy()[0]
        return np.column_stack(
            [
                self.vectors @ user,
                content,
                affinity,
                np.log(self.pop),
                np.full(len(self.items), np.log1p(len(ix))),
            ]
        )

    def scores(self, features, method):
        if method == "popular":
            return features[:, 3]
        if method == "content":
            return features[:, 1] + 0.1 * features[:, 2]
        if method == "tower":
            return features[:, 0]
        r = self.ranker
        return ((features - r["mean"]) / r["scale"]) @ np.array(r["coef"]) + r["intercept"]

    def recommend(self, history, interests, excluded, mode, limit=12):
        start = time.perf_counter()
        x = self.features(history, interests)
        timings = {"encoder_ms": (time.perf_counter() - start) * 1000}
        method = {"popular": "popular", "content": "content", "personalized": self.selected}[mode]
        fallback = None
        if mode == "personalized" and not self.ready:
            method, fallback = "content", self.reason
        elif mode == "personalized" and not history and not interests:
            method, fallback = "popular", "No history yet. A balanced catalog starts your session."
        scores = self.scores(x, method)
        # Public items have no MIND item-level clicks: identical smoothed prior, never invented counts.
        retrieval_scores = x[:, 0] if method in ("tower", "ranker") else scores
        start = time.perf_counter()
        candidates = [
            int(i)
            for i in np.lexsort(([a["id"] for a in self.items], -retrieval_scores))
            if self.items[i]["id"] not in excluded
        ][:50]
        timings["retrieval_ms"] = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        order = sorted(candidates, key=lambda i: (-float(scores[i]), self.items[i]["id"]))
        order = diversify(order, [a["category"] for a in self.items], limit=limit)
        timings["ranker_policy_ms"] = (time.perf_counter() - start) * 1000
        result = []
        for i in order[:limit]:
            reason = "Balanced demo selection"
            if self.items[i]["category"] in interests:
                reason = "Matches a selected interest"
            elif history and method in ("content", "tower", "ranker"):
                reason = "Based on your reading history"
            result.append(self.items[i] | {"reason": reason, "score": float(scores[i])})
        return {
            "items": result,
            "fallback": fallback,
            "method": method,
            "model_version": self.version,
            "policy_version": self.policy,
            "timings": timings,
            "research_ready": self.ready,
            "note": "Original demo content. No item-level audience popularity has been measured.",
        }
