import sys
import uuid

import httpx

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
with httpx.Client(base_url=base, headers={"X-FeedRank": "1", "X-FeedRank-QA": "1"}) as c:
    assert c.get("/health").status_code == 200
    assert c.get("/").status_code == 200
    assert c.post("/api/sessions").status_code == 200
    response = c.get("/api/recommendations")
    response.raise_for_status()
    feed = response.json()
    item = feed["items"][0]["id"]
    payload = {
        "event_id": str(uuid.uuid4()),
        "item_id": item,
        "event_type": "save",
        "recommendation_id": feed["recommendation_id"],
    }
    assert c.post("/api/events", json=payload).status_code == 200
    assert c.post("/api/events", json=payload).json()["duplicate"]
    assert item in [i["id"] for i in c.get("/api/saved").json()["items"]]
    assert c.delete("/api/session/history").status_code == 200
    assert not c.get("/api/saved").json()["items"]
    print("HTTP smoke passed; model ready:", feed["research_ready"])
