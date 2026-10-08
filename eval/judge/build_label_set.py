"""Build the hand-label set used to validate the LLM judge (EVAL_SPEC.md §3.7).

    python eval/judge/build_label_set.py

Picks 80 answered dev-split outputs, 20 from each candidate model, spread across case
categories (fixed seed, so the set is reproducible). Splits them 40/40 into
`calibration` (the judge prompt may be tuned on these) and `holdout` (judge-human
agreement is reported on these only). Dev only: the test split is never used.

If label_set.jsonl already exists, it is kept as is (the items and their split are frozen)
and only the labeling page is rebuilt, e.g. after a checklist change.

Writes
  eval/judge/label_set.jsonl   the 80 items, with the model and split (kept out of the tool)
  eval/judge/label_tool.html   a self-contained labeling page: open it in a browser,
                               label, then "Export CSV" -> save as eval/judge/human_labels.csv
"""
import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
RESULTS = os.path.join(ROOT, "eval", "results")

# one dev run per candidate model (the triage-v2 runs where they exist)
RUNS = {
    "llama-3.1-8b": "20261007-2147_dev_llama-3.1-8b-instruct_t0",
    "llama-3.3-70b": "20261007-2153_dev_llama-3.3-70b-instruct_t0",
    "qwen3-235b": "20261007-2050_dev_qwen3-235b-a22b-instruct-2507_t0",
    "gemma-3-27b": "20261007-2054_dev_gemma-3-27b-it_t0",
}
PER_MODEL = 20
SEED = 42


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pick(traces, n, rng, used_queries):
    """Round-robin over categories so rare categories are represented; avoid using the
    same question more than twice across models."""
    by_cat = defaultdict(list)
    for t in traces:
        by_cat[t["case_id"].rsplit("-", 1)[0]].append(t)
    for lst in by_cat.values():
        rng.shuffle(lst)
    cats = sorted(by_cat)
    rng.shuffle(cats)
    out = []
    while len(out) < n and any(by_cat.values()):
        for c in cats:
            while by_cat[c]:
                t = by_cat[c].pop()
                if used_queries[t["case_id"]] < 2:
                    used_queries[t["case_id"]] += 1
                    out.append(t)
                    break
            if len(out) == n:
                break
    return out


def write_tool(items):
    sys.path.insert(0, HERE)
    import checklist
    blind = [{k: it[k] for k in ("item_id", "query", "answer", "products", "context")} for it in items]
    ck = {"HELPFUL": checklist.HELPFUL, "HELPFUL_NOTE": checklist.HELPFUL_NOTE,
          "APPROPRIATE": checklist.APPROPRIATE, "DOCTOR": checklist.DOCTOR}
    page = open(os.path.join(HERE, "label_tool_template.html"), encoding="utf-8").read()
    page = page.replace("/*ITEMS*/[]", json.dumps(blind, ensure_ascii=False).replace("</", "<\\/"))
    page = page.replace("/*CHECKLIST*/{}", json.dumps(ck, ensure_ascii=False).replace("</", "<\\/"))
    with open(os.path.join(HERE, "label_tool.html"), "w", encoding="utf-8") as f:
        f.write(page)


def main():
    existing = os.path.join(HERE, "label_set.jsonl")
    if os.path.exists(existing):
        items = load_jsonl(existing)
        write_tool(items)
        print(f"Kept the frozen {len(items)}-item label set; rebuilt eval/judge/label_tool.html")
        return
    rng = random.Random(SEED)
    catalog = {p["product_id"]: p for p in json.load(open(os.path.join(ROOT, "app", "app_data.json"), encoding="utf-8"))}
    used = defaultdict(int)
    items = []
    for model, run in RUNS.items():
        traces = [t for t in load_jsonl(os.path.join(RESULTS, run, "traces.jsonl")) if t.get("status") == "ok"]
        for t in pick(traces, PER_MODEL, rng, used):
            products = []
            for pid in t.get("recommended_ids") or []:
                p = catalog.get(pid, {})
                products.append({"name": p.get("name") or p.get("brand", "?"), "price": p.get("price"),
                                 "concerns": p.get("concerns", []), "ingredients": p.get("ingredients", [])[:12]})
            items.append({"case_id": t["case_id"], "model": model, "run": run, "query": t["query"],
                          "answer": t["answer"], "products": products,
                          "context": t.get("context_given_to_llm") or ""})
    rng.shuffle(items)
    for i, it in enumerate(items, 1):
        it["item_id"] = f"L{i:03d}"
    # 40/40 split, balanced by model
    by_model = defaultdict(list)
    for it in items:
        by_model[it["model"]].append(it)
    for lst in by_model.values():
        for j, it in enumerate(lst):
            it["split"] = "calibration" if j % 2 == 0 else "holdout"

    with open(os.path.join(HERE, "label_set.jsonl"), "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    write_tool(items)
    n_split = sum(1 for it in items if it["split"] == "holdout")
    print(f"{len(items)} items ({len(items) - n_split} calibration / {n_split} holdout) -> eval/judge/label_tool.html")


if __name__ == "__main__":
    main()
