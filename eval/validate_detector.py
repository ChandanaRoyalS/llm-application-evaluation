"""Check the escalation detector against human labels (EVAL_SPEC.md §3.5).

    python eval/validate_detector.py eval/results/<run>

Reads <run>/escalation_labels.jsonl — one line per case:
  {"case_id": ..., "escalates": true/false, "note": ...}
where "escalates" is a human judgment: does this answer genuinely refer
the user to a doctor/dermatologist (not a polite closing caveat)?

Reports agreement and Cohen's kappa for the current detector and for the
naive "mentions a doctor" detector, plus every disagreement.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from checks import components as cc  # noqa: E402
from checks.stats import cohens_kappa  # noqa: E402


def validate(run_dir):
    traces = {}
    with open(os.path.join(run_dir, "traces.jsonl"), encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            traces[t["case_id"]] = t
    with open(os.path.join(run_dir, "escalation_labels.jsonl"), encoding="utf-8") as f:
        labels = [json.loads(line) for line in f if line.strip()]

    out = {"n": len(labels)}
    for name, fn in (("detector", cc.advises_doctor), ("naive_mentions_doctor", cc.mentions_doctor)):
        human = [bool(x["escalates"]) for x in labels]
        pred = [fn(traces[x["case_id"]]) for x in labels]
        agree = sum(h == p for h, p in zip(human, pred)) / len(human)
        out[name] = {
            "agreement": agree, "kappa": cohens_kappa(human, pred),
            "disagreements": [x["case_id"] for x, h, p in zip(labels, human, pred) if h != p],
        }
    return out


if __name__ == "__main__":
    res = validate(sys.argv[1])
    print(json.dumps(res, indent=1))
    with open(os.path.join(sys.argv[1], "escalation_validation.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
