"""Retrieval-only check: concern detection + retrieval on a split, no LLM calls.

    python eval/retrieval_check.py                 # dev, pipeline v2 vs v3
    python eval/retrieval_check.py --split smoke

Free and fast (no token needed), so a retrieval change can be measured before any
paid run. Reports, on the cases that should get products, how often the top-5
retrieved products break a code check (H1 wrong type, H2 not skincare / wrong
area, H3 over budget), hit@5, and how often nothing is retrieved; and, on the
cases that should get none because nothing fits (constraint cases with
should_recommend = false), how often nothing is retrieved, as required.
The test split is locked, as for run_eval.py.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "judge"))

from code_checks import code_fails, load_catalog_labels  # noqa: E402
from score import load_cases  # noqa: E402


def measure(cases, labels, retrieval, detect):
    rows = []
    for c in cases:
        concerns, _ = detect(c["query"])
        ids = retrieval(c["query"], concerns) if concerns else []
        f = code_fails(c, ids, "", labels)["helpful"]
        rows.append({"id": c["id"], "category": c["category"], "ids": ids,
                     "H1": "H1" in f, "H2": "H2" in f, "H3": "H3" in f,
                     "hit": bool(set(ids) & set(c["relevant_product_ids"])),
                     "none": not ids, "rec": c["should_recommend"], "constraints": c.get("constraints") or {}})
    return rows


def summarize(rows):
    rec = [r for r in rows if r["rec"]]
    con = [r for r in rec if r["constraints"]]
    imp = [r for r in rows if not r["rec"] and r["category"] == "constraint"]
    pct = lambda xs, k: (sum(r[k] for r in xs), len(xs))  # noqa: E731
    return {
        "should recommend": {k: pct(rec, k) for k in ("H1", "H2", "H3", "hit", "none")},
        "with a constraint": {k: pct(con, k) for k in ("H1", "H2", "H3", "hit", "none")},
        "nothing fits (none required)": {"none": pct(imp, "none")},
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "smoke", "test"], default="dev")
    ap.add_argument("--use-test-set", action="store_true")
    a = ap.parse_args(argv)
    if a.split == "test" and not a.use_test_set:
        sys.exit("The test split is locked. Re-run with --use-test-set only for final results.")
    import pipeline
    from pipeline import config, retrieval
    pipeline.load()
    cases = [c for c in load_cases(a.split).values() if not c["must_escalate"]]
    labels = load_catalog_labels()
    out = {}
    for name, flag in (("v2", False), ("v3", True)):
        config.CONSTRAINT_FILTER = flag
        rows = measure(cases, labels, retrieval.retrieve, retrieval.detect_concerns)
        out[name] = {"summary": summarize(rows), "rows": rows}
    print(f"Retrieval-only check on {a.split} ({len(cases)} non-escalation cases), top-5 retrieved\n")
    print(f"{'':32s} {'metric':6s} {'v2':>10s} {'v3':>10s}")
    for group in out["v2"]["summary"]:
        for k in out["v2"]["summary"][group]:
            v2, v3 = out["v2"]["summary"][group][k], out["v3"]["summary"][group][k]
            print(f"{group:32s} {k:6s} {v2[0]:>4d}/{v2[1]:<5d} {v3[0]:>4d}/{v3[1]:<5d}")
    print("\nConstraint cases (v2 -> v3 retrieved ids):")
    for r2, r3 in zip(out["v2"]["rows"], out["v3"]["rows"]):
        if r2["constraints"]:
            flags = lambda r: ",".join(k for k in ("H1", "H2", "H3") if r[k]) or "ok"  # noqa: E731
            print(f"  {r2['id']:16s} {json.dumps(r2['constraints']):45s} {flags(r2):9s} -> {flags(r3):9s}"
                  f" {'(none)' if r3['none'] else ''}")
    path = os.path.join(HERE, "results", "comparisons", f"retrieval_check_{a.split}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({k: v["summary"] for k, v in out.items()}, open(path, "w"), indent=1)
    print(f"\nSaved {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
