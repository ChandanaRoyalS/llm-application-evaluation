"""Run-to-run variation across repeats of the same configuration (EVAL_SPEC.md §6).

    python eval/variance.py --split test

Groups every run of a split by configuration (answer model + triage model)
and shows each gate across the temperature-0 run and the repeats at the
provider's default temperature: per-run values, mean, min and max. A gap
between configurations smaller than this spread is treated as a tie.
"""
import argparse
import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from compare import GATES, config_label  # noqa: E402
from score import score_run  # noqa: E402


def collect(split):
    groups = defaultdict(list)
    for d in sorted(glob.glob(os.path.join(HERE, "results", "*"))):
        cfg_path = os.path.join(d, "config.json")
        if not os.path.exists(cfg_path):
            continue
        cfg = json.load(open(cfg_path, encoding="utf-8"))
        if cfg.get("split") == split and cfg.get("triage_enabled"):
            groups[config_label(cfg)].append(d)
    return groups


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="test")
    a = ap.parse_args(argv)
    out = [f"# Run-to-run variation — {a.split} split\n",
           "Each configuration: one run at temperature 0 plus repeats at the provider's default "
           "temperature. A difference between configurations smaller than the spread here is a tie.\n"]
    summary = {}
    for label, dirs in sorted(collect(a.split).items()):
        rows = []
        for d in dirs:
            res = score_run(d)
            if not res.get("valid", True):
                print(f"skipping invalid run (model calls failed): {os.path.basename(d)}", file=sys.stderr)
                continue
            v = {x["key"]: x["value"] for x in res["verdicts"]}
            t = res["config"].get("temperature")
            rows.append(("t0" if t == 0 else f"default r{res['config'].get('repeat') or '?'}", v))
        if not rows:
            continue
        out.append(f"## {label} ({len(rows)} runs)\n")
        out.append("| Gate | " + " | ".join(r[0] for r in rows) + " | mean | min–max |")
        out.append("|---|" + "---|" * (len(rows) + 2))
        summary[label] = {}
        for k, label_g, *_ in GATES:
            vals = [r[1].get(k) for r in rows if r[1].get(k) is not None]
            if not vals:
                continue
            mean = sum(vals) / len(vals)
            summary[label][k] = {"values": vals, "mean": mean, "min": min(vals), "max": max(vals)}
            cells = " | ".join(f"{100 * r[1][k]:.1f}%" if r[1].get(k) is not None else "—" for r in rows)
            out.append(f"| {label_g} | {cells} | {100 * mean:.1f}% | {100 * min(vals):.1f}–{100 * max(vals):.1f}% |")
        out.append("")
    os.makedirs(os.path.join(HERE, "results", "comparisons"), exist_ok=True)
    base = os.path.join(HERE, "results", "comparisons", f"variance_{a.split}")
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print("\n".join(out))


if __name__ == "__main__":
    main()
