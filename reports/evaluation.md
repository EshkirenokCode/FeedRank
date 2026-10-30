# Evaluation status

Research evaluation has not run. There are no MIND benchmark numbers in this release.

On 2026-10-30 the download mirror linked from the official MIND site returned HTTP
401 (gated Hugging Face dataset); the earlier Microsoft Azure endpoint returned
409 (public access disabled). Authorized archives or an approved HF_TOKEN are needed.

The implementation includes temporal A/B/C separation, a held-out internal checkpoint
window, all-candidate ranking, group metrics, user-cluster confidence intervals,
slices, ablations and first-observed catalog replay. Its execution is verified on
an isolated synthetic fixture only. That fixture is not evidence of research quality.
See smoke.json and protocol.md. Once access is supplied, `make download prepare train
evaluate release` creates the measured reports and serving bundle. The holdout lock
prevents an accidental second selection cycle using the same final holdout.

The current application serves an explicit content-based demo fallback. `/ready`
returns 503 until a checked research release is installed. `/health` remains 200.
Public demo summaries and visitor actions are separate from research evaluation.
