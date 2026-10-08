"""Paired quality comparison of two runs on the same split (cases answered in both).

    python eval/judge/compare_quality.py --before <run_dir> --after <run_dir> --name <out_name>
"""
import argparse
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from checks.stats import mcnemar_exact, paired_bootstrap_diff, wilson  # noqa: E402


def load(run):
    q = json.load(open(os.path.join(run, "quality.json"), encoding="utf-8"))
    return q["summary"], {r["case_id"]: r for r in q["cases"]}


def fails(r):
    return set(r["helpful_fails"]) | set(r["appropriate_fails"] or [])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--name", required=True)
    a = ap.parse_args(argv)
    sb, b = load(a.before)
    sa, f = load(a.after)
    both = sorted(set(b) & set(f))
    pb = [b[c]["passes"] for c in both]
    pa = [f[c]["passes"] for c in both]
    boot = paired_bootstrap_diff([float(x) for x in pa], [float(x) for x in pb])
    p = mcnemar_exact(pa, pb)
    cb, ca = Counter(), Counter()
    for c in both:
        cb.update(fails(b[c]))
        ca.update(fails(f[c]))
    out = [f"# Answer quality: `{os.path.basename(a.before)}` → `{os.path.basename(a.after)}`\n",
           "| | Before | After |", "|---|---|---|"]
    for lbl, s in (("Before", sb), ("After", sa)):
        pass
    out.append(f"| Quality pass rate (all answered) | {100 * sb['quality_pass_rate']:.1f}% ({sb['n_scored']}) | "
               f"{100 * sa['quality_pass_rate']:.1f}% ({sa['n_scored']}) |")
    kb, ka = sum(pb), sum(pa)
    lb, hb = wilson(kb, len(both))
    la, ha = wilson(ka, len(both))
    out.append(f"| Paired: cases answered in both runs | {kb}/{len(both)} ({100*kb/len(both):.1f}%, CI {100*lb:.0f}–{100*hb:.0f}) | "
               f"{ka}/{len(both)} ({100*ka/len(both):.1f}%, CI {100*la:.0f}–{100*ha:.0f}) |")
    out.append(f"\n**Paired difference: {100*boot['diff']:+.1f} pp** (95% bootstrap CI {100*boot['ci_low']:+.1f} to "
               f"{100*boot['ci_high']:+.1f}), exact McNemar p = {p:.2g}. "
               f"Fixed: {sum(1 for x, y in zip(pb, pa) if not x and y)} · broken: {sum(1 for x, y in zip(pb, pa) if x and not y)}.\n")
    out += ["| Failure code (paired cases) | Before | After |", "|---|---|---|"]
    for code in sorted(set(cb) | set(ca), key=lambda c: -(cb[c] + ca[c])):
        out.append(f"| {code} | {cb[code]} | {ca[code]} |")
    broken = [c for c in both if b[c]["passes"] and not f[c]["passes"]]
    if broken:
        out.append("\nCases that passed before and fail after: " + ", ".join(
            f"{c} ({', '.join(sorted(fails(f[c])))})" for c in broken))
    only = sorted(set(b) ^ set(f))
    if only:
        out.append(f"\nAnswered in only one run (excluded from the paired test): {', '.join(only)}")
    text = "\n".join(out) + "\n"
    path = os.path.join(os.path.dirname(HERE), "results", "comparisons", a.name)
    open(path + ".md", "w", encoding="utf-8").write(text)
    json.dump({"before": sb, "after": sa, "n_paired": len(both), "diff": boot, "mcnemar_p": p,
               "codes_before": cb, "codes_after": ca}, open(path + ".json", "w", encoding="utf-8"), indent=1)
    print(text)


if __name__ == "__main__":
    main()
