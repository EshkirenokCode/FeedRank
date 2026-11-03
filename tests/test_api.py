import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from feedrank.api import create_app
from feedrank.serving import Service

HEADERS = {"X-FeedRank": "1", "X-FeedRank-QA": "1"}


def client(tmp_path):
    return TestClient(create_app(tmp_path / "db.sqlite", tmp_path / "missing"), headers=HEADERS)


def test_session_events_isolation_idempotency_reset(tmp_path):
    with client(tmp_path) as a:
        assert a.get("/api/recommendations").status_code == 401
        assert a.post("/api/sessions").status_code == 200
        feed = a.get("/api/recommendations").json()
        item = feed["items"][0]["id"]
        event = {
            "event_id": "event-12345",
            "item_id": item,
            "event_type": "save",
            "recommendation_id": feed["recommendation_id"],
        }
        assert a.post("/api/events", json=event).json()["duplicate"] is False
        assert a.post("/api/events", json=event).json()["duplicate"] is True
        assert len(a.get("/api/saved").json()["items"]) == 1
        assert item not in [i["id"] for i in a.get("/api/recommendations").json()["items"]]
        with TestClient(a.app, headers=HEADERS) as b:
            b.post("/api/sessions")
            assert b.get("/api/saved").json()["items"] == []
            event["event_id"] = "event-other"
            assert b.post("/api/events", json=event).status_code == 403
        assert a.delete("/api/session/history").status_code == 200
        assert a.get("/api/saved").json()["items"] == []
        assert a.get("/api/session").json()["interests"] == []
        assert a.post("/api/events", json=event).status_code == 403


def test_preferences_hide_undo_and_csrf(tmp_path):
    with client(tmp_path) as c:
        c.post("/api/sessions")
        assert c.put("/api/session/preferences", json={"interests": ["unknown"]}).status_code == 422
        assert c.put("/api/session/preferences", json={"interests": ["science"]}).status_code == 200
        feed = c.get("/api/recommendations?mode=content").json()
        assert feed["items"][0]["category"] == "science"
        event = {
            "event_id": "hide-12345",
            "item_id": feed["items"][0]["id"],
            "event_type": "hide",
            "recommendation_id": feed["recommendation_id"],
        }
        assert c.post("/api/events", json=event).status_code == 200
        event.update(event_id="undo-12345", event_type="unhide")
        assert c.post("/api/events", json=event).status_code == 200
        assert not c.get("/api/session").json()["hidden"]
        assert (
            c.post(
                "/api/events", json=event, headers={"Origin": "https://elsewhere.example"}
            ).status_code
            == 403
        )
        assert c.post("/api/sessions", headers={"X-FeedRank": "0"}).status_code == 403
        assert c.get("/api/recommendations?mode=bad").status_code == 422
        assert c.post("/api/events", json=event | {"position": 1}).status_code == 422
        assert c.get("/ready").status_code == 503
        assert c.get("/health").status_code == 200
        assert c.post("/api/sessions", content="x" * 9000).status_code == 413


def test_event_retry_concurrent_and_conflict(tmp_path):
    with client(tmp_path) as c:
        c.post("/api/sessions")
        f = c.get("/api/recommendations").json()
        event = {
            "event_id": "concurrent-save",
            "item_id": f["items"][0]["id"],
            "event_type": "save",
            "recommendation_id": f["recommendation_id"],
        }
        with ThreadPoolExecutor(2) as pool:
            responses = list(pool.map(lambda _: c.post("/api/events", json=event), range(2)))
        assert all(r.status_code == 200 for r in responses)
        assert sum(r.json()["duplicate"] for r in responses) == 1
        assert c.post("/api/events", json=event | {"event_type": "hide"}).status_code == 409
        with sqlite3.connect(tmp_path / "db.sqlite") as db:
            assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 1
            assert db.execute("SELECT qa FROM events").fetchone()[0] == 1


def test_real_features_change_after_history(tmp_path):
    service = Service(tmp_path)
    x = service.features([], [])
    after = service.features([service.items[0]["id"]], [])
    assert (x != after).any()
    assert after[0, 1] > 0.99
    f = service.recommend([], [], set(), "personalized")
    assert f["fallback"] and not f["research_ready"]
    assert len({i["id"] for i in f["items"]}) == len(f["items"])


def test_corrupted_manifest_fails_closed(tmp_path):
    (tmp_path / "release.json").write_text(json.dumps({"files": {"../secret": "no"}}))
    service = Service(tmp_path)
    assert not service.ready
    assert "could not be loaded" in service.reason


def test_unsave_restores_unread_but_keeps_opened_history(tmp_path):
    with client(tmp_path) as c:
        c.post("/api/sessions")
        feed = c.get("/api/recommendations").json()
        item = feed["items"][0]["id"]
        event = {"item_id": item, "recommendation_id": feed["recommendation_id"]}
        for event_id, kind in [("save-unread", "save"), ("undo-unread", "unsave")]:
            c.post(
                "/api/events", json=event | {"event_id": event_id, "event_type": kind}
            ).raise_for_status()
        assert item in [i["id"] for i in c.get("/api/recommendations").json()["items"]]
        for event_id, kind in [
            ("open-article", "open"),
            ("save-opened", "save"),
            ("undo-opened", "unsave"),
        ]:
            c.post(
                "/api/events", json=event | {"event_id": event_id, "event_type": kind}
            ).raise_for_status()
        assert item not in [i["id"] for i in c.get("/api/recommendations").json()["items"]]
        assert not c.get("/api/saved").json()["items"]


def test_hidden_restore_read_reload_and_bounded_impressions(tmp_path):
    with client(tmp_path) as c:
        c.post("/api/sessions")
        feed = c.get("/api/recommendations").json()
        hidden, saved = [i["id"] for i in feed["items"][:2]]
        for item, kind in [(hidden, "hide"), (saved, "save")]:
            c.post(
                "/api/events",
                json={
                    "event_id": f"persist-{kind}",
                    "item_id": item,
                    "event_type": kind,
                    "recommendation_id": feed["recommendation_id"],
                },
            ).raise_for_status()
        for n in range(220):
            if n % 50 == 0:
                c.app.state.rate.clear()
            c.get("/api/recommendations").raise_for_status()
        with sqlite3.connect(tmp_path / "db.sqlite") as db:
            assert db.execute("SELECT count(*) FROM served").fetchone()[0] <= 200 * 12 + 48
            before = db.execute("SELECT count(*) FROM events").fetchone()[0]
        item = c.get(f"/api/items/{saved}").json()
        assert item["id"] == saved
        assert item["body"]
        with sqlite3.connect(tmp_path / "db.sqlite") as db:
            assert db.execute("SELECT count(*) FROM events").fetchone()[0] == before
        h = c.get("/api/hidden").json()["items"][0]
        assert h["id"] == hidden
        c.post(
            "/api/events",
            json={
                "event_id": "restore-hidden",
                "item_id": hidden,
                "event_type": "unhide",
                "recommendation_id": h["recommendation_id"],
            },
        ).raise_for_status()
        assert not c.get("/api/hidden").json()["items"]
        assert hidden in [i["id"] for i in c.get("/api/recommendations").json()["items"]]
        own_cookie = c.cookies.get("feedrank")
        c.cookies.clear()
        c.post("/api/sessions")
        assert c.get(f"/api/items/{saved}").status_code == 404
        c.cookies.set("feedrank", own_cookie)
        c.delete("/api/session/history").raise_for_status()
        assert c.get(f"/api/items/{saved}").status_code == 404


def test_expired_session_can_restart_without_reusing_history(tmp_path):
    with client(tmp_path) as c:
        c.post("/api/sessions")
        cookie = c.cookies.get("feedrank")
        with sqlite3.connect(tmp_path / "db.sqlite") as db:
            db.execute("UPDATE sessions SET updated=0")
        assert c.get("/api/session").status_code == 401
        c.post("/api/sessions").raise_for_status()
        assert c.cookies.get("feedrank") != cookie
        assert c.get("/api/session").json() == {"saved": [], "hidden": [], "interests": []}


def test_docs_use_local_assets_and_a_per_request_script_nonce(tmp_path):
    import re

    with client(tmp_path) as c:
        first, second = c.get("/docs"), c.get("/docs")
        assert first.status_code == 200
        nonce = re.search(r'<script nonce="([^"]+)"', first.text)[1]
        assert f"'nonce-{nonce}'" in first.headers["content-security-policy"]
        assert nonce not in second.text
        assert "/api-docs/swagger-ui-bundle.js" in first.text
        assert "cdn.jsdelivr.net" not in first.text
        assert "'unsafe-inline'" not in c.get("/health").headers["content-security-policy"]


def test_corrupt_checkpoint_and_partial_load_preserve_fallback(tmp_path):
    import numpy as np
    import torch

    from feedrank.data import ROOT, sha
    from feedrank.model import Preprocessor, TwoTower, encode

    items = json.loads((ROOT / "catalog/demo.json").read_text())
    prep = Preprocessor.fit(items)
    model = TwoTower(len(prep.vocab), len(prep.categories) + 1, len(prep.subcategories) + 1).eval()
    torch.save(
        {"config": model.config, "preprocessing": prep.state(), "state_dict": model.state_dict()},
        tmp_path / "encoder.pt",
    )
    np.save(tmp_path / "demo-vectors.npy", encode(model, prep.transform(items)))
    (tmp_path / "ranker.json").write_text(
        json.dumps({"mean": [0] * 5, "scale": [1] * 5, "coef": [0] * 5, "intercept": 0})
    )
    (tmp_path / "baselines.json").write_text(
        json.dumps({"tfidf_vocab": {"river": 0}, "idf": [1.0], "prior": 0.0})
    )
    (tmp_path / "selection.json").write_text("{}")
    files = ["encoder.pt", "demo-vectors.npy", "ranker.json", "baselines.json", "selection.json"]

    def manifest():
        (tmp_path / "release.json").write_text(
            json.dumps(
                {
                    "files": {f: sha(tmp_path / f) for f in files},
                    "selected": "ranker",
                    "catalog_sha256": sha(ROOT / "catalog/demo.json"),
                    "model_version": "test",
                }
            )
        )

    manifest()
    loaded = Service(tmp_path)
    clean = Service(tmp_path / "missing")
    assert not loaded.ready
    assert loaded.text.shape == clean.text.shape
    np.testing.assert_allclose(loaded.features(["demo-001"], []), clean.features(["demo-001"], []))
    assert not hasattr(loaded, "model")
    (tmp_path / "encoder.pt").write_bytes(b"broken checkpoint")
    manifest()
    broken = Service(tmp_path)
    assert not broken.ready
    assert np.isfinite(
        [i["score"] for i in broken.recommend([], [], set(), "personalized")["items"]]
    ).all()


def test_popular_mode_does_not_claim_interest_personalization(tmp_path):
    service = Service(tmp_path)
    result = service.recommend([], ["science"], set(), "popular")
    assert all(i["reason"] == "Balanced demo selection" for i in result["items"])


def test_legacy_hidden_impression_is_recovered_from_accepted_event(tmp_path):
    with client(tmp_path) as c:
        c.post("/api/sessions")
        f = c.get("/api/recommendations").json()
        item = f["items"][0]["id"]
        c.post(
            "/api/events",
            json={
                "event_id": "legacy-hide",
                "event_type": "hide",
                "item_id": item,
                "recommendation_id": f["recommendation_id"],
            },
        ).raise_for_status()
        with sqlite3.connect(tmp_path / "db.sqlite") as db:
            db.execute("DELETE FROM served WHERE item=?", (item,))
        restored = c.get("/api/hidden").json()["items"][0]
        assert restored["recommendation_id"] == f["recommendation_id"]
        c.post(
            "/api/events",
            json={
                "event_id": "legacy-restore",
                "event_type": "unhide",
                "item_id": item,
                "recommendation_id": restored["recommendation_id"],
            },
        ).raise_for_status()
        assert not c.get("/api/hidden").json()["items"]
