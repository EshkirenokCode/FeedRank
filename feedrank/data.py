import csv
import hashlib
import json
import os
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(os.environ.get("FEEDRANK_ROOT", Path(__file__).resolve().parents[1]))
DATA = ROOT / "data"
REPORTS = ROOT / "reports"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def download():
    DATA.mkdir(exist_ok=True)
    manifest = {
        "parser": "mind-tsv-v1",
        "source": "https://msnews.github.io/",
        "mirror_revision": "0f871bdfd1ac4029324a48722ec6d52d714ebf27",
        "license": "https://github.com/msnews/MIND/blob/master/MSR%20License_Data.pdf",
        "retrieved_utc": datetime.now(UTC).isoformat(),
        "files": {},
    }
    for split, suffix in [("train", "train"), ("holdout", "dev")]:
        url = f"https://huggingface.co/datasets/yjw1029/MIND/resolve/0f871bdfd1ac4029324a48722ec6d52d714ebf27/MINDsmall_{suffix}.zip"
        archive = DATA / f"{split}.zip"
        if not archive.exists():
            tmp = archive.with_suffix(".part")
            token = os.environ.get("HF_TOKEN")
            req = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {token}"} if token else {}
            )
            import shutil

            with urllib.request.urlopen(req, timeout=60) as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
            tmp.rename(archive)
        dest = DATA / split
        dest.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            for name in ["news.tsv", "behaviors.tsv"]:
                with z.open(name) as src, open(dest / name, "wb") as out:
                    import shutil

                    shutil.copyfileobj(src, out)
        manifest["files"][split] = {
            "url": url,
            "archive_sha256": sha(archive),
            "extracted": {n: sha(dest / n) for n in ["news.tsv", "behaviors.tsv"]},
        }
        print("Downloaded", split, flush=True)
    write(REPORTS / "data-manifest.json", manifest)


def news():
    items = {}
    duplicate = conflict = 0
    for split in ["train", "holdout"]:
        with open(DATA / split / "news.tsv") as f:
            for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
                if len(row) != 8:
                    raise ValueError("Expected eight news columns")
                key, cat, sub, title, abstract = row[:5]
                value = {
                    "id": key,
                    "category": cat,
                    "subcategory": sub,
                    "title": title,
                    "abstract": abstract,
                }
                if key in items:
                    duplicate += 1
                    conflict += items[key] != value
                else:
                    items[key] = value
    return items, {"repeated_metadata_ids": duplicate, "conflicting_metadata": conflict}


def behaviors(split):
    result = []
    with open(DATA / split / "behaviors.tsv") as f:
        for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            if len(row) != 5:
                raise ValueError("Expected five behavior columns")
            iid, user, ts, hist, raw = row
            pairs = {}
            duplicates = 0
            for part in raw.split():
                item, label = part.rsplit("-", 1)
                y = int(label)
                if y not in (0, 1) or (item in pairs and pairs[item] != y):
                    raise ValueError("Invalid/conflicting candidate")
                duplicates += item in pairs
                pairs[item] = y
            ids = sorted(pairs)
            result.append(
                {
                    "id": iid,
                    "user": user,
                    "time": datetime.strptime(ts, "%m/%d/%Y %I:%M:%S %p").isoformat(),
                    "history": hist.split(),
                    "items": ids,
                    "labels": [pairs[x] for x in ids],
                    "duplicate_candidates": duplicates,
                }
            )
    return sorted(result, key=lambda r: (r["time"], r["id"]))


def temporal(rows, fractions=(0.7, 0.85)):
    boundaries = [rows[int(len(rows) * f)]["time"] for f in fractions]
    return [
        [r for r in rows if r["time"] < boundaries[0]],
        [r for r in rows if boundaries[0] <= r["time"] < boundaries[1]],
        [r for r in rows if r["time"] >= boundaries[1]],
    ]


def describe(rows, items):
    ids = {i for r in rows for i in r["items"] + r["history"]}
    return {
        "groups": len(rows),
        "users": len({r["user"] for r in rows}),
        "items": len(ids),
        "candidates": sum(len(r["items"]) for r in rows),
        "positive_labels": sum(sum(r["labels"]) for r in rows),
        "empty_history": sum(not r["history"] for r in rows),
        "missing_metadata_ids": len(ids - items.keys()),
        "zero_positive": sum(not any(r["labels"]) for r in rows),
        "zero_negative": sum(all(r["labels"]) for r in rows),
        "duplicate_candidates": sum(r["duplicate_candidates"] for r in rows),
        "duplicate_impression_ids": len(rows) - len({r["id"] for r in rows}),
        "time_range": [rows[0]["time"], rows[-1]["time"]],
        "history_quantiles": np.quantile(
            [len(r["history"]) for r in rows], [0, 0.5, 0.9, 1]
        ).tolist(),
        "candidate_quantiles": np.quantile(
            [len(r["items"]) for r in rows], [0, 0.5, 0.9, 1]
        ).tolist(),
    }


def prepare():
    items, meta = news()
    train, holdout = behaviors("train"), behaviors("holdout")
    a, b, c = temporal(train)
    fit, _, val = temporal(a, (0.9, 0.9))
    splits = {"A_fit": fit, "A_validation": val, "B": b, "C": c, "holdout": holdout}
    audit = {k: describe(v, items) for k, v in splits.items()}
    audit["metadata"] = meta | {
        "items": len(items),
        "empty_title": sum(not x["title"] for x in items.values()),
        "empty_abstract": sum(not x["abstract"] for x in items.values()),
    }
    fit_users = {r["user"] for r in fit}
    fit_items = {i for r in fit for i in r["items"] + r["history"]}
    audit["overlap"] = {
        k: {
            "users_with_A_fit": len({r["user"] for r in rows} & fit_users),
            "items_with_A_fit": len({i for r in rows for i in r["items"]} & fit_items),
        }
        for k, rows in splits.items()
    }
    write(REPORTS / "audit.json", audit)
    write(DATA / "prepared.json", {"items": items, "splits": splits})
    print(json.dumps(audit, indent=2), flush=True)


if __name__ == "__main__":
    import sys

    {"download": download, "prepare": prepare}[sys.argv[1]]()
