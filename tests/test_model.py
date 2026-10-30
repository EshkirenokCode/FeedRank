import io

import numpy as np
import torch

from feedrank.model import Preprocessor, TwoTower, encode
from feedrank.train import examples, seed

ITEMS = [
    {
        "title": "River water science",
        "abstract": "Water in the river",
        "category": "science",
        "subcategory": "water",
    },
    {
        "title": "Local sport game",
        "abstract": "A local sport game",
        "category": "sports",
        "subcategory": "game",
    },
]


def test_optimizer_roundtrip_and_new_content():
    seed()
    prep = Preprocessor.fit(ITEMS)
    model = TwoTower(len(prep.vocab), len(prep.categories) + 1, len(prep.subcategories) + 1)
    features = prep.transform(
        [{"title": "", "abstract": "", "category": "", "subcategory": ""}] + ITEMS
    )
    before = model.words.weight.detach().clone()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    loss = torch.nn.functional.cross_entropy(
        model(torch.tensor([[1, 0], [2, 0]]), torch.tensor([[1, 2], [2, 1]]), features),
        torch.zeros(2, dtype=torch.long),
    )
    loss.backward()
    optimizer.step()
    assert not torch.equal(before, model.words.weight)
    model.eval()
    expected = encode(model, features)
    stream = io.BytesIO()
    torch.save({"state_dict": model.state_dict(), "config": model.config}, stream)
    stream.seek(0)
    state = torch.load(stream, weights_only=True)
    restored = TwoTower(**state["config"])
    restored.load_state_dict(state["state_dict"])
    np.testing.assert_allclose(expected, encode(restored, features), atol=1e-7)
    new = prep.transform(
        [
            {
                "title": "Previously unseen comet",
                "abstract": "",
                "category": "unknown",
                "subcategory": "unknown",
            }
        ]
    )
    assert torch.isfinite(torch.from_numpy(encode(restored, new))).all()


def test_padding_empty_and_interest():
    model = TwoTower(8, 4, 4)
    history = torch.randn(2, 3, 64)
    mask = torch.tensor([[True, False, False], [False, False, False]])
    output = model.user(history, mask)
    history[:, 1:] = 1000
    torch.testing.assert_close(output, model.user(history, mask))
    assert torch.isfinite(output).all()
    assert not torch.allclose(
        output, model.user(history, mask, model.interest(torch.tensor([1, 2])))
    )


def test_observed_negatives_only_and_multiple_positives():
    rows = [
        {"history": ["h"], "items": ["p", "q", "n"], "labels": [1, 1, 0]},
        {"history": [], "items": ["p"], "labels": [1]},
    ]
    h, candidates = examples(rows, {"h": 1, "p": 2, "q": 3, "n": 4}, np.random.default_rng(1))
    assert len(h) == 2
    assert set(candidates[:, 0].tolist()) == {2, 3}
    assert torch.all(candidates[:, 1:] == 4)


def test_vocabulary_excludes_future_text():
    prep = Preprocessor.fit(ITEMS)
    assert "comet" not in prep.vocab
    assert (
        prep.transform(
            [{"title": "Comet", "abstract": "", "category": "future", "subcategory": "future"}]
        )[0][0, 0]
        == 1
    )
