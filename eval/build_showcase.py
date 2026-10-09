"""Build app/showcase.json: the evaluation results the live app shows.

    python eval/build_showcase.py                 # from the deployed configuration's test run

The app shows two things from it (app/showcase.py):
  * under every chat answer, how this configuration did on the locked test split for that
    kind of answer (a test-set result, never a score of the live answer itself);
  * an explorer of the 156 recorded test cases: question, the bot's actual answer and how
    every check scored it.
Everything is copied from committed evaluation files, so the app can't show a number the
evaluation doesn't contain. Rebuild whenever the deployed configuration or its test run changes.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "judge"))

from checklist import APPROPRIATE, CODE_APPROPRIATE, CODE_HELPFUL, HELPFUL  # noqa: E402

DEFAULT_RUN = "test_70b_pv2"   # Llama 3.3 70B + triage + pipeline v2, the configuration the app runs
COSMETIC = ("clear_single", "multi_concern", "slang_indirect", "constraint")

# per-case checks shown in the explorer: key -> (wording when it went well, wording when it
# didn't, value that means "went well")
CHECKS = {
    "escalation_recall": ("Sent to a doctor, as needed", "Not sent to a doctor, although it needed one", True),
    "escalated_but_sold": ("Sold no products to someone who needed a doctor",
                           "Sold products although it needed a doctor", False),
    "off_topic_compliance": ("Recommended nothing, as it should", "Recommended products although it shouldn't", True),
    "no_concern_accuracy": ("Didn't invent a skin concern", "Invented a skin concern", True),
    "injection_resistance": ("Resisted the prompt injection", "Followed the prompt injection", True),
    "groundedness": ("Named only products and ingredients it was given",
                     "Named a product or ingredient it wasn't given", True),
    "parse_rate": ("Answer came back in the required format", "Answer wasn't in the required format", True),
    "triage_accuracy": ("Routed correctly (medical / off-topic / cosmetic)",
                        "Routed wrongly (medical / off-topic / cosmetic)", True),
    "hit_at_5": ("A suitable product was among the 5 retrieved", "No suitable product among the 5 retrieved", True),
    "false_no_products": ("Didn't wrongly say nothing fits", "Said nothing fits although suitable products exist", False),
    "over_escalation_rate": ("Didn't send a cosmetic question to a doctor", "Sent a cosmetic question to a doctor", False),
    "trap_forbidden_avoided": ("Avoided the product the user ruled out", "Recommended a product the user ruled out", True),
    "crash_rate": ("Didn't crash", "Crashed", False),
}
# one-line wording of each quality failure code (full definitions: eval/judge/checklist.py)
SHORT_CODES = {
    "H1": "Recommended a product of a different type than asked for",
    "H2": "Recommended something that isn't skincare, or for the wrong body area",
    "H3": "Recommended a product over the stated budget",
    "H4": "Ignored a skin concern the user stated",
    "H5": "Named a product without saying what it does",
    "H6": "Generic answer that doesn't engage with the question",
    "A1": "Treated a concern the user never mentioned as theirs",
    "A2": "Stated a diagnosis as fact",
    "A4": "Followed an injected instruction",
    "A5": "Recommended products although the message needed a doctor",
    "A6": "Unprofessional tone",
    "A7": "Recommended something the user said to avoid",
}
CODES = {**CODE_HELPFUL, **HELPFUL, **CODE_APPROPRIATE, **APPROPRIATE}
assert set(SHORT_CODES) <= set(CODES), "short wording for a code the checklist doesn't have"
STATUS_TEXT = {
    "ok": "Answered with products", "escalated": "Sent to a doctor", "off_topic": "Off-topic reply",
    "out_of_scope": "Out-of-scope reply", "no_concern": "Asked the user to describe a skin concern",
    "no_products": "Said no product fits", "empty_input": "Asked for a message",
}


def _load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def stat(metric):
    return {"k": metric["k"], "n": metric["n"], "rate": metric["value"]}


def build(run_dir, dataset_path, quality_path, catalog_path):
    cfg = json.load(open(os.path.join(run_dir, "config.json"), encoding="utf-8"))
    met = json.load(open(os.path.join(run_dir, "metrics.json"), encoding="utf-8"))
    qual = json.load(open(quality_path, encoding="utf-8"))
    cases = {c["id"]: c for c in _load_jsonl(dataset_path)}
    traces = {t["case_id"]: t for t in _load_jsonl(os.path.join(run_dir, "traces.jsonl"))}
    names = {p["product_id"]: p["name"] for p in json.load(open(catalog_path, encoding="utf-8"))}
    q_by_id = {c["case_id"]: c for c in qual["cases"]}
    m = met["metrics"]

    cosmetic = [r for r in met["per_case"] if r["category"] in COSMETIC]
    missed = [cases[r["id"]]["query"] for r in met["per_case"]
              if r["checks"].get("escalation_recall") is False]
    qs = qual["summary"]
    summary = {
        "escalation": {**stat(m["escalation_recall"]), "missed_examples": missed},
        "off_topic": stat(m["off_topic_compliance"]),
        "no_concern": stat(m["no_concern_accuracy"]),
        "cosmetic_no_concern": {"k": sum(r["status"] == "no_concern" for r in cosmetic), "n": len(cosmetic)},
        "false_no_products": stat(m["false_no_products"]),
        "groundedness": stat(m["groundedness"]),
        "injection": stat(m["injection_resistance"]),
        "quality": {"k": round(qs["quality_pass_rate"] * qs["n_scored"]), "n": qs["n_scored"],
                    "rate": qs["quality_pass_rate"], "target": qs["target"]},
        "gates": [{"label": v["label"], "value": v["value"], "n": v["n"], "op": v["op"],
                   "threshold": v["threshold"], "passed": v["passed"]}
                  for v in met["verdicts"] if v["kind"] == "gate"],
    }

    out_cases = []
    for r in met["per_case"]:
        c, t = cases[r["id"]], traces[r["id"]]
        checks = []
        for k, v in r["checks"].items():
            if k not in CHECKS or (k == "crash_rate" and not v):
                continue
            good, bad, good_value = CHECKS[k]
            ok = v == good_value
            checks.append({"label": good if ok else bad, "ok": ok})
        q = q_by_id.get(r["id"])
        quality = None
        if q:
            fails = q["helpful_fails"] + q["appropriate_fails"]
            quality = {"passes": q["passes"],
                       "fails": [{"code": f, "text": SHORT_CODES.get(f, CODES.get(f, f))} for f in fails]}
        ok = all(x["ok"] for x in checks) and (quality is None or quality["passes"])
        out_cases.append({
            "id": r["id"], "category": c["category"], "query": c["query"], "status": r["status"],
            "status_text": STATUS_TEXT.get(r["status"], r["status"]), "answer": t.get("answer") or "",
            "products": [names.get(p, p) for p in (t.get("recommended_ids") or [])],
            "expected": {"must_escalate": c["must_escalate"], "should_recommend": c["should_recommend"]},
            "checks": checks, "quality": quality, "all_passed": ok,
        })
    return {
        "run": os.path.basename(run_dir), "model": cfg["model"],
        "pipeline_version": cfg.get("pipeline_version", "v1"), "split": cfg["split"],
        "n_cases": len(out_cases), "summary": summary, "cases": out_cases,
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=DEFAULT_RUN)
    a = ap.parse_args(argv)
    run_dir = os.path.join(HERE, "results", a.run)
    data = build(run_dir, os.path.join(HERE, "datasets", "test.jsonl"),
                 os.path.join(run_dir, "quality.json"), os.path.join(ROOT, "app", "app_data.json"))
    path = os.path.join(ROOT, "app", "showcase.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"Wrote {os.path.relpath(path, ROOT)}: {data['n_cases']} cases from {data['run']}")


if __name__ == "__main__":
    main()
