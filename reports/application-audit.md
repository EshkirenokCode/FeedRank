# Application audit — 2026-11-04

## Fixed

| Issue | Change | Evidence |
|---|---|---|
| Undoing Save left an unread item in history, permanently excluding it from the feed | Unsave removes the save-only history signal; a genuine Open remains in history | API regression and browser Save → Undo → item returns |
| Hidden reads could only be restored through a short-lived toast | Settings links to a persistent Hidden reads page with Restore actions | Browser reload of Hidden reads, then restore on desktop and mobile |
| Reload and browser navigation lost the active article or list | Explicit hash routes, browser history and session-scoped article recovery | Browser Open → Reload → Back → Forward; four navigation tests |
| An expired session offered an ineffective retry loop | A 401 has an explicit new-session recovery action; initial load failures no longer imply an empty list | API expiry/restart regression; frontend type check and error handling |
| Partial model loading could replace the fallback's TF-IDF state before failing | Loading restores the complete original baseline on failure, checks finite priors/IDF and catches malformed checkpoints in safe mode | Invalid prior and corrupt checkpoint regressions; fixture release smoke |
| Swagger's external/inline scripts were blocked by the application CSP | Self-hosted pinned UI assets, per-request nonce, no external validator; same-origin request header is supplied for Try it out | Browser POST /api/sessions returns 200 with no console errors; HTTP assets smoke |
| Served-impression storage grew with every refresh | Retain 200 recent recommendation groups and one durable association per item | 220-request bounded-retention regression; saved/hidden access remains usable |
| Older hidden reads could have already lost their served record | Recover the original impression provenance from the accepted server event, scoped to the owning session | Legacy-pruning regression; recorded action time is reused for the association and no new event is logged |
| Popular mode claimed category personalization it did not use | Interest explanations are restricted to methods that use those features | Popular-mode regression |

The selected method now survives a reload within the browser session. The skip link
moves keyboard focus without changing the article route. Unknown or unavailable
read links show a recoverable error, rather than a spinner or another session's content.

The benchmark command also accepts the local Docker endpoint, rejects remote load-test
targets, paces requests below the reverse proxy limit and labels the memory scope.
The synthetic smoke sets its import path explicitly to the current checkout.

## Verification

- 21 Python tests and four frontend tests pass.
- TypeScript/Vite production build and formatting/lint checks pass.
- Docker API and proxy are healthy; HTTP smoke includes local Swagger assets.
- A repeated synthetic training run still produces matching checkpoint checksums.
  Its trained bundle loads in the API and session feedback changes the user vector.
- Browser QA covers article reload/back/forward, method persistence, Save/Undo,
  hidden restoration after reload, mobile use, invalid-read recovery and reset.
- The current local Docker proxy completed 300 measured requests;
  p50 20.03 ms, p95 22.86 ms. This is fallback-mode,
  one-client latency, not learned-model performance or a production SLA.
- Session expiry is exercised through the API regression. A live visitor session was
  not expired in the browser to simulate the failure.

## Remaining limits

MIND research training and final holdout evaluation are still pending data access.
Synthetic integration checks do not establish recommendation quality. Public demo
content has no measured item popularity and no established transfer quality.

The application remains a small single-worker SQLite demo. It has not been deployed
as public HTTPS or subjected to a production load test. No online lift is claimed.
