"""Compare runs side by side and apply the decision rule (EVAL_SPEC.md §5–6).

    python eval/compare.py eval/results/<run-a> eval/results/<run-b> ...
    python eval/compare.py --split dev          # every run of that split, latest per model

Re-scores each run with the current checks, computes cost from token counts
and eval/model_prices.json, compares every candidate with the baseline
(the first run, or --baseline) using paired tests on the same cases, and
writes eval/results/comparisons/<name>.md and .json.
"""
import argparse
import datetime
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from checks.stats import mcnemar_exact, paired_bootstrap_diff, percentile  # noqa: E402
from score import SPEC, load_jsonl, score_run  # noqa: E402

GATES = [(k, label, op, thr) for k, label, kind, op, thr in SPEC if kind == "gate"]
LLM_METRICS = ["groundedness", "parse_rate", "escalation_recall", "escalated_but_sold",
               "off_topic_compliance", "injection_resistance"]


def load_prices():
    with open(os.path.join(HERE, "model_prices.json"), encoding="utf-8") as f:
        return json.load(f)


def run_cost_per_1k(run_dir, cfg, prices):
    """List-price cost per 1,000 user messages. Triage and answer tokens are priced
    with their own models' prices."""
    answer_p = prices.get(cfg["model"])
    triage_p = prices.get(cfg.get("triage_model") or cfg["model"])
    if not answer_p or not triage_p:
        return None
    traces = load_jsonl(os.path.join(run_dir, "traces.jsonl"))
    if not traces:
        return None
    total = 0.0
    for t in traces:
        tp, tc = t.get("triage_prompt_tokens") or 0, t.get("triage_completion_tokens") or 0
        ap_, ac = (t.get("prompt_tokens") or 0) - tp, (t.get("completion_tokens") or 0) - tc
        total += tp * triage_p["input"] + tc * triage_p["output"]
        total += ap_ * answer_p["input"] + ac * answer_p["output"]
    return 1000 * (total / 1_000_000) / len(traces)


def llm_latency(run_dir, q):
    """Latency of answers that actually called the model (status ok), in seconds."""
    lat = [t.get("total_latency_ms") for t in load_jsonl(os.path.join(run_dir, "traces.jsonl"))
           if t.get("status") == "ok"]
    v = percentile(lat, q)
    return None if v is None else v / 1000


def config_label(cfg):
    """Human label for a configuration: answer model, plus the triage model if different."""
    label = cfg["model"].split("/")[-1]
    tm = cfg.get("triage_model")
    if not cfg.get("triage_enabled", False):  # runs from before triage existed have no key
        label += " (no triage)"
    elif tm and tm != cfg["model"]:
        label += f" + triage {tm.split('/')[-1]}"
    return label


def latest_runs(split, triage_only=True):
    """Latest temperature-0 run per configuration for a split."""
    runs = {}
    for d in sorted(glob.glob(os.path.join(HERE, "results", "*"))):
        cfg = os.path.join(d, "config.json")
        if not os.path.exists(cfg):
            continue
        c = json.load(open(cfg, encoding="utf-8"))
        if c.get("split") != split or c.get("temperature") != 0:
            continue
        if triage_only and not c.get("triage_enabled"):
            continue
        runs[config_label(c)] = d               # sorted by name = timestamp, so latest wins
    return list(runs.values())


def fmt(v, pct=True):
    if v is None:
        return "—"
    return f"{100 * v:.1f}%" if pct else f"{v:.3f}"


def compare(run_dirs, baseline=None, name=None):
    prices = load_prices()
    runs = []
    for d in run_dirs:
        res = score_run(d)
        if not res.get("valid", True):
            print(f"skipping invalid run (model calls failed): {os.path.basename(d)}", file=sys.stderr)
            continue
        model = config_label(res["config"])
        per_case = {r["id"]: r.get("checks", {}) for r in res["per_case"]}
        runs.append({"dir": d, "model": model, "res": res, "per_case": per_case,
                     "cost_per_1k": run_cost_per_1k(d, res["config"], prices),
                     "llm_p50": llm_latency(d, 0.5), "llm_p95": llm_latency(d, 0.95),
                     "p95": res["metrics"]["latency_p95_s"]["value"],
                     "p50": res["metrics"]["latency_p50_s"]["value"]})
    split = runs[0]["res"]["config"]["split"]
    base = next((r for r in runs if baseline and r["model"] == baseline), runs[0])

    for r in runs:
        v = {x["key"]: x for x in r["res"]["verdicts"]}
        r["gates"] = {k: v[k] for k, *_ in GATES}
        r["eligible"] = all(g["passed"] for g in r["gates"].values())

    # paired comparisons vs baseline on the cases both runs scored for a metric
    paired = {}
    for r in runs:
        if r is base:
            continue
        paired[r["model"]] = {}
        for key in LLM_METRICS:
            ids = [i for i in base["per_case"] if key in base["per_case"][i]
                   and key in r["per_case"].get(i, {})]
            if not ids:
                continue
            a = [float(r["per_case"][i][key]) for i in ids]
            b = [float(base["per_case"][i][key]) for i in ids]
            d = paired_bootstrap_diff(a, b, iters=5000) if len(ids) > 1 else None
            paired[r["model"]][key] = {"n": len(ids), "diff": d and d["diff"],
                                       "ci_low": d and d["ci_low"], "ci_high": d and d["ci_high"],
                                       "mcnemar_p": mcnemar_exact([bool(x) for x in a], [bool(x) for x in b])}

    eligible = [r for r in runs if r["eligible"]]
    if eligible:
        known = [r for r in eligible if r["cost_per_1k"] is not None]
        pick = min(known or eligible, key=lambda r: (r["cost_per_1k"] or 0, r["p95"] or 0))
        decision = (f"Ship `{pick['model']}`: the cheapest configuration that passes every gate. "
                    "Quality non-inferiority (§5 step 3) is still pending the validated judge.")
    else:
        common = [label for k, label, *_ in GATES if all(not r["gates"][k]["passed"] for r in runs)]
        decision = ("**No configuration ships** (§5 step 5): no candidate passes every gate. "
                    f"Gates failed by every candidate: {', '.join(common) or 'none in common'}.")

    name = name or f"{datetime.date.today():%Y%m%d}_{split}_" + "-vs-".join(
        r["model"].lower() for r in runs)[:120]
    name = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in name)
    out_dir = os.path.join(HERE, "results", "comparisons")
    os.makedirs(out_dir, exist_ok=True)
    md = render(runs, base, paired, decision, split)
    with open(os.path.join(out_dir, name + ".md"), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as f:
        json.dump({"split": split, "baseline": base["model"], "decision": decision,
                   "runs": [{"dir": os.path.relpath(r["dir"], HERE), "model": r["model"],
                             "eligible": r["eligible"], "cost_per_1k_usd": r["cost_per_1k"],
                             "latency_p50_s": r["p50"], "latency_p95_s": r["p95"],
                             "answered_latency_p50_s": r["llm_p50"], "answered_latency_p95_s": r["llm_p95"],
                             "gates": {k: {"value": g["value"], "ci_low": g["ci_low"],
                                           "ci_high": g["ci_high"], "n": g["n"], "passed": g["passed"]}
                                       for k, g in r["gates"].items()}} for r in runs],
                   "paired_vs_baseline": paired}, f, indent=1)
    print(md)
    return os.path.join(out_dir, name + ".md")


def render(runs, base, paired, decision, split):
    o = [f"# Model comparison — {split} split\n",
         f"Baseline: `{base['model']}`. Everything except the model is identical "
         "(same prompt, retrieval, catalog and cases). Cost uses list prices from "
         "`eval/model_prices.json`; intervals are 95% Wilson.\n",
         f"**Decision:** {decision}\n", "## Gates\n"]
    o.append("| Gate | Threshold | " + " | ".join(f"`{r['model'].split('/')[-1]}`" for r in runs) + " |")
    o.append("|---|---|" + "---|" * len(runs))
    for k, label, op, thr in GATES:
        cells = []
        for r in runs:
            g = r["gates"][k]
            mark = "✅" if g["passed"] else ("❌" if g["passed"] is False else "—")
            ci = f" ({fmt(g['ci_low'])}–{fmt(g['ci_high'])})" if g["ci_low"] is not None else ""
            cells.append(f"{mark} {fmt(g['value'])}{ci}")
        o.append(f"| {label} | {op} {fmt(thr)} | " + " | ".join(cells) + " |")
    o.append("")
    o.append("## Cost and speed\n")
    o.append("Latency is shown for all messages and for answered messages only (those that called "
             "the model); greetings and refusals return almost instantly and pull the overall numbers down.\n")
    o.append("| Model | Cost per 1,000 messages | p50 / p95 (all) | p50 / p95 (answered) | Eligible |\n"
             "|---|---|---|---|---|")
    for r in runs:
        c = "—" if r["cost_per_1k"] is None else f"${r['cost_per_1k']:.3f}"
        o.append(f"| `{r['model']}` | {c} | {r['p50']:.2f}s / {r['p95']:.2f}s | "
                 f"{r['llm_p50']:.2f}s / {r['llm_p95']:.2f}s | {'yes' if r['eligible'] else 'no'} |")
    o.append("")
    o.append(f"## Paired differences vs `{base['model']}`\n")
    o.append("Same cases, candidate minus baseline. A difference whose interval includes 0 is not "
             "distinguishable from noise.\n")
    o.append("| Model | Metric | n | Difference | 95% CI | McNemar p |\n|---|---|---|---|---|---|")
    for model, mets in paired.items():
        for key, v in mets.items():
            if v["diff"] is None:
                continue
            o.append(f"| `{model}` | {key} | {v['n']} | {100 * v['diff']:+.1f} pp | "
                     f"{100 * v['ci_low']:+.1f} to {100 * v['ci_high']:+.1f} pp | {v['mcnemar_p']:.2f} |")
    o.append("")
    return "\n".join(o)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--split", choices=["dev", "test"])
    ap.add_argument("--baseline", default=None, help="config label of the baseline (default: first run)")
    ap.add_argument("--name")
    a = ap.parse_args()
    dirs = a.runs or latest_runs(a.split or "dev")
    if a.baseline:
        dirs.sort(key=lambda d: config_label(json.load(open(os.path.join(d, "config.json")))) != a.baseline)
    compare(dirs, a.baseline, a.name)
