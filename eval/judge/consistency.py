"""Labeler consistency check (plan Phase 4; EVAL_SPEC.md changelog v1.18).

The reference labels (reference_labels.csv) were written once. To measure how
consistent that labeler is, a fixed sample of 20 items is labeled again, blind to
the first labels, and the two passes are compared.

    python eval/judge/consistency.py sample    # writes consistency_sample.jsonl (no labels)
    # ... label the sample blind into consistency_labels.csv ...
    python eval/judge/consistency.py compare   # writes consistency.md / consistency.json

Only the reading codes are compared (H4-H6, A1, A2, A4, A6 and the doctor code):
the code checks are deterministic and need no consistency check.
"""
import argparse
import csv
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from agreement import bootstrap_kappa  # noqa: E402
from checklist import APPROPRIATE, HELPFUL  # noqa: E402
from checks.stats import cohens_kappa, wilson  # noqa: E402

SEED = 2026
PER_SPLIT = 10
SAMPLE = os.path.join(HERE, "consistency_sample.jsonl")
LABELS = os.path.join(HERE, "consistency_labels.csv")
REFERENCE = os.path.join(HERE, "reference_labels.csv")
FIELDS = ("item_id", "query", "answer", "context", "case_id", "split")


def sample(items, seed=SEED, per_split=PER_SPLIT):
    """10 calibration + 10 holdout items, drawn with a fixed seed."""
    rng, out = random.Random(seed), []
    for split in ("calibration", "holdout"):
        pool = sorted((i for i in items if i["split"] == split), key=lambda i: i["item_id"])
        out += sorted(rng.sample(pool, per_split), key=lambda i: i["item_id"])
    return [{k: i[k] for k in FIELDS} for i in out]


def reading_fails(row, crit):
    codes = HELPFUL if crit == "helpful" else APPROPRIATE
    return {c for c in (row.get(f"{crit}_fails") or "").split(";") if c in codes}


def compare(ref, new):
    ids = sorted(new)
    out = {"n": len(ids), "criteria": {}, "codes": {}, "disagreements": []}
    views = {
        "helpful (reading codes)": lambda r: bool(reading_fails(r, "helpful")),
        "appropriate (reading codes)": lambda r: bool(reading_fails(r, "appropriate")),
        "refers to a doctor": lambda r: r["doctor_code"] == "D_YES",
    }
    for name, f in views.items():
        a, b = [f(ref[i]) for i in ids], [f(new[i]) for i in ids]
        k = cohens_kappa(a, b)
        same = sum(x == y for x, y in zip(a, b))
        out["criteria"][name] = {
            "raw": same / len(ids), "raw_ci": wilson(same, len(ids)), "kappa": k,
            "kappa_ci": bootstrap_kappa(a, b) if k is not None else (None, None),
            "first_pass_fails": sum(a), "second_pass_fails": sum(b)}
    for crit, codes in (("helpful", HELPFUL), ("appropriate", APPROPRIATE)):
        for c in codes:
            a = {i for i in ids if c in reading_fails(ref[i], crit)}
            b = {i for i in ids if c in reading_fails(new[i], crit)}
            out["codes"][c] = {"both": len(a & b), "first_only": len(a - b), "second_only": len(b - a)}
    out["codes"]["doctor_code"] = {"same": sum(ref[i]["doctor_code"] == new[i]["doctor_code"] for i in ids),
                                   "n": len(ids)}
    for i in ids:
        r, n = ref[i], new[i]
        diff = {}
        for crit in ("helpful", "appropriate"):
            if reading_fails(r, crit) != reading_fails(n, crit):
                diff[crit] = (sorted(reading_fails(r, crit)), sorted(reading_fails(n, crit)))
        if r["doctor_code"] != n["doctor_code"]:
            diff["doctor"] = (r["doctor_code"], n["doctor_code"])
        if diff:
            out["disagreements"].append({"item_id": i, "diff": diff, "note": n.get("notes", "")})
    return out


def render(res):
    f = lambda v: "—" if v is None else f"{v:.2f}"  # noqa: E731
    lines = ["# Labeler consistency check", "",
             f"The same labeler (Claude) labeled {res['n']} of the 80 judge items a second time, blind to the "
             "first labels; the sample was drawn with a fixed seed (10 calibration, 10 holdout). "
             "Only the reading codes are compared.", "",
             "| Criterion | Raw agreement (95% Wilson CI) | κ (bootstrap 95% CI) | Fails, first pass | Fails, second pass |",
             "|---|---|---|---|---|"]
    for name, c in res["criteria"].items():
        lo, hi = c["kappa_ci"]
        rlo, rhi = c["raw_ci"]
        lines.append(f"| {name} | {c['raw']:.0%} ({rlo:.0%}–{rhi:.0%}) | {f(c['kappa'])} ({f(lo)}–{f(hi)}) | "
                     f"{c['first_pass_fails']} | {c['second_pass_fails']} |")
    lines += ["", "| Code | Both passes | First only | Second only |", "|---|---|---|---|"]
    for c, v in res["codes"].items():
        if c != "doctor_code":
            lines.append(f"| {c} | {v['both']} | {v['first_only']} | {v['second_only']} |")
    d = res["codes"]["doctor_code"]
    lines += ["", f"Doctor code (D_YES / D_GENERIC / D_NONE) identical on {d['same']}/{d['n']} items.", "",
              "## Disagreements", ""]
    if not res["disagreements"]:
        lines.append("None.")
    for x in res["disagreements"]:
        parts = [f"{k}: {v[0] or '—'} → {v[1] or '—'}" for k, v in x["diff"].items()]
        lines.append(f"- **{x['item_id']}**: {'; '.join(map(str, parts))}" + (f". {x['note']}" if x["note"] else ""))
    lines += ["", "## How to read this", "",
              "- κ is undefined (—) when a criterion has no failures in either pass. When the two passes agree "
              "on every item, the bootstrap interval collapses to a point; the Wilson interval on raw agreement "
              "is the honest range (20/20 is consistent with true agreement as low as about 84%).",
              "- Failures are rare (a handful per criterion), so this mostly confirms the passes agree on the "
              "common cases and on the few failures sampled; it cannot rule out disagreement on rarer codes "
              "(H5, H6, A2, A4, A6 never occurred in the sample).",
              "- Both passes were made by the same AI model with the same written checklist. Agreement shows the "
              "checklist is applied the same way twice; it does not show the labels are right. That needs an "
              "independent (ideally expert) labeler, which the project doesn't have."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "compare"])
    a = ap.parse_args(argv)
    if a.cmd == "sample":
        items = [json.loads(l) for l in open(os.path.join(HERE, "label_set.jsonl"), encoding="utf-8") if l.strip()]
        with open(SAMPLE, "w", encoding="utf-8") as fh:
            for it in sample(items):
                fh.write(json.dumps(it, ensure_ascii=False) + "\n")
        print(f"Wrote {SAMPLE}")
        return
    ref = {r["item_id"]: r for r in csv.DictReader(open(REFERENCE, encoding="utf-8"))}
    new = {r["item_id"]: r for r in csv.DictReader(open(LABELS, encoding="utf-8"))}
    want = {json.loads(l)["item_id"] for l in open(SAMPLE, encoding="utf-8") if l.strip()}
    if set(new) != want:
        sys.exit(f"consistency_labels.csv must label exactly the sampled items; missing {sorted(want - set(new))}")
    res = compare(ref, new)
    json.dump(res, open(os.path.join(HERE, "consistency.json"), "w"), indent=1)
    open(os.path.join(HERE, "consistency.md"), "w", encoding="utf-8").write(render(res))
    print(render(res))


if __name__ == "__main__":
    main()
