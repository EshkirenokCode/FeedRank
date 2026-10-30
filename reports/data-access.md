# Source and access

- Dataset: [MIND-small](https://msnews.github.io/), Wu et al., ACL 2020.
- [Format](https://github.com/msnews/msnews.github.io/blob/master/assets/doc/introduction.md).
- [Microsoft Research License Terms](https://github.com/msnews/MIND/blob/master/MSR%20License_Data.pdf), read before attempting download.
- Current official-site download destination: `yjw1029/MIND` on Hugging Face.
- Mirror revision observed: `0f871bdfd1ac4029324a48722ec6d52d714ebf27`.
- 2026-10-30: mirror requires authenticated, approved access (401); former Microsoft blob storage disables public access (409).

The license permits non-commercial research, analysis, personal experiments and
public demonstrations, and prohibits dataset redistribution. Results may be published
without a material portion of the dataset. The code license does not cover MIND.

No raw logs, source article catalog, archives or research item vectors are committed
or exposed through API. No expired article URLs are crawled. The 48 public summaries
are independently written demo content. Their synthetic fixtures are for software
verification only; no MIND quality or real audience behaviour is inferred from them.

With authorized access, download uses the official-site-linked mirror, records archive
and extracted TSV SHA-256, parser version and retrieval time in data-manifest.json.
Only news.tsv and behaviors.tsv are extracted. No dataset-provided scripts execute.
Local archives can be placed at `data/train.zip` and `data/holdout.zip` before running
the download command; they receive the same hashes and schema audit. Their provenance
must be the authorized MIND-small download, not a modified third-party dataset.
