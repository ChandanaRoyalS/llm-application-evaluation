"""Statistics used by every report (EVAL_SPEC.md §6)."""
import math
import random


def wilson(successes, n, z=1.96):
    """95% Wilson score interval for a proportion. Returns (low, high), or (None, None) if n == 0."""
    if n == 0:
        return None, None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def proportion(flags):
    """Summarize a list of booleans: value, n, and 95% Wilson CI."""
    flags = list(flags)
    n = len(flags)
    k = sum(1 for f in flags if f)
    lo, hi = wilson(k, n)
    return {"value": (k / n) if n else None, "k": k, "n": n, "ci_low": lo, "ci_high": hi}


def paired_bootstrap_diff(a, b, iters=10_000, seed=0):
    """95% CI of mean(a) - mean(b) for paired per-case scores (same cases, same order)."""
    if len(a) != len(b) or not a:
        raise ValueError("paired samples must be non-empty and the same length")
    rng = random.Random(seed)
    n = len(a)
    diffs = []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        diffs.append(sum(a[i] - b[i] for i in idx) / n)
    diffs.sort()
    point = sum(x - y for x, y in zip(a, b)) / n
    return {"diff": point, "ci_low": diffs[int(0.025 * iters)], "ci_high": diffs[int(0.975 * iters) - 1]}


def mcnemar_exact(a, b):
    """Exact two-sided McNemar p-value for paired pass/fail lists."""
    b01 = sum(1 for x, y in zip(a, b) if x and not y)
    b10 = sum(1 for x, y in zip(a, b) if y and not x)
    n = b01 + b10
    if n == 0:
        return 1.0
    k = min(b01, b10)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def percentile(values, q):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    pos = (len(values) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def cohens_kappa(a, b):
    """Cohen's kappa for two lists of binary labels."""
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("need two non-empty label lists of equal length")
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)
