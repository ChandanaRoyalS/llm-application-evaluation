"""Dataset label consistency check (EVAL_SPEC.md §4; changelog v1.18).

50 of the 260 cases are re-labeled blind, from the query text only (no id hint,
no category, no earlier labels), and compared with the dataset labels:

    python eval/datasets/label_consistency.py sample    # label_consistency_sample.jsonl
    # ... label blind into label_consistency_labels.csv ...
    python eval/datasets/label_consistency.py compare   # label_consistency.md / .json

Hand-written labels only: must_escalate, should_recommend, expected_concerns.
relevant_product_ids and must_not_recommend_ids are derived by code.
"""
import argparse
import csv
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from checks.stats import cohens_kappa, wilson  # noqa: E402

SEED = 2026
N = 50
SAMPLE = os.path.join(HERE, "label_consistency_sample.jsonl")
LABELS = os.path.join(HERE, "label_consistency_labels.csv")


def load_all():
    out = []
    for split in ("dev", "test"):
        with open(os.path.join(HERE, f"{split}.jsonl"), encoding="utf-8") as f:
            out += [json.loads(line) for line in f if line.strip()]
    return out


def sample(cases, seed=SEED, n=N):
    """Stratified by category (proportional, at least 2 each), fixed seed.

    The output is shuffled and given neutral keys (S01..S50) so the labeler
    sees neither the case id (which names the category) nor the category order.
    """
    rng = random.Random(seed)
    by_cat = {}
    for c in sorted(cases, key=lambda c: c["id"]):
        by_cat.setdefault(c["category"], []).append(c)
    quota = {k: max(2, round(len(v) * n / len(cases))) for k, v in by_cat.items()}
    while sum(quota.values()) > n:                       # trim the largest strata
        quota[max(quota, key=lambda k: quota[k])] -= 1
    while sum(quota.values()) < n:
        quota[max(by_cat, key=lambda k: len(by_cat[k]) - quota[k])] += 1
    picked = [c for k in sorted(by_cat) for c in rng.sample(by_cat[k], quota[k])]
    rng.shuffle(picked)
    return [{"key": f"S{i:02d}", "case_id": c["id"], "query": c["query"]} for i, c in enumerate(picked, 1)]


def _concerns(s):
    return frozenset(x.strip() for x in (s or "").split(";") if x.strip())


def compare(cases, sample_rows, labels):
    by_id = {c["id"]: c for c in cases}
    rows = []
    for s in sample_rows:
        c, l = by_id[s["case_id"]], labels[s["key"]]
        rows.append({"key": s["key"], "case_id": s["case_id"], "category": c["category"],
                     "esc": (c["must_escalate"], l["must_escalate"] == "true"),
                     "rec": (c["should_recommend"], l["should_recommend"] == "true"),
                     "con": (frozenset(c["expected_concerns"]), _concerns(l["expected_concerns"])),
                     "note": l.get("notes", "")})
    n = len(rows)
    res = {"n": n, "fields": {}, "disagreements": []}
    for f, name in (("esc", "must_escalate"), ("rec", "should_recommend")):
        a, b = [r[f][0] for r in rows], [r[f][1] for r in rows]
        same = sum(x == y for x, y in zip(a, b))
        res["fields"][name] = {"raw": same / n, "raw_ci": wilson(same, n), "kappa": cohens_kappa(a, b),
                               "true_first": sum(a), "true_second": sum(b)}
    same = sum(r["con"][0] == r["con"][1] for r in rows)
    jac = [len(a & b) / len(a | b) if (a | b) else 1.0 for a, b in (r["con"] for r in rows)]
    res["fields"]["expected_concerns"] = {"raw": same / n, "raw_ci": wilson(same, n), "kappa": None,
                                          "mean_jaccard": sum(jac) / n}
    for r in rows:
        d = {}
        if r["esc"][0] != r["esc"][1]:
            d["must_escalate"] = r["esc"]
        if r["rec"][0] != r["rec"][1]:
            d["should_recommend"] = r["rec"]
        if r["con"][0] != r["con"][1]:
            d["expected_concerns"] = (sorted(r["con"][0]), sorted(r["con"][1]))
        if d:
            res["disagreements"].append({"case_id": r["case_id"], "category": r["category"],
                                         "diff": {k: list(map(lambda v: sorted(v) if isinstance(v, frozenset) else v, x))
                                                  for k, x in d.items()},
                                         "note": r["note"]})
    return res


def render(res):
    lines = ["# Dataset label consistency check", "",
             f"{res['n']} of the 260 cases (stratified by category, fixed seed) were labeled a second time from the "
             "query text alone, blind to the first labels, the case id and the category.", "",
             "| Field | Exact agreement (95% Wilson CI) | κ | Notes |", "|---|---|---|---|"]
    for name, v in res["fields"].items():
        lo, hi = v["raw_ci"]
        k = "—" if v["kappa"] is None else f"{v['kappa']:.2f}"
        note = (f"true: {v['true_first']} first pass, {v['true_second']} second" if "true_first" in v
                else f"mean Jaccard overlap {v['mean_jaccard']:.2f}")
        lines.append(f"| {name} | {v['raw']:.0%} ({lo:.0%}–{hi:.0%}) | {k} | {note} |")
    lines += ["", "## Disagreements", ""]
    if not res["disagreements"]:
        lines.append("None.")
    for d in res["disagreements"]:
        parts = []
        for k, (a, b) in d["diff"].items():
            parts.append(f"{k}: {a} → {b}")
        lines.append(f"- **{d['case_id']}** ({d['category']}): " + "; ".join(parts)
                     + (f". Second pass note: {d['note']}" if d["note"] else ""))
    lines += ["", "## How to read this", "",
              "- The second pass was made by Claude with the same labeling guide, on the same day as the first: "
              "the spec asked for a gap of at least a week, which the project timeline didn't allow. It is not an "
              "independent labeler (the same project wrote the guide and the original labels), so agreement shows "
              "the guide is applied the same way twice, not that the labels are right.",
              "- Disagreements are not resolved here: the dataset labels are not changed after this check, so the "
              "check measures noise instead of reducing it."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "compare"])
    a = ap.parse_args(argv)
    cases = load_all()
    if a.cmd == "sample":
        with open(SAMPLE, "w", encoding="utf-8") as f:
            for s in sample(cases):
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        print(f"Wrote {SAMPLE}")
        return
    rows = [json.loads(line) for line in open(SAMPLE, encoding="utf-8") if line.strip()]
    labels = {r["key"]: r for r in csv.DictReader(open(LABELS, encoding="utf-8"))}
    if set(labels) != {r["key"] for r in rows}:
        sys.exit("label_consistency_labels.csv must label exactly the sampled keys")
    res = compare(cases, rows, labels)
    json.dump(res, open(os.path.join(HERE, "label_consistency.json"), "w"), indent=1, default=list)
    open(os.path.join(HERE, "label_consistency.md"), "w", encoding="utf-8").write(render(res))
    print(render(res))


if __name__ == "__main__":
    main()
