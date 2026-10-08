# Evaluation

Application evaluation of the skincare assistant. What is measured, and the pass thresholds, are defined in [`EVAL_SPEC.md`](../EVAL_SPEC.md); this folder implements it.

```
eval/
  datasets/           test cases, catalog labels, build + split (see datasets/README.md)
  labeling_guide.md   how every label is decided
  checks/
    components.py     per-case checks: concerns, retrieval, groundedness, safety, injection
    catalog.py        catalog facts used by the checks
    stats.py          Wilson intervals, paired bootstrap, McNemar
  run_eval.py         runs a split through the real pipeline, then scores it
  score.py            traces -> metrics.json + report.md (gates, targets, breakdowns)
  validate_dataset.py dataset sanity checks (also run in CI)
  results/<run>/      config.json, traces.jsonl, metrics.json, report.md
```

## Running an evaluation

Needs the real models, so it runs where Hugging Face is reachable (Python 3.10–3.12):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt
export HF_TOKEN=hf_...                                  # Inference Providers enabled

python eval/run_eval.py --split dev --limit 5           # smoke test
python eval/run_eval.py --split dev                     # full dev run
python eval/run_eval.py --split dev --model <model-id>  # another candidate
```

- The **test split is locked**: it only runs with `--use-test-set`, for final comparisons.
- An interrupted run resumes when re-run with the same `--run-name`.
- Re-score an existing run without calling any model: `python eval/score.py eval/results/<run>`.

## How each check decides

| Check | Method |
|---|---|
| Concern detection, retrieval | compared with dataset labels; relevance comes from independent product labels |
| Groundedness | code only: JSON parsed, no product number outside the context, every named ingredient present in the context (common names like "hyaluronic acid" or "vitamin C" are mapped to their INCI forms), no brand outside the context |
| Escalation | rule-based matcher for advice to see a dermatologist/doctor; to be checked against human labels before results are final (EVAL_SPEC §3.5) |
| No-recommend compliance | the structured list of recommended products is empty |
| Injection | no forbidden string, no leaked instructions, no invented product, no products when none should be recommended |
| Answer quality | **not yet**: needs the LLM judge and its validation against hand labels |
