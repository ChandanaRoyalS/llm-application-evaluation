"""Build the CI smoke set: a fixed, small subset of the dev split.

    python eval/datasets/build_smoke.py

The smoke set runs on every pull request (.github/workflows/eval-gate.yml), so it
has to be cheap (~24 cases) and still exercise every gate in EVAL_SPEC.md §4.
Cases are taken by a fixed rule, not picked by hand: for each category, the first
N dev cases in id order. It is a subset of dev, never of test, so the locked test
split stays unseen. Rebuild only when dev.jsonl changes.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# Weighted toward the categories behind the safety gates (escalation, injection,
# off-topic, no-concern), with at least one answered case per remaining category
# so groundedness, parse rate and crashes are exercised on real answers.
PER_CATEGORY = {
    "hidden_red_flag": 5, "clearly_medical": 2, "injection": 4, "off_topic": 3,
    "edge_case": 2, "not_in_catalog": 2, "clear_single": 2, "multi_concern": 1,
    "slang_indirect": 1, "constraint": 1, "trap": 1,
}


def build(dev_cases):
    out = []
    for cat, n in PER_CATEGORY.items():
        picked = sorted((c for c in dev_cases if c["category"] == cat), key=lambda c: c["id"])[:n]
        if len(picked) < n:
            raise ValueError(f"dev has only {len(picked)} {cat} cases, need {n}")
        out.extend(picked)
    return out


def main():
    with open(os.path.join(HERE, "dev.jsonl"), encoding="utf-8") as f:
        dev = [json.loads(line) for line in f if line.strip()]
    smoke = build(dev)
    with open(os.path.join(HERE, "smoke.jsonl"), "w", encoding="utf-8") as f:
        for c in smoke:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"Wrote {len(smoke)} cases to smoke.jsonl")


if __name__ == "__main__":
    main()
