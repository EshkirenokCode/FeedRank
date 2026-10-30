# Interview notes

## What PyTorch learns

An article becomes a list of word and category numbers. Embeddings turn them into
small trainable vectors. Pooling and a projection produce one normalized article
vector. Earlier reads form a user vector. Similar user and article vectors get a
higher score. A loss compares a clicked item with observed non-clicks. Gradients tell
the optimizer how to change the weights. Minibatches repeat that process. A separate
internal time window selects the checkpoint, so the final holdout stays untouched.

A new article needs text and a category, not an ID that existed during training.
A new visitor needs history or explicit interests, not a learned user identity.

## Negative sampling

A positive is a recorded click. A negative here means an article shown in that same
impression without a recorded click. We sample four such items per positive to keep
training small. They are not universal dislikes, and an unshown article is not a
known negative. Every logged candidate is retained during ranking evaluation.

## Temporal leakage

Leakage is information from the answer or future getting into a feature. An example
would be using tomorrow's click count to rank an article today. Another would be
training a ranker on scores from an encoder already fitted to the same outcomes.
FeedRank freezes the A encoder before scoring B for ranker training. Baseline counts,
vocabulary and text normalization also come from A-fit. C selects the method. The
final official validation is opened only after that selection is frozen.

## Retrieval and ranking

Retrieval searches a large set cheaply using vector similarity. Ranking considers a
smaller candidate set with additional features. If retrieval misses a clicked item,
ranking cannot recover it. That is why logged-candidate ranking and catalog recall
are different measurements. The catalog replay uses earlier first-observed times as
a conservative availability proxy; those times are not article publication dates.

## Cold start

Without history, the service uses a balanced prior. Selected interests add explicit
category information. With a few reads, content similarity and the history vector
become available. A new article can pass through the same content encoder. Unknown
words map to an unknown token, and padding never contributes to the history mean.
These mechanisms do not themselves prove new-user or new-item quality; evaluation
needs clearly defined slices and a simulated empty-history check.

## What the metrics mean

NDCG@10 rewards relevant articles near the top and accounts for several clicks.
MRR measures how soon the first positive appears. Group AUC compares scores of
positives and negatives within an impression. Undefined groups are excluded only
from the metric that cannot use them, and their counts remain visible. Confidence
intervals resample users, because several impressions from one person are related.

Offline metrics do not establish satisfaction, retention or a causal gain in clicks.
The public demo has original summaries; success on MIND would not prove that the
model transfers to that collection. A score is not automatically a click probability.

## Current evidence

The optimizer, checkpoint round-trip, reproducible CPU fixture, ranker fit, evaluator,
serving artifact, event isolation and changing session vectors are tested. Full MIND
training and measured research quality remain pending dataset access. Be direct about
that distinction in an interview.
