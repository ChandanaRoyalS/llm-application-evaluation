"""Answer quality for one run (EVAL_SPEC.md §3.7, as validated in spec v1.10).

    python eval/judge/score_quality.py --run eval/results/<run> --hand eval/judge/hand_helpful_<...>.csv

Scores every answered case (status "ok"):
  Helpful      fails if any of H1-H3 (code checks) or H4-H6 (hand labels: the judge's
               holdout kappa for Helpful was 0.44, below the 0.60 bar)
  Appropriate  fails if any of A5, A7 (code checks) or A1, A2, A4, A6 (judge v5, holdout kappa 0.78)
  A case passes quality only if both pass. A3 (ingredient-claim accuracy) is unmeasured.
The doctor-referral verdict (judge, holdout kappa 1.00) is reported alongside, not part of the pass.
Judge calls are cached in eval/judge/runs/, so a stopped run resumes.
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "app"))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from checks.stats import wilson  # noqa: E402
from code_checks import code_fails, load_catalog_labels  # noqa: E402

TARGET = 0.85
JUDGE_VERSION = "v5"


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def product_view(pid, app):
    p = app.get(str(pid), {})
    return {"name": p.get("name") or p.get("brand", "?"), "price": p.get("price"),
            "concerns": p.get("concerns", []), "ingredients": p.get("ingredients", [])[:12]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--hand", required=True, help="hand labels for H4-H6 (case_id, helpful_fails)")
    a = ap.parse_args(argv)

    import judge
    from pipeline import llm
    if judge.PROMPT_VERSION != JUDGE_VERSION:
        sys.exit(f"score_quality uses the validated judge {JUDGE_VERSION}, but judge.py is {judge.PROMPT_VERSION}")

    run_dir = os.path.abspath(a.run)
    cfg = json.load(open(os.path.join(run_dir, "config.json"), encoding="utf-8"))
    cases = {c["id"]: c for c in load_jsonl(os.path.join(ROOT, "eval", "datasets", f"{cfg['split']}.jsonl"))}
    traces = [t for t in load_jsonl(os.path.join(run_dir, "traces.jsonl")) if t.get("status") == "ok"]
    hand = {r["case_id"]: r for r in csv.DictReader(open(a.hand, encoding="utf-8"))}
    missing = [t["case_id"] for t in traces if t["case_id"] not in hand]
    if missing:
        sys.exit(f"hand labels missing for {len(missing)} answered cases, e.g. {missing[:3]}")
    labels = load_catalog_labels()
    app = {str(p["product_id"]): p for p in json.load(open(os.path.join(ROOT, "app", "app_data.json"), encoding="utf-8"))}

    cache_path = os.path.join(HERE, "runs", f"quality_{os.path.basename(run_dir)}_{JUDGE_VERSION}.jsonl")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    cached = {r["case_id"]: r for r in load_jsonl(cache_path)} if os.path.exists(cache_path) else {}
    todo = [t for t in traces if t["case_id"] not in cached]
    if todo:
        try:
            llm.chat(judge.routed(judge.JUDGE_MODEL), [{"role": "user", "content": "Reply with OK."}], max_tokens=3)
        except llm.LLMError as e:
            sys.exit(f"Preflight call to {judge.JUDGE_MODEL} failed, nothing was run: {e}")
    print(f"{len(traces)} answered cases; judging {len(todo)} ({len(cached)} cached)")
    with open(cache_path, "a", encoding="utf-8") as f:
        for n, t in enumerate(todo, 1):
            products = [product_view(p, app) for p in t.get("recommended_ids") or []]
            res = judge.judge_one(t["query"], t["answer"], products, t.get("context_given_to_llm") or "")
            res["case_id"] = t["case_id"]
            res["provider"] = os.environ.get("JUDGE_PROVIDER") or "router default"
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            f.flush()
            cached[t["case_id"]] = res
            print(f"  [{n}/{len(todo)}] {t['case_id']}")

    rows, code_counts = [], Counter()
    for t in traces:
        cid = t["case_id"]
        cf = code_fails(cases[cid], t.get("recommended_ids"), t.get("answer"), labels)
        jv = cached[cid]["verdicts"]
        hand_fails = [c for c in (hand[cid]["helpful_fails"] or "").split(";") if c]
        judge_app = jv["appropriate"]["fails"]
        helpful = sorted(set(cf["helpful"]) | set(hand_fails))
        appropriate = None if judge_app is None else sorted(set(cf["appropriate"]) | set(judge_app))
        row = {"case_id": cid, "category": cases[cid]["category"], "helpful_fails": helpful,
               "appropriate_fails": appropriate, "doctor": jv["refers_to_doctor"].get("code"),
               "judge_parse_ok": cached[cid]["parse_ok"]}
        row["passes"] = None if appropriate is None else (not helpful and not appropriate)
        code_counts.update(helpful + (appropriate or []))
        rows.append(row)

    scored = [r for r in rows if r["passes"] is not None]
    k, n = sum(r["passes"] for r in scored), len(scored)
    lo, hi = wilson(k, n)
    hk = sum(not r["helpful_fails"] for r in rows)
    ak = sum(not r["appropriate_fails"] for r in scored)
    summary = {"run": os.path.basename(run_dir), "n_answered": len(rows), "n_scored": n,
               "judge_failures": len(rows) - n, "quality_pass_rate": k / n if n else None,
               "ci_low": lo, "ci_high": hi, "target": TARGET,
               "helpful_rate": hk / len(rows), "appropriate_rate": ak / n if n else None,
               "codes": dict(sorted(code_counts.items())), "judge_version": JUDGE_VERSION}
    out = [f"# Answer quality — `{summary['run']}`\n",
           "Helpful = code checks H1–H3 + hand labels H4–H6 (judge not validated for Helpful). "
           f"Appropriate = code checks A5, A7 + judge {JUDGE_VERSION} A1, A2, A4, A6 (holdout κ 0.78). "
           "A3 (ingredient-claim accuracy) is unmeasured.\n",
           f"**Quality pass rate: {100 * summary['quality_pass_rate']:.1f}%** ({k}/{n}, 95% CI {100 * lo:.1f}–{100 * hi:.1f}%) "
           f"— target ≥ {100 * TARGET:.0f}%: **{'met' if summary['quality_pass_rate'] >= TARGET else 'not met'}**.\n",
           f"- Helpful: {100 * summary['helpful_rate']:.1f}% · Appropriate: {100 * summary['appropriate_rate']:.1f}% · "
           f"judge failures: {summary['judge_failures']}\n",
           "| Code | Cases | Meaning |", "|---|---|---|"]
    import checklist
    meaning = {**checklist.CODE_HELPFUL, **checklist.HELPFUL, **checklist.CODE_APPROPRIATE, **checklist.APPROPRIATE}
    for c, v in sorted(code_counts.items(), key=lambda x: -x[1]):
        out.append(f"| {c} | {v} | {meaning.get(c, '')} |")
    out += ["\n| Case | Helpful fails | Appropriate fails | Doctor |", "|---|---|---|---|"]
    for r in rows:
        if r["passes"] is not True:
            out.append(f"| {r['case_id']} | {', '.join(r['helpful_fails']) or '—'} | "
                       f"{'judge failed' if r['appropriate_fails'] is None else ', '.join(r['appropriate_fails']) or '—'} | {r['doctor']} |")
    with open(os.path.join(run_dir, "quality.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    with open(os.path.join(run_dir, "quality.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "cases": rows}, f, indent=1)
    print("\n".join(out[:4]))
    print(f"\nReport: {os.path.relpath(os.path.join(run_dir, 'quality.md'), ROOT)}")


if __name__ == "__main__":
    main()
