# Engineering decisions

1. **Content towers, no user-ID embeddings.** A live visitor and a new article can be represented without a training ID. A masked mean history encoder keeps CPU cost small.
2. **Temporal A/B/C.** A fits the encoder and baseline statistics. B trains the ranker on frozen A scores. C selects the serving method. Official validation is the final holdout.
3. **Observed negatives only.** Four non-clicked candidates from the same impression are sampled for each positive. Unseen articles are not labelled as dislikes. Single-class groups are counted and handled explicitly.
4. **Trainable word and category embeddings.** A small 48-wide pooled content encoder projects to normalized 64-dimensional vectors. It offers a clear training path and controllable cost; a large language model is unnecessary here.
5. **Exact retrieval before ranking.** Public catalog vectors are precomputed. Exact top-50 search is easier to validate at this size than an approximate index. Full-catalog replay never adds missed positives.
6. **Separate ranker experiment.** Standardized logistic regression has explicit JSON weights and feature definitions. Its score is not presented as a click probability. C, not the final holdout, determines whether to use it.
7. **Separate public content.** MIND remains a local research dataset. Original evergreen summaries demonstrate interaction without redistributing source articles. Transfer quality remains unmeasured.
8. **Cookie sessions and SQLite WAL.** Opaque server-generated tokens, event-to-recommendation association, transactional idempotency and a single worker cover the intended small demo without collecting identities.
9. **Fail visibly.** Missing or corrupt artifacts lead to 503 readiness and an explicit demo fallback. Serving verifies checksums and encoder/vector agreement, uses safe checkpoint loading and never trains in an HTTP request.
10. **One isolated deployment.** A non-root API image, a small reverse proxy and a persistent session volume have independent resource limits. Training and deployment are separate. No existing production service needs modification.
