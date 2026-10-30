"""Isolated synthetic integration run. Never a substitute for MIND evaluation."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="feedrank-smoke-") as directory:
    d = Path(directory)
    for folder in ["data", "artifacts", "reports", "catalog"]:
        (d / folder).mkdir()
    catalog = json.loads((root / "catalog/demo.json").read_text())
    (d / "catalog/demo.json").write_text(json.dumps(catalog))
    rows = []
    for n in range(480):
        cat = n % 8
        positive = cat * 6 + n // 8 % 6
        history = (
            [catalog[cat * 6 + (n // 8 + offset) % 6]["id"] for offset in [1, 2, 3]]
            if n % 13
            else []
        )
        candidates = sorted({positive, *[((cat + j) % 8) * 6 + (n + j) % 6 for j in range(1, 6)]})
        rows.append(
            {
                "id": str(n),
                "user": f"u{n % 31}",
                "time": (datetime(2019, 11, 1) + timedelta(minutes=n)).isoformat(),
                "history": history,
                "items": [catalog[i]["id"] for i in candidates],
                "labels": [int(i == positive) for i in candidates],
                "duplicate_candidates": 0,
            }
        )
    splits = {
        "A_fit": rows[:280],
        "A_validation": rows[280:320],
        "B": rows[320:380],
        "C": rows[380:430],
        "holdout": rows[430:],
    }
    (d / "data/prepared.json").write_text(
        json.dumps({"items": {x["id"]: x for x in catalog}, "splits": splits})
    )
    shutil.copyfile(root / "reports/protocol.md", d / "reports/protocol.md")
    (d / "reports/data-manifest.json").write_text(json.dumps({"dataset": "synthetic smoke only"}))
    env = os.environ | {"FEEDRANK_ROOT": str(d)}
    subprocess.run([sys.executable, "-m", "feedrank.train"], check=True, cwd=root, env=env)
    checksum = hashlib.sha256((d / "artifacts/encoder.pt").read_bytes()).hexdigest()
    subprocess.run([sys.executable, "-m", "feedrank.train"], check=True, cwd=root, env=env)
    assert checksum == hashlib.sha256((d / "artifacts/encoder.pt").read_bytes()).hexdigest()
    subprocess.run([sys.executable, "-m", "feedrank.evaluate"], check=True, cwd=root, env=env)
    shutil.copyfile(root / "reports/protocol.md", d / "reports/protocol.md")
    (d / "reports/data-manifest.json").write_text(json.dumps({"dataset": "synthetic smoke only"}))
    subprocess.run([sys.executable, "-m", "feedrank.release"], check=True, cwd=root, env=env)
    subprocess.run([sys.executable, "scripts/release_smoke.py"], check=True, cwd=root, env=env)
    training = json.loads((d / "reports/training.json").read_text())
    assert training["losses"][-1]["train"] < training["losses"][0]["train"]
    result = {
        "status": "passed",
        "dataset": "synthetic category-consistent fixture, not MIND",
        "train_losses": [e["train"] for e in training["losses"]],
        "checks": [
            "optimizer and minibatches",
            "repeated CPU training checkpoint checksum matches",
            "trained release loads in API and events change user vectors",
            "checkpoint selection and reload",
            "frozen B ranker",
            "C selection before holdout",
            "logged metrics and full-catalog miss accounting",
        ],
    }
    (root / "reports/smoke.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
