"""Executed only inside the isolated synthetic smoke root."""

import sqlite3

from fastapi.testclient import TestClient

from feedrank.api import create_app
from feedrank.data import ROOT

with TestClient(
    create_app(ROOT / "runtime/test.sqlite"), headers={"X-FeedRank": "1", "X-FeedRank-QA": "1"}
) as c:
    assert c.get("/ready").status_code == 200
    c.post("/api/sessions").raise_for_status()
    c.put("/api/session/preferences", json={"interests": ["science"]}).raise_for_status()
    f = c.get("/api/recommendations").json()
    assert f["research_ready"]
    item = f["items"][0]["id"]
    before = c.app.state.service.features([], ["science"])
    e = {
        "event_id": "release-smoke-open",
        "item_id": item,
        "event_type": "open",
        "recommendation_id": f["recommendation_id"],
    }
    c.post("/api/events", json=e).raise_for_status()
    after = c.app.state.service.features([item], ["science"])
    assert abs(before[:, 0] - after[:, 0]).max() > 1e-6
    assert item not in [i["id"] for i in c.get("/api/recommendations").json()["items"]]
    with sqlite3.connect(ROOT / "runtime/test.sqlite") as db:
        assert db.execute("SELECT count(*) FROM events WHERE qa=1").fetchone()[0] == 1
print("Trained artifact → API → changed user representation: passed (synthetic fixture only).")
