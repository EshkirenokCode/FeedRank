import numpy as np

from feedrank.data import temporal
from feedrank.metrics import aggregate, bootstrap, metrics
from feedrank.model import diversify


def test_hand_computed_metrics():
    m = metrics([0, 1, 1], [3, 2, 1])
    expected = (1 / np.log2(3) + 1 / np.log2(4)) / (1 + 1 / np.log2(3))
    assert abs(m["ndcg10"] - expected) < 1e-12
    assert m["mrr"] == 0.5
    assert m["auc"] == 0
    assert metrics([1, 0], [1, 1], ["b", "a"])["mrr"] == 0.5
    assert metrics([0, 0], [1, 2])["ndcg10"] is None
    assert metrics([1, 1], [1, 2])["auc"] is None
    assert aggregate([metrics([0], [1])])["ndcg10"]["groups"] == 0


def test_cluster_bootstrap_deterministic():
    a = bootstrap(["a", "a", "b"], [0.1, 0.2, -0.1])
    assert a == bootstrap(["a", "a", "b"], [0.1, 0.2, -0.1])
    assert a["users"] == 2
    assert abs(a["mean_difference"] - 0.2 / 3) < 1e-12


def test_policy_no_duplicates_and_fills_single_category():
    assert diversify([0, 1, 2, 3], ["a"] * 4) == [0, 1, 2, 3]
    order = diversify([0, 1, 2, 3, 4], ["a", "a", "a", "b", "b"], limit=4)
    assert order[:4] == [0, 1, 3, 4]
    assert sorted(order) == list(range(5))


def test_temporal_groups_and_timestamp_ties():
    rows = [{"id": str(i), "time": str(i // 3)} for i in range(30)]
    a, b, c = temporal(rows)
    assert len(a) + len(b) + len(c) == 30
    assert max(r["time"] for r in a) < min(r["time"] for r in b)
    assert max(r["time"] for r in b) < min(r["time"] for r in c)
    assert not ({r["id"] for r in a} & {r["id"] for r in b})
