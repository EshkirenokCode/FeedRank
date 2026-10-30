import json
import os
import platform
import random
import time
from collections import Counter

import numpy as np
import psutil
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .data import DATA, REPORTS, ROOT, sha, write
from .model import MAX_HISTORY, Preprocessor, TwoTower, encode, tokens

ART = ROOT / "artifacts"
FEATURE_NAMES = [
    "tower_cosine",
    "content_cosine",
    "category_affinity",
    "log_popularity",
    "log_history_length",
]


def seed():
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)


def examples(rows, index, rng):
    hist, cand = [], []
    for r in rows:
        neg = [index.get(i, 0) for i, y in zip(r["items"], r["labels"]) if not y]
        if not neg:
            continue
        for item, y in zip(r["items"], r["labels"]):
            if y:
                h = [index.get(i, 0) for i in r["history"][-MAX_HISTORY:]]
                hist.append(h + [0] * (MAX_HISTORY - len(h)))
                cand.append([index.get(item, 0)] + rng.choice(neg, 4, replace=True).tolist())
    return torch.tensor(hist), torch.tensor(cand)


class Research:
    def __init__(self):
        prepared = json.loads((DATA / "prepared.json").read_text())
        self.items, self.splits = prepared["items"], prepared["splits"]
        self.ids = ["<pad>"] + sorted(self.items)
        self.index = {x: i for i, x in enumerate(self.ids)}
        self.catalog = [
            {"id": "<pad>", "category": "", "subcategory": "", "title": "", "abstract": ""}
        ] + [self.items[x] for x in self.ids[1:]]
        self.fit_ids = {x for r in self.splits["A_fit"] for x in r["items"] + r["history"]}

    def load(self):
        state = torch.load(ART / "encoder.pt", map_location="cpu", weights_only=True)
        self.prep = Preprocessor(**state["preprocessing"])
        self.model = TwoTower(**state["config"])
        self.model.load_state_dict(state["state_dict"])
        self.model.eval()
        self.features = self.prep.transform(self.catalog)
        self.vectors = encode(self.model, self.features)
        self.vectors[0] = 0
        base = json.loads((ART / "research-baselines.json").read_text())
        self.pop = np.array([base["popularity"].get(i, base["prior"]) for i in self.ids])
        self.tfidf = TfidfVectorizer(vocabulary=base["tfidf_vocab"], sublinear_tf=True)
        self.tfidf.fit([" ".join(self.prep.vocab)])
        self.tfidf.idf_ = np.array(base["idf"])
        self.text = self.tfidf.transform([x["title"] + " " + x["abstract"] for x in self.catalog])
        self.ranker = json.loads((ART / "ranker.json").read_text())
        return self

    def user_features(self, rows, cold=False):
        h = np.zeros((len(rows), MAX_HISTORY), dtype=np.int64)
        cats = np.zeros((len(rows), len(self.prep.categories) + 1), dtype=np.float32)
        for n, r in enumerate(rows):
            history = [] if cold else r["history"][-MAX_HISTORY:]
            ix = [self.index.get(i, 0) for i in history]
            h[n, : len(ix)] = ix
            for i in ix:
                cats[n, self.features[1][i]] += 1 / max(1, len(ix))
        with torch.inference_mode():
            users = self.model.user(
                torch.from_numpy(self.vectors[h]), torch.from_numpy(h != 0)
            ).numpy()
        return h, cats, users

    def group_features(self, row, h, cats, user):
        ix = np.array([self.index.get(i, 0) for i in row["items"]])
        valid = h[h != 0]
        if len(valid):
            profile = self.text[valid].sum(axis=0)
            norm = np.linalg.norm(profile)
            content = np.asarray(
                self.text[ix] @ (np.asarray(profile).ravel() / max(norm, 1e-8))
            ).ravel()
        else:
            content = np.zeros(len(ix))
        affinity = cats[self.features[1][ix].numpy()]
        return np.column_stack(
            [
                self.vectors[ix] @ user,
                content,
                affinity,
                np.log(np.maximum(self.pop[ix], 1e-9)),
                np.full(len(ix), np.log1p(len(valid))),
            ]
        )

    def rank(self, x):
        r = self.ranker
        return ((x - r["mean"]) / r["scale"]) @ np.array(r["coef"]) + r["intercept"]


def train():
    seed()
    start = time.perf_counter()
    provenance = {
        "protocol": sha(REPORTS / "protocol.md"),
        "prepared": sha(DATA / "prepared.json"),
        "data_manifest": sha(REPORTS / "data-manifest.json"),
    }
    research = Research()
    fitting_items = [research.items[i] for i in sorted(research.fit_ids) if i in research.items]
    prep = Preprocessor.fit(fitting_items)
    features = prep.transform(research.catalog)
    model = TwoTower(len(prep.vocab), len(prep.categories) + 1, len(prep.subcategories) + 1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.002, weight_decay=0.001)
    train_h, train_c = examples(research.splits["A_fit"], research.index, np.random.default_rng(42))
    val_h, val_c = examples(
        research.splits["A_validation"], research.index, np.random.default_rng(43)
    )
    losses, best = [], float("inf")
    for epoch in range(3):
        model.train()
        train_loss = []
        for batch in torch.randperm(len(train_h)).split(256):
            optimizer.zero_grad()
            scores = model(train_h[batch], train_c[batch], features)
            loss = torch.nn.functional.cross_entropy(
                scores, torch.zeros(len(batch), dtype=torch.long)
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5)
            optimizer.step()
            train_loss.append(loss.item())
        model.eval()
        with torch.inference_mode():
            v = [
                torch.nn.functional.cross_entropy(
                    model(val_h[i : i + 256], val_c[i : i + 256], features),
                    torch.zeros(len(val_h[i : i + 256]), dtype=torch.long),
                ).item()
                for i in range(0, len(val_h), 256)
            ]
        value = float(np.mean(v))
        losses.append(
            {"epoch": epoch + 1, "train": float(np.mean(train_loss)), "validation": value}
        )
        if value < best:
            best = value
            torch.save(
                {
                    "config": model.config,
                    "preprocessing": prep.state(),
                    "state_dict": model.state_dict(),
                    "version": "feedrank-v1",
                    "torch_version": str(torch.__version__),
                    "provenance": provenance,
                },
                ART / "encoder.pt",
            )
        print(losses[-1], flush=True)
    counts, exposures = Counter(), Counter()
    for r in research.splits["A_fit"]:
        for i, y in zip(r["items"], r["labels"]):
            counts[i] += y
            exposures[i] += 1
    prior = sum(counts.values()) / sum(exposures.values())
    pop = {i: (counts[i] + 20 * prior) / (n + 20) for i, n in exposures.items()}
    tf = TfidfVectorizer(max_features=20000, min_df=2, sublinear_tf=True)
    tf.fit([x["title"] + " " + x["abstract"] for x in fitting_items])
    write(
        ART / "research-baselines.json",
        {
            "popularity": pop,
            "prior": prior,
            "tfidf_vocab": {k: int(v) for k, v in tf.vocabulary_.items()},
            "idf": tf.idf_.tolist(),
        },
    )
    write(ART / "ranker.json", {"mean": [0] * 5, "scale": [1] * 5, "coef": [0] * 5, "intercept": 0})
    research.load()
    rows = research.splits["B"]
    hs, cats, users = research.user_features(rows)
    xs = [research.group_features(r, h, c, u) for r, h, c, u in zip(rows, hs, cats, users)]
    x, y = np.concatenate(xs), np.concatenate([r["labels"] for r in rows])
    scaler = StandardScaler().fit(x)
    ranker = LogisticRegression(C=1, max_iter=200, random_state=42).fit(scaler.transform(x), y)
    write(
        ART / "ranker.json",
        {
            "mean": scaler.mean_.tolist(),
            "scale": scaler.scale_.tolist(),
            "coef": ranker.coef_[0].tolist(),
            "intercept": float(ranker.intercept_[0]),
            "features": FEATURE_NAMES,
        },
    )
    # Audit unknowns without fitting any preprocessing on later windows.
    oov = {}
    for name, split in research.splits.items():
        ids = {i for r in split for i in r["items"] + r["history"]}
        ts = [
            t
            for i in ids
            if i in research.items
            for t in tokens(research.items[i]["title"] + " " + research.items[i]["abstract"])
        ]
        oov[name] = {
            "token_oov": sum(t not in prep.vocab for t in ts) / max(len(ts), 1),
            "category_oov": sum(
                research.items[i]["category"] not in prep.categories
                for i in ids
                if i in research.items
            )
            / max(len(ids), 1),
        }
    write(
        REPORTS / "training.json",
        {
            "seed": 42,
            "provenance": provenance,
            "artifacts": {
                f: sha(ART / f) for f in ["encoder.pt", "ranker.json", "research-baselines.json"]
            },
            "device": "cpu",
            "threads": 4,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": str(torch.__version__),
            "seconds": time.perf_counter() - start,
            "rss_bytes": psutil.Process(os.getpid()).memory_info().rss,
            "losses": losses,
            "examples": len(train_h),
            "validation_examples": len(val_h),
            "B_candidates": len(y),
            "oov": oov,
        },
    )
    print("Training complete", flush=True)


if __name__ == "__main__":
    train()
