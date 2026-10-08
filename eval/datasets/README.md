# Evaluation datasets

| File | What it is |
|---|---|
| `source_cases.py` | the test cases, written by hand: **edit here** |
| `catalog_labels.csv` | independent labels for all 106 catalog products |
| `build_dataset.py` | derives relevance labels, ids and the split; writes the `.jsonl` files |
| `dev.jsonl` | 104 cases for development and tuning |
| `test.jsonl` | 156 cases, **locked** for final results only |
| `label_consistency.py` | blind re-label of 50 cases and agreement with the dataset labels (`label_consistency.md`) |
| `build_smoke.py` → `smoke.jsonl` | 24 dev cases chosen by a fixed rule (first N per category), run by the CI eval gate on every pull request |

Rebuild after any change, then validate:

```bash
python eval/datasets/build_dataset.py
python eval/validate_dataset.py
python eval/datasets/build_smoke.py   # only if dev.jsonl changed
```

Labeling rules: [`eval/labeling_guide.md`](../labeling_guide.md).

## Composition (v1)

260 text cases across 11 categories. 61 must escalate to a doctor; 150 should get product recommendations.

| Category | Dev | Test |
|---|---|---|
| clear_single | 16 | 24 |
| multi_concern | 12 | 18 |
| slang_indirect | 12 | 18 |
| constraint | 10 | 15 |
| not_in_catalog | 8 | 12 |
| off_topic | 6 | 9 |
| hidden_red_flag | 16 | 24 |
| clearly_medical | 8 | 12 |
| injection | 8 | 12 |
| trap | 4 | 6 |
| edge_case | 4 | 6 |

## What the product labels already show

Labeled independently of the system's own tags, **only 61 of the 106 catalog products are skincare** (including sunscreen and body, hand and lip care). The rest are haircare (25), makeup (15), fragrance (3), a bath soak and a device gel. This is the baseline for the data-layer metric in `EVAL_SPEC.md` §3.2.

## Known limitations

- **All cases are synthetic.** They were written for this evaluation, not collected from real users.
- **Single annotator, not yet independently reviewed.** The label-consistency re-check and the one-by-one review of synthetic cases required by `EVAL_SPEC.md` §4 haven't been done for v1. Results are reported with that caveat.
- **Ingredient checks use the first 8 listed ingredients** stored in the catalog, so allergy and fragrance-free rules can miss an ingredient further down the list.
- **Product concern labels** come from product names and listed ingredients; rows marked `low` confidence are uncertain.
- **No photo set yet.** Photo cases need images whose license permits this use; they'll be added separately.
