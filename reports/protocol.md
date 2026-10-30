# Protocol v1 — frozen before experiments
Seed 42. Sort official train by timestamp. Boundaries at 70%/85% timestamps,
with ties moved wholly to later window, define A/B/C. A's last 10% is internal
checkpoint validation. Vocabulary, TF-IDF and popularity use earlier A-fit only.
Three epochs, select lowest internal contrastive loss. B fits standardized logistic
ranker on all logged candidates using frozen tower. C selects popularity, content,
tower or ranker by NDCG@10. No tuning after C. Official validation used as final
holdout, never an official test. All its groups evaluated after model selection.

All logged candidates retained for ranking, sorted by item ID for deterministic ties.
Same-label duplicates deduplicated and counted; conflicting labels fail parsing.
Each positive uses four observed non-clicks from its impression, sampled with
replacement if needed; no in-batch negatives. Single-class groups skipped only in
contrastive training/AUC. Zero-positive groups excluded from NDCG/MRR. MRR means
first-positive reciprocal rank. NDCG uses binary relevance. Scores are not probabilities.

Full-catalog replay: first 200 chronological positive groups, fixed without scores.
Availability: first observation in history/candidates strictly before current timestamp.
This proxy is not publication time; unknown/unavailable positives count as misses.
Recall@50 and pipeline NDCG@10 never insert missed positives. Logged policy caps
categories at two in first ten when alternatives exist, reported separately. Online
policy additionally excludes opened/saved/hidden items; offline task retains them.

Warm=nonempty history, short=1–5, empty=natural no history. New-item group has at
least one candidate absent from A-fit content. Simulated cold start clears history
and all identity; ablations clear history or category features. User-cluster bootstrap:
500 seed-42 resamples, percentile 95% CI of paired mean NDCG@10 difference.
No causal lift claims. Public demo uses original summaries, no MIND text/logs.
Demo events are separate; transfer quality is unmeasured.
