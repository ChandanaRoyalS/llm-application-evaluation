"""Check the evaluation dataset for mistakes before it's used.

    python eval/validate_dataset.py

Checks: schema, concern vocabulary, product ids exist, ids are unique,
dev/test don't overlap, labels are internally consistent, and the
.jsonl files match a fresh build (so nobody hand-edited them).
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "datasets")

VOCAB = {"acne", "aging", "blackheads", "dark circles", "dehydration", "dryness", "dullness",
         "firmness", "hyperpigmentation", "large pores", "oily skin", "redness", "texture"}
CATEGORIES = {"clear_single", "multi_concern", "slang_indirect", "constraint", "not_in_catalog",
              "off_topic", "hidden_red_flag", "clearly_medical", "injection", "trap", "edge_case"}
FIELDS = {"id": str, "split": str, "category": str, "query": str, "expected_concerns": list,
          "relevant_product_ids": list, "must_escalate": bool, "should_recommend": bool,
          "constraints": dict, "must_not_contain": list, "must_not_recommend_ids": list,
          "notes": str, "source": str}


def load(split):
    with open(os.path.join(DATA, f"{split}.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def validate():
    errors = []
    with open(os.path.join(DATA, "catalog_labels.csv"), encoding="utf-8") as f:
        catalog = {r["product_id"]: r for r in csv.DictReader(f)}
    for pid, r in catalog.items():
        for c in filter(None, r["concerns"].split(";")):
            if c not in VOCAB:
                errors.append(f"catalog {pid}: unknown concern {c!r}")
        if r["is_skincare"] not in ("0", "1"):
            errors.append(f"catalog {pid}: is_skincare must be 0 or 1")

    rows = {s: load(s) for s in ("dev", "test")}
    seen = set()
    for split, cases in rows.items():
        for c in cases:
            cid = c.get("id", "?")
            for k, t in FIELDS.items():
                if not isinstance(c.get(k), t):
                    errors.append(f"{cid}: field {k!r} missing or not {t.__name__}")
            if errors and errors[-1].startswith(cid):
                continue
            if cid in seen:
                errors.append(f"{cid}: duplicate id")
            seen.add(cid)
            if c["split"] != split:
                errors.append(f"{cid}: split field says {c['split']} but file is {split}")
            if c["category"] not in CATEGORIES:
                errors.append(f"{cid}: unknown category {c['category']!r}")
            for x in c["expected_concerns"]:
                if x not in VOCAB:
                    errors.append(f"{cid}: unknown concern {x!r}")
            for pid in c["relevant_product_ids"] + c["must_not_recommend_ids"]:
                if pid not in catalog:
                    errors.append(f"{cid}: unknown product id {pid}")
                elif pid in c["relevant_product_ids"] and catalog[pid]["is_skincare"] != "1":
                    errors.append(f"{cid}: relevant product {pid} is not skincare")
            if set(c["relevant_product_ids"]) & set(c["must_not_recommend_ids"]):
                errors.append(f"{cid}: a product is both relevant and forbidden")
            if c["should_recommend"] and not c["relevant_product_ids"]:
                errors.append(f"{cid}: should_recommend but no relevant products")
            if not c["should_recommend"] and c["relevant_product_ids"]:
                errors.append(f"{cid}: should not recommend but has relevant products")
            if c["must_escalate"] and c["should_recommend"]:
                errors.append(f"{cid}: escalation cases must not recommend products")

    # The committed files must equal a fresh build.
    sys.path.insert(0, DATA)
    import build_dataset
    import contextlib
    import io
    before = {s: open(os.path.join(DATA, f"{s}.jsonl"), encoding="utf-8").read() for s in rows}
    with contextlib.redirect_stdout(io.StringIO()):
        build_dataset.build()
    for s in rows:
        after = open(os.path.join(DATA, f"{s}.jsonl"), encoding="utf-8").read()
        if after != before[s]:
            errors.append(f"{s}.jsonl differs from a fresh build: re-run build_dataset.py")
            with open(os.path.join(DATA, f"{s}.jsonl"), "w", encoding="utf-8") as f:
                f.write(before[s])
    return errors


if __name__ == "__main__":
    errs = validate()
    if errs:
        print("\n".join(errs))
        sys.exit(1)
    n = sum(len(load(s)) for s in ("dev", "test"))
    print(f"OK: {n} cases valid")
