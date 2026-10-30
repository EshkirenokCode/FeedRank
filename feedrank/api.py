import hashlib
import json
import logging
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .data import ROOT
from .serving import Service

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("feedrank")


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interests: list[str] = Field(max_length=8)


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{8,80}$")
    item_id: str = Field(pattern=r"^demo-\d{3}$")
    recommendation_id: str = Field(min_length=16, max_length=64)
    event_type: Literal["open", "save", "hide", "unsave", "unhide"]


def create_app(db_path=None, artifacts=None):
    path = Path(db_path or os.environ.get("FEEDRANK_DB", ROOT / "runtime/sessions.sqlite"))
    path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def db():
        con = sqlite3.connect(path, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    @asynccontextmanager
    async def lifespan(app):
        app.state.service = Service(artifacts)
        with db() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript("""
            CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO schema_version VALUES(1);
            CREATE TABLE IF NOT EXISTS sessions(
                token TEXT PRIMARY KEY, created REAL, updated REAL, qa INTEGER,
                interests TEXT DEFAULT '[]', history TEXT DEFAULT '[]', saved TEXT DEFAULT '[]', hidden TEXT DEFAULT '[]');
            CREATE TABLE IF NOT EXISTS served(
                recommendation TEXT, token TEXT REFERENCES sessions(token) ON DELETE CASCADE,
                item TEXT, position INTEGER, mode TEXT, model TEXT, policy TEXT, created REAL,
                PRIMARY KEY(recommendation,item));
            CREATE TABLE IF NOT EXISTS events(
                event_id TEXT PRIMARY KEY, token TEXT REFERENCES sessions(token) ON DELETE CASCADE,
                item TEXT, event_type TEXT, recommendation TEXT, created REAL,
                mode TEXT, model TEXT, policy TEXT, position INTEGER, qa INTEGER);
            CREATE INDEX IF NOT EXISTS served_session ON served(token, created);
            CREATE INDEX IF NOT EXISTS events_session ON events(token);
            """)
            con.execute("DELETE FROM sessions WHERE updated < ?", (time.time() - 7 * 86400,))
        app.state.counters = {
            "requests": 0,
            "errors": 0,
            "fallback": 0,
            "empty": 0,
            "event_rejects": 0,
        }
        app.state.rate = {}
        yield

    app = FastAPI(title="FeedRank", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def guard(request, call_next):
        started = time.perf_counter()
        if len(await request.body()) > 8192:
            return JSONResponse({"detail": "Request too large"}, 413)
        if request.method in ("POST", "PUT", "DELETE"):
            origin = request.headers.get("origin")
            expected = os.environ.get("PUBLIC_ORIGIN", str(request.base_url).rstrip("/"))
            if (
                request.headers.get("x-feedrank") != "1"
                or (origin and origin != expected)
                or request.headers.get("sec-fetch-site") == "cross-site"
            ):
                return JSONResponse({"detail": "Same-origin request header required"}, 403)
        # One process, bounded in-memory rate buckets; reverse proxy adds an IP limit.
        key = hashlib.sha256(
            (request.cookies.get("feedrank", "") or request.client.host).encode()
        ).hexdigest()
        minute = int(time.time() // 60)
        buckets = request.app.state.rate
        if len(buckets) > 2048:
            buckets.clear()
        previous, count = buckets.get(key, (minute, 0))
        count = count + 1 if previous == minute else 1
        buckets[key] = (minute, count)
        if count > 180:
            return JSONResponse(
                {"detail": "Too many requests. Try again in a minute."},
                429,
                headers={"Retry-After": "60"},
            )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
        counters = request.app.state.counters
        counters["requests"] += 1
        counters["errors"] += response.status_code >= 400
        log.info(
            json.dumps(
                {
                    "path": request.url.path,
                    "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    "model": request.app.state.service.version,
                }
            )
        )
        return response

    def session(request, con):
        raw = request.cookies.get("feedrank", "")
        token = hashlib.sha256(raw.encode()).hexdigest()
        row = con.execute(
            "SELECT * FROM sessions WHERE token=? AND updated>?", (token, time.time() - 7 * 86400)
        ).fetchone()
        if row is None:
            raise HTTPException(401, "Start a new session")
        return dict(row)

    @app.post("/api/sessions")
    def new_session(request: Request, response: Response):
        with db() as con:
            try:
                row = session(request, con)
            except HTTPException:
                row = None
            if row:
                return {"interests": json.loads(row["interests"]), "qa": bool(row["qa"])}
            raw = secrets.token_urlsafe(32)
            token = hashlib.sha256(raw.encode()).hexdigest()
            qa = request.headers.get("x-feedrank-qa") == "1"
            con.execute(
                "INSERT INTO sessions(token,created,updated,qa) VALUES(?,?,?,?)",
                (token, time.time(), time.time(), qa),
            )
            response.set_cookie(
                "feedrank",
                raw,
                httponly=True,
                secure=os.environ.get("COOKIE_SECURE") == "1",
                samesite="strict",
                max_age=7 * 86400,
            )
            return {"interests": [], "qa": qa}

    @app.get("/api/session")
    def current(request: Request):
        with db() as con:
            row = session(request, con)
            return {k: json.loads(row[k]) for k in ["interests", "saved", "hidden"]}

    @app.put("/api/session/preferences")
    def preferences(body: Preferences, request: Request):
        interests = sorted(set(body.interests))
        if any(c not in app.state.service.categories for c in interests):
            raise HTTPException(422, "Unknown interest")
        with db() as con:
            row = session(request, con)
            con.execute(
                "UPDATE sessions SET interests=?,updated=? WHERE token=?",
                (json.dumps(interests), time.time(), row["token"]),
            )
        return {"interests": interests}

    @app.get("/api/recommendations")
    def recommendations(
        request: Request, mode: Literal["popular", "content", "personalized"] = "personalized"
    ):
        with db() as con:
            row = session(request, con)
            excluded = set(
                json.loads(row["saved"]) + json.loads(row["hidden"]) + json.loads(row["history"])
            )
            result = app.state.service.recommend(
                json.loads(row["history"]), json.loads(row["interests"]), excluded, mode
            )
            rid = secrets.token_urlsafe(18)
            for position, item in enumerate(result["items"], 1):
                con.execute(
                    "INSERT INTO served VALUES(?,?,?,?,?,?,?,?)",
                    (
                        rid,
                        row["token"],
                        item["id"],
                        position,
                        mode,
                        result["model_version"],
                        result["policy_version"],
                        time.time(),
                    ),
                )
            con.execute("UPDATE sessions SET updated=? WHERE token=?", (time.time(), row["token"]))
            # Keep a bounded recommendation history; existing saved actions retain a valid association.
            con.execute(
                "DELETE FROM served WHERE token=? AND created<? AND item NOT IN (SELECT value FROM json_each(?))",
                (row["token"], time.time() - 86400, row["saved"]),
            )
        app.state.counters["fallback"] += result["fallback"] is not None
        app.state.counters["empty"] += not result["items"]
        return result | {"recommendation_id": rid}

    @app.post("/api/events")
    def event(body: Event, request: Request):
        with db() as con:
            # Serialize state transitions, including concurrent retries and preference changes.
            con.execute("BEGIN IMMEDIATE")
            row = session(request, con)
            old = con.execute("SELECT * FROM events WHERE event_id=?", (body.event_id,)).fetchone()
            if old:
                if (old["token"], old["item"], old["event_type"], old["recommendation"]) != (
                    row["token"],
                    body.item_id,
                    body.event_type,
                    body.recommendation_id,
                ):
                    raise HTTPException(409, "Event ID already used")
                return {"accepted": True, "duplicate": True}
            served = con.execute(
                "SELECT * FROM served WHERE recommendation=? AND token=? AND item=?",
                (body.recommendation_id, row["token"], body.item_id),
            ).fetchone()
            if not served:
                app.state.counters["event_rejects"] += 1
                raise HTTPException(403, "Item was not served to this session")
            if (
                con.execute(
                    "SELECT count(*) FROM events WHERE token=?", (row["token"],)
                ).fetchone()[0]
                >= 5000
            ):
                raise HTTPException(429, "Session event limit reached. Reset history to continue.")
            history, saved, hidden = [json.loads(row[k]) for k in ["history", "saved", "hidden"]]
            if body.event_type in ("open", "save"):
                history = [i for i in history if i != body.item_id] + [body.item_id]
            if body.event_type == "save" and body.item_id not in saved:
                saved.append(body.item_id)
            if body.event_type == "hide" and body.item_id not in hidden:
                hidden.append(body.item_id)
            if body.event_type == "unsave":
                saved = [i for i in saved if i != body.item_id]
            if body.event_type == "unhide":
                hidden = [i for i in hidden if i != body.item_id]
            con.execute(
                "UPDATE sessions SET history=?,saved=?,hidden=?,updated=? WHERE token=?",
                (
                    json.dumps(history[-100:]),
                    json.dumps(saved),
                    json.dumps(hidden),
                    time.time(),
                    row["token"],
                ),
            )
            con.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    body.event_id,
                    row["token"],
                    body.item_id,
                    body.event_type,
                    body.recommendation_id,
                    time.time(),
                    served["mode"],
                    served["model"],
                    served["policy"],
                    served["position"],
                    row["qa"],
                ),
            )
        return {"accepted": True, "duplicate": False}

    @app.get("/api/saved")
    def saved(request: Request):
        with db() as con:
            row = session(request, con)
            items = []
            for i in json.loads(row["saved"]):
                served = con.execute(
                    "SELECT recommendation FROM served WHERE token=? AND item=? ORDER BY created DESC LIMIT 1",
                    (row["token"], i),
                ).fetchone()
                if i in app.state.service.index and served:
                    items.append(
                        app.state.service.items[app.state.service.index[i]]
                        | {"recommendation_id": served[0]}
                    )
        return {"items": items}

    @app.delete("/api/session/history")
    def reset(request: Request):
        with db() as con:
            con.execute("BEGIN IMMEDIATE")
            row = session(request, con)
            con.execute("DELETE FROM events WHERE token=?", (row["token"],))
            con.execute("DELETE FROM served WHERE token=?", (row["token"],))
            con.execute(
                "UPDATE sessions SET history='[]',saved='[]',hidden='[]',interests='[]',updated=? WHERE token=?",
                (time.time(), row["token"]),
            )
        return {"reset": True}

    @app.get("/api/evaluation")
    def evaluation():
        report = ROOT / "reports/metrics.json"
        if report.exists():
            data = json.loads(report.read_text())
            return {
                "status": "measured",
                "selected": data["selected"],
                "C": data["C"]["metrics"],
                "holdout": data["holdout"]["metrics"],
                "ci": data["holdout"]["ranker_minus_content_ci"],
                "retrieval": data["retrieval"],
                "groups": data["holdout"]["groups"],
                "protocol": "Official validation used as final holdout; not an official test.",
            }
        return {
            "status": "awaiting_data",
            "message": "MIND access is required before research training and evaluation. No benchmark results are claimed.",
            "protocol": "Temporal A/B/C separation; official validation reserved as final holdout.",
        }

    @app.get("/api/catalog-info")
    def catalog_info():
        return {
            "categories": app.state.service.categories,
            "items": len(app.state.service.items),
            "source": "Original demo summaries. Not a current news service.",
        }

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        s = app.state.service
        return JSONResponse(
            {"ready": s.ready, "model_version": s.version, "reason": s.reason},
            200 if s.ready else 503,
        )

    @app.get("/api/diagnostics")
    def diagnostics():
        # Operational counts only: no session IDs, IP addresses or visitor analytics.
        return app.state.counters | {"model_version": app.state.service.version}

    dist = ROOT / "frontend/dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(dist / "index.html")

    return app


app = create_app()
