"""Build dev.jsonl and test.jsonl from source_cases.py + catalog_labels.csv.

    python eval/datasets/build_dataset.py

Derived fields (never hand-edited):
  id                      <category>-<nnn>
  relevant_product_ids    from the *independent* product labels in
                          catalog_labels.csv, never from the system's own tags
  must_not_recommend_ids  products a case forbids (e.g. an allergy)
  split                   dev / test, stratified by category, fixed seed

The build is deterministic: same inputs -> byte-identical outputs.
"""
import csv
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from source_cases import CASES  # noqa: E402

SEED = 42
DEV_FRACTION = 0.4
DEFAULT_AREAS = {"face", "eye"}


def load_catalog():
    with open(os.path.join(HERE, "catalog_labels.csv"), encoding="utf-8") as f:
        labels = {r["product_id"]: r for r in csv.DictReader(f)}
    with open(os.path.join(ROOT, "app", "app_data.json"), encoding="utf-8") as f:
        app = {str(p["product_id"]): p for p in json.load(f)}
    for pid, r in labels.items():
        r["is_skincare"] = r["is_skincare"] == "1"
        r["price"] = float(r["price"])
        r["concern_set"] = {c for c in r["concerns"].split(";") if c}
        r["ingredients_text"] = " ".join(app[pid].get("ingredients", [])).lower()
    return labels


def forbidden_ids(case, catalog):
    rule = case["must_not_recommend"]
    out = set()
    for pid, r in catalog.items():
        text = (r["name"] + " " + r["ingredients_text"]).lower()
        if any(s in r["ingredients_text"] for s in rule.get("ingredient_contains", [])):
            out.add(pid)
        if any(s in text for s in rule.get("text_contains", [])):
            out.add(pid)
    return out


def relevant_ids(case, catalog, forbidden):
    con = case["constraints"]
    areas = {con["area"]} if "area" in con else DEFAULT_AREAS
    wanted = set(case["expected_concerns"])
    out = []
    for pid, r in catalog.items():
        if not r["is_skincare"] or r["area"] not in areas or pid in forbidden:
            continue
        if "product_type" in con and r["product_type"] != con["product_type"]:
            continue
        if wanted and not (r["concern_set"] & wanted):
            continue
        if not wanted and "product_type" not in con:
            continue
        if "form" in con and r["form"] not in con["form"]:
            continue
        if "max_price" in con and not (0 < r["price"] <= con["max_price"]):
            continue
        out.append(pid)
    return sorted(out)


def build():
    catalog = load_catalog()
    rng = random.Random(SEED)
    by_cat = {}
    for case in CASES:
        by_cat.setdefault(case["category"], []).append(dict(case))

    rows, problems = [], []
    for cat, cases in by_cat.items():
        order = list(range(len(cases)))
        rng.shuffle(order)
        n_dev = round(len(cases) * DEV_FRACTION)
        dev_idx = set(order[:n_dev])
        for i, case in enumerate(cases):
            forb = forbidden_ids(case, catalog)
            rel = relevant_ids(case, catalog, forb)
            case["id"] = f"{cat}-{i + 1:03d}"
            case["must_not_recommend_ids"] = sorted(forb)
            case["relevant_product_ids"] = rel if case["should_recommend"] else []
            case["split"] = "dev" if i in dev_idx else "test"
            case["source"] = "synthetic"
            case.pop("must_not_recommend")
            if case["should_recommend"] and not rel:
                problems.append(f"{case['id']}: should_recommend but no relevant products")
            rows.append(case)

    if problems:
        raise SystemExit("Dataset problems:\n  " + "\n  ".join(problems))

    keys = ["id", "split", "category", "query", "expected_concerns", "relevant_product_ids",
            "must_escalate", "should_recommend", "constraints", "must_not_contain",
            "must_not_recommend_ids", "notes", "source"]
    for split in ("dev", "test"):
        path = os.path.join(HERE, f"{split}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                if r["split"] == split:
                    f.write(json.dumps({k: r[k] for k in keys}, ensure_ascii=False) + "\n")

    counts = {}
    for r in rows:
        counts.setdefault(r["category"], {"dev": 0, "test": 0})[r["split"]] += 1
    print(f"{len(rows)} cases")
    for cat, c in counts.items():
        print(f"  {cat:18s} dev {c['dev']:3d}  test {c['test']:3d}")
    return rows


if __name__ == "__main__":
    build()
