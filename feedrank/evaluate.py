"""One-shot holdout evaluation after C selection; never trains on holdout."""

import json
import time
from collections import Counter

import numpy as np

from .data import DATA, REPORTS, sha, write
from .metrics import aggregate, bootstrap, metrics
from .model import diversify
from .train import ART, Research, seed

METHODS = ["popular", "content", "tower", "ranker", "policy"]


def scores_for(research, row, x):
    scores = {
        "popular": x[:, 3],
        "content": x[:, 1] + 0.1 * x[:, 2],
        "tower": x[:, 0],
        "ranker": research.rank(x),
    }
    order = np.lexsort((row["items"], -scores["ranker"]))
    cats = [research.items.get(i, {}).get("category", "") for i in row["items"]]
    policy = diversify(order, cats)
    values = np.empty(len(policy))
    values[policy] = np.arange(len(policy), 0, -1)
    scores["policy"] = values
    return scores


def evaluate_split(research, name):
    rows = research.splits[name]
    hs, cats, users = research.user_features(rows)
    ch, cc, cu = research.user_features(rows, cold=True)
    per = {m: [] for m in METHODS + ["no_history", "ranker_no_category"]}
    exposure = {m: Counter() for m in METHODS}
    coverage = {m: set() for m in METHODS}
    head_count = Counter(
        i for r in research.splits["A_fit"] for i, y in zip(r["items"], r["labels"]) if y
    )
    head = {i for i, _ in head_count.most_common(max(1, len(head_count) // 5))}
    head_exposure = Counter()
    cases = []
    for n, (r, h, c, u) in enumerate(zip(rows, hs, cats, users)):
        x = research.group_features(r, h, c, u)
        ss = scores_for(research, r, x)
        cold_x = research.group_features(r, ch[n], cc[n], cu[n])
        ss["no_history"] = research.rank(cold_x)
        without = x.copy()
        without[:, 2] = 0
        ss["ranker_no_category"] = research.rank(without)
        for m, s in ss.items():
            per[m].append(metrics(r["labels"], s, r["items"]))
            if m in METHODS:
                top = np.lexsort((r["items"], -s))[:10]
                for j in top:
                    i = r["items"][j]
                    coverage[m].add(i)
                    exposure[m][research.items.get(i, {}).get("category", "unknown")] += 1
                    head_exposure[m] += i in head
        if n < 12:
            # Case notes contain no source text or user IDs.
            ranked = np.lexsort((r["items"], -ss["ranker"]))
            cases.append(
                {
                    "case": n + 1,
                    "history_length": len(r["history"]),
                    "candidates": len(r["items"]),
                    "positives": sum(r["labels"]),
                    "top_categories": [
                        research.items.get(r["items"][j], {}).get("category", "unknown")
                        for j in ranked[:5]
                    ],
                    "positive_ranks": [
                        int(np.where(ranked == j)[0][0]) + 1 for j, y in enumerate(r["labels"]) if y
                    ],
                    "ndcg10": per["ranker"][-1]["ndcg10"],
                    "empty_history": not r["history"],
                }
            )
    segments = {
        "warm": [i for i, r in enumerate(rows) if r["history"]],
        "empty": [i for i, r in enumerate(rows) if not r["history"]],
        "short": [i for i, r in enumerate(rows) if 1 <= len(r["history"]) <= 5],
        "new_item_group": [
            i for i, r in enumerate(rows) if any(k not in research.fit_ids for k in r["items"])
        ],
    }
    result = {
        "groups": len(rows),
        "users": len({r["user"] for r in rows}),
        "candidates": sum(len(r["items"]) for r in rows),
        "metrics": {m: aggregate(p) for m, p in per.items()},
        "segments": {
            k: {m: aggregate([per[m][i] for i in ix]) for m in METHODS}
            for k, ix in segments.items()
        },
        "exposure": {m: dict(c) for m, c in exposure.items()},
        "head_exposure_fraction": {
            m: head_exposure[m] / max(1, sum(exposure[m].values())) for m in METHODS
        },
        "catalog_coverage": {m: len(s) / max(len(research.items), 1) for m, s in coverage.items()},
        "cases": cases,
    }
    valid = [i for i in range(len(rows)) if per["ranker"][i]["ndcg10"] is not None]
    result["ranker_minus_content_ci"] = bootstrap(
        [rows[i]["user"] for i in valid],
        [per["ranker"][i]["ndcg10"] - per["content"][i]["ndcg10"] for i in valid],
    )
    return result


def catalog_replay(research, name):
    rows = [r for r in research.splits[name] if any(r["labels"])][:200]
    # Only earlier observations affect availability; timestamps have no timezone in MIND.
    first = {}
    for split in research.splits.values():
        for r in split:
            for i in r["items"] + r["history"]:
                first[i] = min(first.get(i, r["time"]), r["time"])
    hs, cats, users = research.user_features(rows)
    recall, ndcg, unavailable, sizes = [], [], 0, []
    for r, h, c, u in zip(rows, hs, cats, users):
        ids = sorted(i for i, t in first.items() if t < r["time"] and i in research.index)
        ix = np.array([research.index[i] for i in ids])
        sizes.append(len(ids))
        scores = research.vectors[ix] @ u
        top = np.lexsort((ids, -scores))[:50]
        retrieved = [ids[j] for j in top]
        positives = {i for i, y in zip(r["items"], r["labels"]) if y}
        unavailable += len(positives - set(ids))
        recall.append(len(positives & set(retrieved)) / len(positives))
        synthetic = {"items": retrieved}
        x = research.group_features(synthetic, h, c, u)
        order = np.lexsort((retrieved, -research.rank(x)))
        y = np.array([retrieved[j] in positives for j in order[:10]], dtype=float)
        weights = 1 / np.log2(np.arange(2, len(y) + 2))
        ideal = sum(1 / np.log2(np.arange(2, min(10, len(positives)) + 2)))
        ndcg.append(float(y @ weights / ideal))
    return {
        "groups": len(rows),
        "selection": "first 200 chronological positive groups",
        "k": 50,
        "recall50": float(np.mean(recall)),
        "pipeline_ndcg10": float(np.mean(ndcg)),
        "unavailable_positive_count": unavailable,
        "catalog_size_range": [min(sizes), max(sizes)],
        "availability": "strictly earlier first-observed time; not publication time",
    }


def main():
    seed()
    marker = REPORTS / "holdout.lock"
    if marker.exists():
        raise SystemExit(
            "Holdout already evaluated. Use a new documented protocol for further tuning."
        )
    training = json.loads((REPORTS / "training.json").read_text())
    if training["provenance"] != {
        "protocol": sha(REPORTS / "protocol.md"),
        "prepared": sha(DATA / "prepared.json"),
        "data_manifest": sha(REPORTS / "data-manifest.json"),
    }:
        raise SystemExit("Training data or protocol changed; refuse evaluation.")
    if any(sha(ART / f) != digest for f, digest in training["artifacts"].items()):
        raise SystemExit("Training artifacts changed; refuse evaluation.")
    start = time.perf_counter()
    research = Research().load()
    c = evaluate_split(research, "C")
    selected = max(METHODS[:-1], key=lambda m: c["metrics"][m]["ndcg10"]["mean"])
    write(
        ART / "selection.json",
        {"selected": selected, "criterion": "C mean NDCG@10", "policy": "category-cap-v1"},
    )
    write(REPORTS / "selection-C.json", c)
    marker.write_text("Selection frozen. Official validation opened; no further tuning.\n")
    holdout = evaluate_split(research, "holdout")
    result = {
        "protocol": "v1",
        "provenance": training["provenance"],
        "artifacts": training["artifacts"] | {"selection.json": sha(ART / "selection.json")},
        "selected": selected,
        "C": c,
        "holdout": holdout,
        "retrieval": {n: catalog_replay(research, n) for n in ["C", "holdout"]},
        "seconds": time.perf_counter() - start,
    }
    write(REPORTS / "metrics.json", result)
    lines = [
        "# Evaluation",
        "",
        "Official validation used as final holdout. Not an official test.",
        "",
        "Full logged candidate sets. Primary metric: NDCG@10. See protocol.md for exclusions.",
        "",
    ]
    for name, report in [("C — configuration selection", c), ("Final holdout", holdout)]:
        lines += [
            f"## {name}",
            "",
            "| Method | NDCG@10 | NDCG@5 | MRR | Group AUC |",
            "|---|---:|---:|---:|---:|",
        ]
        for m, v in report["metrics"].items():
            lines.append(
                "| "
                + m
                + " | "
                + " | ".join(f"{v[k]['mean']:.5f}" for k in ["ndcg10", "ndcg5", "mrr", "auc"])
                + " |"
            )
        lines += [
            "",
            f"Groups: {report['groups']}; users: {report['users']}; candidates: {report['candidates']}.",
            "",
        ]
    lines += [
        f"Selected on C: **{selected}**.",
        "",
        "No online lift is established. Original demo content has unmeasured transfer quality.",
        "Machine-readable segments, ablations, user-cluster CI, exposure, cases and retrieval: metrics.json.",
    ]
    (REPORTS / "evaluation.md").write_text("\n".join(lines) + "\n")
    print("Evaluation complete", selected, flush=True)


if __name__ == "__main__":
    main()
