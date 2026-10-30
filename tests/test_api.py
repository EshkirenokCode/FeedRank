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
