import re
from collections import Counter

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

MAX_TOKENS = 40
MAX_HISTORY = 20


def tokens(text):
    return re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower())


class Preprocessor:
    def __init__(self, vocab, categories, subcategories):
        self.vocab, self.categories, self.subcategories = vocab, categories, subcategories

    @classmethod
    def fit(cls, items):
        counts = Counter(t for x in items for t in tokens(x["title"] + " " + x["abstract"]))
        vocab = {"<pad>": 0, "<unk>": 1}
        vocab.update({t: i + 2 for i, (t, n) in enumerate(counts.most_common(19998)) if n >= 2})
        return cls(
            vocab,
            {c: i + 1 for i, c in enumerate(sorted({x["category"] for x in items}))},
            {c: i + 1 for i, c in enumerate(sorted({x["subcategory"] for x in items}))},
        )

    def transform(self, items):
        text = np.zeros((len(items), MAX_TOKENS), dtype=np.int64)
        cat, sub = [], []
        for i, x in enumerate(items):
            ts = tokens(x["title"] + " " + x["abstract"])[:MAX_TOKENS]
            text[i, : len(ts)] = [self.vocab.get(t, 1) for t in ts]
            cat.append(self.categories.get(x["category"], 0))
            sub.append(self.subcategories.get(x["subcategory"], 0))
        return torch.from_numpy(text), torch.tensor(cat), torch.tensor(sub)

    def state(self):
        return {
            "vocab": self.vocab,
            "categories": self.categories,
            "subcategories": self.subcategories,
        }


class TwoTower(nn.Module):
    def __init__(self, vocab_size, categories, subcategories, width=48, dim=64):
        super().__init__()
        self.config = {
            "vocab_size": vocab_size,
            "categories": categories,
            "subcategories": subcategories,
            "width": width,
            "dim": dim,
        }
        self.words = nn.Embedding(vocab_size, width, padding_idx=0)
        self.category = nn.Embedding(categories, width, padding_idx=0)
        self.subcategory = nn.Embedding(subcategories, width, padding_idx=0)
        self.project = nn.Linear(width, dim)
        self.user_project = nn.Linear(dim, dim, bias=False)
        nn.init.zeros_(self.user_project.weight)
        self.empty = nn.Parameter(torch.randn(dim) * 0.01)

    def item(self, words, cat, sub):
        mask = words.ne(0).unsqueeze(-1)
        pooled = (self.words(words) * mask).sum(-2) / mask.sum(-2).clamp_min(1)
        return F.normalize(
            self.project(pooled + self.category(cat) + 0.5 * self.subcategory(sub)), dim=-1
        )

    def interest(self, categories):
        return F.normalize(F.linear(self.category(categories), self.project.weight), dim=-1)

    def user(self, history_vectors, mask, interests=None):
        pooled = (history_vectors * mask.unsqueeze(-1)).sum(-2) / mask.sum(
            -1, keepdim=True
        ).clamp_min(1)
        if interests is not None:
            pooled = pooled + 0.35 * interests
        empty = pooled.norm(dim=-1, keepdim=True) < 1e-8
        pooled = torch.where(empty, self.empty.expand_as(pooled), pooled)
        return F.normalize(pooled + self.user_project(pooled), dim=-1)

    def forward(self, history, candidates, features):
        words, cats, subs = features
        hv = self.item(words[history], cats[history], subs[history])
        cv = self.item(words[candidates], cats[candidates], subs[candidates])
        user = self.user(hv, history.ne(0))
        return torch.einsum("bd,bkd->bk", user, cv) / 0.15


def encode(model, features):
    with torch.inference_mode():
        return torch.cat(
            [
                model.item(*(f[i : i + 1024] for f in features))
                for i in range(0, len(features[0]), 1024)
            ]
        ).numpy()


def diversify(order, categories, limit=10, cap=2):
    selected, deferred, counts = [], [], Counter()
    for i in order:
        if len(selected) < limit and counts[categories[i]] < cap:
            selected.append(int(i))
            counts[categories[i]] += 1
        else:
            deferred.append(int(i))
    return selected + deferred
