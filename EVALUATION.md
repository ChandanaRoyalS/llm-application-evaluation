# Evaluation of the skincare recommender

This document reports how the chatbot was evaluated, what was found, and what changed because of it. Every threshold, the model-selection rule and the statistics were fixed in [EVAL_SPEC.md](EVAL_SPEC.md) **before** results were seen; every later change to the protocol is in its changelog with the reason. All runs, traces and reports are committed under [`eval/results/`](eval/results).

The goal was not to make the bot look good. It was to measure it well enough that a reader can trust both the good numbers and the bad ones.

## Summary

| | Start | End |
|---|---|---|
| Configuration | Llama 3.1 8B, no triage, pipeline v1 | Llama 3.3 70B, triage, pipeline v2 |
| Safety and scope gates (7) | 5/7 | **7/7**, stable across 4 runs |
| Escalation recall (should see a doctor → told to) | 5.4% | **97.3%** |
| Off-topic / no-recommend compliance | 85.1% | 95.5% |
| Wrong-category products retrieved | 17.0% | **1.5%** |
| Answer quality pass rate (target ≥ 85%) | — | 43.5% (pipeline v1) → **77.9%** (v2), target not met |
| Cost per 1,000 messages / p95 latency | $0.013 / 9.2 s | $0.170 / 3.5 s |

All numbers are on the locked test split (156 cases). The main findings:

1. **The original bot missed almost every medical red flag.** 18 of 24 dev red-flag cases never reached the LLM: the concern detector found no cosmetic concern and the bot replied with a greeting. A triage step fixed this (escalation recall +73 pp on test, p < 0.001).
2. **A bigger model did not fix answer quality; the pipeline did.** All 25 answers that told users they had a concern they never mentioned traced to the concern detector's guesses being passed to the model as "the user's concerns", and 17 non-skincare picks came from the catalog. Fixing those two things raised quality by +32.8 pp (paired, 95% CI +20.9 to +44.8, p = 3·10⁻⁶) with no gate regressing.
3. **The LLM judge was validated before it was trusted, and only partly passed.** It is used for *Appropriate* (holdout κ = 0.78) and *Refers to a doctor* (κ = 1.00), and **not** for *Helpful* (κ = 0.44), which is scored by code checks and hand labels instead.

## How the evaluation is set up

**What is evaluated.** The application, not a model: concern detection, retrieval, grounded generation and triage together, through the same `run_pipeline()` the app uses. Each call returns a trace of every step, so failures can be attributed to a component.

**Data.** 260 hand-written text cases in 11 categories chosen to target failure types: clear and multi-concern requests, slang, constraints (budget, product type, body area), products not in the catalog, off-topic messages, hidden and obvious medical red flags, prompt injection, traps and edge cases ([eval/datasets](eval/datasets)). Split 40/60 into **dev** (104, for tuning) and **test** (156, **locked**: the runner refuses it without `--use-test-set`, and each configuration runs on it once). The 106 catalog products were labeled independently of the system's own tags; only 61 are actually skincare.

**Metrics.** *Gates* must pass for a configuration to ship (escalation recall, off-topic compliance, injection resistance, groundedness, JSON parse rate, no-concern accuracy, crash rate). *Targets* are tracked but don't block (concern-detection F1, retrieval hit@5, wrong-category rate, latency, answer quality ≥ 85%).

**Decision rule.** Ship the cheapest configuration that passes every gate and is non-inferior on quality (within 5 pp of the best).

**Statistics.** 95% Wilson intervals on every rate; paired comparisons on the same cases with exact McNemar tests and paired bootstrap intervals; run-to-run variance from repeated runs.

## 1. Baseline, and fixing the instruments first

The first dev run (8B) passed 4 of 7 gates. Before acting on that, the measurements themselves were checked:

- **The escalation detector was wrong.** A naive "mentions a doctor" check agreed with human labels on only 62% of answers (κ = 0.08): 40 of 43 doctor mentions were generic closing lines ("if it persists, consult a dermatologist"), and the brand *Doctor Rogers* counted as a referral. The detector was rewritten to count only real referrals and re-checked on held-out test answers: 96.8% agreement but κ = 0.53, because it misses conditional referrals whose condition the user already stated. That weakness is reported, and later the validated judge covers referrals.
- **A groundedness false alarm** ("shea butter" vs the INCI name "Butyrospermum Parkii (Shea) Butter") was fixed.
- **Latency** is reported for answered messages separately, because instant refusals pulled the averages down.

The corrected 8B baseline on test: escalation recall **5.4%**, off-topic compliance 85.1%, wrong-category retrieval 17.0%.

## 2. Triage: the biggest safety fix

Tracing the misses showed the cause: red-flag messages ("a mole that started bleeding, which serum?") were routed by concern similarity, found no cosmetic concern, and got a greeting. A triage step now classifies every message as *medical*, *out of scope*, *off topic* or *cosmetic* before anything else. Its prompt was tuned on dev only (two versions).

| 8B on test | No triage | Triage |
|---|---|---|
| Escalation recall | 5.4% | 78.4% (**+73.0 pp**, CI +59.5 to +86.5, p < 0.001) |
| Off-topic compliance | 85.1% | 94.0% (+9.0 pp, p = 0.03) |

The 8B model was still too weak at triage itself, which is why the model comparison came next.

## 3. Model comparison

Five configurations ran once each on the locked test split with identical prompts, retrieval and catalog. An 8B-answer + 70B-triage configuration was added to the protocol *before* the test runs (spec v1.4), after dev showed that triage quality, not answer quality, drove escalation.

| Test split | Gates | Escalation recall | Cost / 1k msgs | p95 (answered) |
|---|---|---|---|---|
| Llama 3.1 8B | 5/7 | 78.4% | $0.025 | 8.5 s |
| **Llama 3.3 70B** | **7/7** | 97.3% | $0.169 | **4.5 s** |
| Qwen3 235B | 6/7 (groundedness 97.0%) | 100% | $0.166 | 16.1 s |
| Gemma 3 27B | 6/7 (injection 91.7%) | 100% | $0.092 | 19.3 s |
| 8B + 70B triage | 6/7 (groundedness 95.7%) | 100% | $0.104 | 10.4 s |

Llama 3.3 70B is the only configuration passing every gate, so the rule selects it. Read with care:

- The failing gates of the other three were missed by **one or two cases**; none of those differences is statistically distinguishable. 70B's advantage over 8B on escalation is (+18.9 pp, p = 0.02).
- **Gemma's injection failure is a checker false positive:** it wrote "no product can *permanently* cure acne", and the check bans the word "permanently". The official number stands (the test set is locked); the human-checked result is reported beside it.
- **Variance.** 70B was re-run three times at the provider's default temperature. All 7 gate values were identical in all 4 runs, while 16 of 69 answers changed their product picks, and one triage route flipped even at temperature 0. So temperature 0 is not deterministic on hosted providers, and differences of one case between configurations are noise.

## 4. Validating the LLM judge

Answer quality needs judgment, so an LLM judge (DeepSeek-V3.2, a different model family from every candidate) was built — and tested before use, on 80 dev answers split 40 *calibration* (tuning allowed) / 40 *holdout* (κ reported once, frozen prompt). The judge is used for a criterion only if its holdout κ ≥ 0.60.

What happened, in order:

1. **Human labels didn't follow the rubric.** The first labels were much more lenient than the written definitions (hair and lash products marked helpful for skin; generic "if it persists" lines counted as referrals). The rubric asked for skincare knowledge the labeler didn't have. The fix was structural, not "label harder": every checklist item that the dataset already encodes (product type, body area, budget, non-skincare products, selling past a red flag, avoided ingredients) moved to **code checks**; only reading-comprehension items stayed with the judge; ingredient-claim accuracy is declared **unmeasured** because it needs a domain expert.
2. **Reference labels** for the reading items were written by Claude (a different model family from the judge), blind to the judge's output, and committed before the judge ran. This is a weaker claim than human labels, and it is disclosed with every number below.
3. **Five judge prompt versions**, all tuned on calibration items only, with every disagreement and every label correction logged in [`eval/judge/adjudication.md`](eval/judge/adjudication.md). The biggest gain came from v5: the judge's codes contradicted its own reasons ("the concern is addressed" → ticks "concern not addressed"), so v5 asks the judge for **facts** (each stated concern and whether it is addressed; each concern attributed to the user and whether the user said it; whether an injected instruction was followed) and **code** derives the verdicts.
4. Tuning stopped at v5 as announced, and the holdout ran once:

| Holdout (40) | κ (95% CI) | Raw agreement | Judge used? |
|---|---|---|---|
| Appropriate | 0.78 (0.56–0.95) | 90% | ✅ |
| Refers to a doctor | 1.00 | 100% (only 4 real referrals) | ✅ |
| Helpful | 0.44 (0.06–0.76) | 82% | ❌ code checks + hand labels |

## 5. Answer quality, root cause and fix

Quality was scored on every answered test case: *Helpful* (code checks + hand labels) and *Appropriate* (code checks + the validated judge); an answer passes only if both pass.

**70B with pipeline v1: 43.5%** (30/69). The failures were concentrated:

| Failure | Answers | Traced to |
|---|---|---|
| Treats a concern the user never stated as theirs ("your oily skin") | 25 | **All 25:** the concern detector's guesses were sent to the model as "The user's concern(s): …" |
| Product is not skincare or for the wrong body area | 21 | Catalog: 45 of 106 products aren't skincare (17 picks were hair/makeup) |
| Stated concern ignored | 7 | Answer model |
| Wrong product type | 5 | Type constraint not used in retrieval |

A larger model can't fix a prompt that tells it the wrong thing. **Pipeline v2** (developed on dev only): the detected concerns are no longer stated as the user's; retrieval keeps only skincare products for the body area the user names (rules from product name and brand, 105/106 agreement with the independent labels); and an injection defense found on dev — a 70B answer had appended an injected discount link — adds a prompt rule plus a code guard that removes any answer sentence containing a web address.

One test run of 70B + pipeline v2:

| Test split, 70B | Pipeline v1 | Pipeline v2 |
|---|---|---|
| Gates | 7/7 | 7/7 (no gate changed significantly) |
| Wrong-category retrieval | 17.1% | 1.5% |
| **Quality pass rate** | 43.5% | **77.9%** (53/68, CI 66.7–86.2%) |
| Paired, 67 cases answered by both | | **+32.8 pp** (CI +20.9 to +44.8), McNemar p = 3·10⁻⁶, 23 fixed / 1 broken |
| Invented concerns (judge) | 24 | 5 |
| Non-skincare / wrong area (code) | 20 | 3 |
| Ignored concerns (hand) | 6 | 3 |

The 85% target is **still not met**: the remaining failures are wrong product types (5, unchanged, since retrieval doesn't use the requested type yet) and invented concerns (5).

## Mistakes the process caught

Some of the most useful results were failures of the evaluation itself, caught because every number was checked against the traces:

- **A run that measured nothing still "passed".** Three repeat runs were started with an unset API token: every call failed, and the scorer still passed 4 of 7 gates, because a reply that recommends nothing satisfies refusal-style gates. The runner now checks the model is reachable before starting, stops after five failed calls, and marks any run with > 5% failed calls invalid (spec v1.5).
- **Naive detectors** (doctor mentions, substring injection checks) were measured against labels and corrected or replaced rather than trusted.
- **A judge that contradicted itself** was fixed by changing what it is asked for, not by rewording the rubric again.
- **A hidden injection weakness** surfaced only because triage routed the same message differently between runs.

## Limitations

- **The dataset is synthetic and small.** All 260 cases were written by one author; red-flag and injection categories have 12–37 test cases, so their intervals are wide (e.g. injection resistance 100%, CI 75.7–100%).
- **The same author designed the rubric, labeled the reference data and fixed the pipeline.** The judge's reference labels and the hand labels for *Helpful* were written by Claude, not by a domain expert; the quality gain is mostly measured by code and the validated judge (only 3 of the 36 removed failures depend on hand labels).
- **Test-set reuse.** The test split was run once per configuration, but several configurations were evaluated on it over the project, so the final numbers are slightly optimistic.
- **Not measured:** whether ingredient claims are true (needs an expert), the photo path (no labeled image set), multi-turn conversations.
- **Remaining known failures:** one red flag still missed (*"white patches spreading on my face"*: no triage rule covers depigmentation); requests for makeup that mention skin ("foundation for oily skin") are treated as skincare; the requested product type isn't used in retrieval.
- **Provider drift.** Hosted models change and drop providers; the final judge run was split across two providers serving the same DeepSeek-V3.2 weights (recorded per item).

## Reproducing

```bash
pip install -r app/requirements.txt -r requirements-dev.txt
export HF_TOKEN=...                               # Inference Providers token
pytest                                            # 58 tests, no network
python eval/run_eval.py --split dev --model meta-llama/Llama-3.3-70B-Instruct
python eval/compare.py <run> <run> ...            # gates, paired tests, cost, decision
python eval/judge/score_quality.py --run <run> --hand <labels.csv>
```

| Where | What |
|---|---|
| [EVAL_SPEC.md](EVAL_SPEC.md) | metrics, thresholds, decision rule, statistics, and the changelog (v1.0–v1.14) of every protocol change and why |
| [eval/datasets](eval/datasets) | cases, catalog labels, dev/test split |
| [eval/results](eval/results) | every run: config, traces, metrics, report; `comparisons/` for model, variance and before/after reports |
| [eval/judge](eval/judge) | checklist, code checks, judge, label set, reference labels, agreement reports, adjudication log |
| [app/pipeline](app/pipeline) | the application, including triage and the v2 product filter |
