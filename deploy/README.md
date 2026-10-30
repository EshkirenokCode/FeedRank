# Deployment

Use a separate host or an agreed isolated environment. This repository does not
change any existing service, DNS, firewall, database or reverse proxy.

## Local container

```sh
docker compose up --build -d --wait
curl http://127.0.0.1:8080/health
curl -i http://127.0.0.1:8080/ready
python scripts/http_smoke.py http://127.0.0.1:8080
```

The proxy listens only on loopback. The API runs as UID 10001 with a read-only root,
one CPU, 1 GiB RAM and a 64 MiB temporary directory. SQLite has its own volume. A
small proxy request limit complements the per-session single-process limit. No
training or dataset download occurs at serving startup.

A missing research bundle means readiness 503 and explicit demo fallback. The
container process health remains 200. A production readiness check should require
200 before presenting the research model as installed.

## Public HTTPS

Public deployment needs a dedicated host/account and a domain. No public deployment
or hostname is claimed until those are available and checked. On a dedicated host:

1. Clone the repository and install the verified serving release; never copy `data/`.
2. Set `PUBLIC_ORIGIN=https://your-domain.example` and `COOKIE_SECURE=1` in a local
   untracked environment file. The example domain is a placeholder, not a live demo.
3. Build and start the same Compose stack. Put a maintained HTTPS reverse proxy in
   front of `127.0.0.1:8080`, preserving `Host` and forwarding the original scheme.
   For Caddy on the dedicated host, the site block is simply your actual hostname
   with `reverse_proxy 127.0.0.1:8080`. Caddy obtains and renews certificates.
4. Check HTTPS `/`, `/docs`, `/health`, `/ready`, save/reset, cookie Secure/HttpOnly /
   SameSite, and cross-origin rejection. Check that `/api/evaluation` matches the
   release reports and that no raw data path is exposed.
5. Keep one API worker. SQLite WAL and the in-memory limiter assume one process.
   Enable host disk monitoring, rotate container logs, and retain a daily session backup
   only if needed. Default session expiry is seven days; no visitor identities collected.

Proxy headers are trusted because the API has no host-published port and the only
public entry point is the reverse proxy. Do not publish port 8000 directly with this
configuration. If introducing additional proxies, restrict the trusted network.

## Update and rollback

Build an immutable image per commit, for example `feedrank:<commit>`, and keep the
previous image. The release manifest binds encoder, preprocessing, ranker and vectors;
replace the whole bundle. Check readiness and a QA session before switching traffic.
Rollback by restoring the previous image and restarting only FeedRank. Do not remove
the `sessions` volume. A model rollback does not require deleting session history.

Use SQLite's backup API (or `VACUUM INTO` during a controlled maintenance window) for
consistent snapshots; do not copy a live WAL database file alone. The v1 schema is
created idempotently and recorded in `schema_version`. Future schema changes need
explicit migrations with backup and rollback tests.

Stop local containers with `docker compose down`; this retains session data. Never
add `--volumes` unless deliberately discarding this demo's sessions.
