"""Judge-human agreement (EVAL_SPEC.md §3.7, changelog v1.7).

    python eval/judge/agreement.py --version v1

Per criterion and split: Cohen's kappa with a bootstrap 95% CI, raw agreement,
confusion counts, and how many items were left out (human "unsure" or unreadable
judge output). The usage decision is made on the holdout split only:
a criterion may be scored by the judge if its holdout kappa >= 0.60.
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

from checks.stats import cohens_kappa  # noqa: E402
from checklist import APPROPRIATE, HELPFUL  # noqa: E402
from judge import CRITERIA, JUDGE_MODEL, run_path  # noqa: E402

KAPPA_MIN = 0.60


def bootstrap_kappa(h, j, iters=5000, seed=0):
    rng, n, ks = random.Random(seed), len(h), []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        ks.append(cohens_kappa([h[i] for i in idx], [j[i] for i in idx]))
    ks.sort()
    return ks[int(0.025 * iters)], ks[int(0.975 * iters) - 1]


def agreement(pairs):
    """pairs: list of (human 'yes'/'no'/'unsure'/'', judge 'yes'/'no'/None)."""
    used = [(h, j) for h, j in pairs if h in ("yes", "no") and j in ("yes", "no")]
    out = {"n": len(used), "excluded_unsure": sum(1 for h, _ in pairs if h not in ("yes", "no")),
           "excluded_judge": sum(1 for h, j in pairs if h in ("yes", "no") and j not in ("yes", "no"))}
    if not used:
        return out
    h = [x == "yes" for x, _ in used]
    j = [y == "yes" for _, y in used]
    out.update(kappa=cohens_kappa(h, j), raw=sum(a == b for a, b in zip(h, j)) / len(h),
               yy=sum(a and b for a, b in zip(h, j)), yn=sum(a and not b for a, b in zip(h, j)),
               ny=sum(b and not a for a, b in zip(h, j)), nn=sum(not a and not b for a, b in zip(h, j)))
    out["kappa_ci"] = bootstrap_kappa(h, j) if len(used) >= 5 else (None, None)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--labels", default=os.path.join(HERE, "reference_labels.csv"),
                    help="reference labels (default: reference_labels.csv, written by Claude; see spec v1.9)")
    a = ap.parse_args(argv)
    human = {r["item_id"]: r for r in csv.DictReader(open(a.labels, encoding="utf-8"))}
    judged = {}
    path = run_path(a.model, a.version)
    for line in open(path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            judged[r["item_id"]] = r
    results, out = {}, [f"# Judge agreement — prompt {a.version}, `{a.model}`\n",
                        f"Reference labels: `{os.path.relpath(a.labels, os.path.dirname(os.path.dirname(HERE)))}`. The judge is used for a criterion only if "
                        f"its **holdout** κ ≥ {KAPPA_MIN}. Calibration numbers are for tuning and are optimistic.\n",
                        "| Split | Criterion | n | κ (95% CI) | Raw agreement | Reference yes / judge no | Reference no / judge yes | Left out (unsure / judge) | Judge usable |",
                        "|---|---|---|---|---|---|---|---|---|"]
    for split in ("calibration", "holdout"):
        ids = [i for i, r in judged.items() if r["split"] == split and i in human]
        if not ids:
            continue
        for c in CRITERIA:
            s = agreement([(human[i][c], judged[i]["verdicts"][c]["verdict"]) for i in ids])
            results[f"{split}:{c}"] = s
            if "kappa" not in s:
                out.append(f"| {split} | {c} | 0 | — | — | — | — | {s['excluded_unsure']} / {s['excluded_judge']} | — |")
                continue
            lo, hi = s["kappa_ci"]
            ci = f" ({lo:.2f} to {hi:.2f})" if lo is not None else ""
            usable = ("yes" if s["kappa"] >= KAPPA_MIN else "no") if split == "holdout" else "—"
            out.append(f"| {split} | {c} | {s['n']} | {s['kappa']:.2f}{ci} | {100 * s['raw']:.0f}% | {s['yn']} | {s['ny']} "
                       f"| {s['excluded_unsure']} / {s['excluded_judge']} | {usable} |")
    codes = ["\n## Checklist codes (counts; which specific failures each side found)\n",
             "| Split | Code | Reference ticked | Judge ticked | Both |", "|---|---|---|---|---|"]
    for split in ("calibration", "holdout"):
        ids = [i for i, r in judged.items() if r["split"] == split and i in human]
        for code in list(HELPFUL) + list(APPROPRIATE):
            crit = "helpful" if code.startswith("H") else "appropriate"
            hs = {i for i in ids if code in (human[i].get(f"{crit}_fails") or "").split(";")}
            js = {i for i in ids if code in (judged[i]["verdicts"][crit].get("fails") or [])}
            if hs or js:
                codes.append(f"| {split} | {code} | {len(hs)} | {len(js)} | {len(hs & js)} |")
    disagree = ["\n## Disagreements (calibration only; holdout disagreements are not shown, to keep tuning blind)\n"]
    for i, r in sorted(judged.items()):
        if r["split"] != "calibration" or i not in human:
            continue
        for c in CRITERIA:
            hv, jv = human[i][c], r["verdicts"][c]["verdict"]
            if hv in ("yes", "no") and jv in ("yes", "no") and hv != jv:
                extra = ""
                if c != "refers_to_doctor":
                    extra = f" (reference codes: {human[i].get(c + '_fails') or '—'}; judge codes: {', '.join(r['verdicts'][c].get('fails') or []) or '—'})"
                else:
                    extra = f" (reference: {human[i].get('doctor_code') or '—'}; judge: {r['verdicts'][c].get('code') or '—'})"
                disagree.append(f"- **{i}** {c}: reference {hv}, judge {jv}{extra} — {r['verdicts'][c]['reason']}")
    text = "\n".join(out + codes + disagree) + "\n"
    base = os.path.join(HERE, f"agreement_{a.version}")
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write(text)
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print(text)


if __name__ == "__main__":
    main()
