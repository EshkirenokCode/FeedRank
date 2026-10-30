import numpy as np
from scipy.stats import rankdata


def metrics(labels, scores, ids=None):
    y, s = np.asarray(labels), np.asarray(scores)
    order = np.lexsort((np.asarray(ids) if ids is not None else np.arange(len(y)), -s))
    ranked = y[order]
    result = {}
    for k in (5, 10):
        weights = 1 / np.log2(np.arange(2, min(k, len(y)) + 2))
        ideal = np.dot(np.sort(y)[::-1][:k], weights)
        result[f"ndcg{k}"] = float(np.dot(ranked[:k], weights) / ideal) if ideal else None
    pos = np.flatnonzero(ranked)
    result["mrr"] = float(1 / (pos[0] + 1)) if len(pos) else None
    npos = int(y.sum())
    nneg = len(y) - npos
    result["auc"] = (
        float((rankdata(s)[y == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg))
        if npos and nneg
        else None
    )
    return result


def aggregate(rows):
    return {
        k: {"mean": float(np.mean(v)), "groups": len(v)} if v else {"mean": None, "groups": 0}
        for k in ["ndcg5", "ndcg10", "mrr", "auc"]
        for v in [[r[k] for r in rows if r[k] is not None]]
    }


def bootstrap(users, differences, repeats=500):
    totals, counts = {}, {}
    for user, diff in zip(users, differences):
        totals[user] = totals.get(user, 0) + diff
        counts[user] = counts.get(user, 0) + 1
    keys = sorted(totals)
    t, c = np.array([totals[k] for k in keys]), np.array([counts[k] for k in keys])
    rng = np.random.default_rng(42)
    values = []
    for _ in range(repeats):
        idx = rng.integers(0, len(keys), len(keys))
        values.append(float(t[idx].sum() / c[idx].sum()))
    return {
        "mean_difference": float(t.sum() / c.sum()),
        "ci95": np.quantile(values, [0.025, 0.975]).tolist(),
        "users": len(keys),
        "resamples": repeats,
        "seed": 42,
    }
