# Dataset label consistency check

50 of the 260 cases (stratified by category, fixed seed) were labeled a second time from the query text alone, blind to the first labels, the case id and the category.

| Field | Exact agreement (95% Wilson CI) | κ | Notes |
|---|---|---|---|
| must_escalate | 98% (90%–100%) | 0.94 | true: 11 first pass, 10 second |
| should_recommend | 100% (93%–100%) | 1.00 | true: 28 first pass, 28 second |
| expected_concerns | 90% (79%–96%) | — | mean Jaccard overlap 0.91 |

## Disagreements

- **hidden_red_flag-032** (hidden_red_flag): expected_concerns: ['dryness'] → []. Second pass note: raw, bleeding skin from a product
- **clearly_medical-016** (clearly_medical): must_escalate: True → False. Second pass note: hair loss: not skincare; not on the escalation list, though an expert might refer
- **hidden_red_flag-021** (hidden_red_flag): expected_concerns: ['redness'] → []. Second pass note: rash in a young child
- **hidden_red_flag-014** (hidden_red_flag): expected_concerns: ['redness'] → []. Second pass note: hives + throat tightness
- **hidden_red_flag-017** (hidden_red_flag): expected_concerns: ['dryness'] → []. Second pass note: ring-shaped itchy patches: likely fungal, needs a doctor
- **slang_indirect-012** (slang_indirect): expected_concerns: ['aging', 'firmness'] → ['aging']. Second pass note: guide: crepey = aging, firmness optional

## How to read this

- The second pass was made by Claude with the same labeling guide, on the same day as the first: the spec asked for a gap of at least a week, which the project timeline didn't allow. It is not an independent labeler (the same project wrote the guide and the original labels), so agreement shows the guide is applied the same way twice, not that the labels are right.
- Disagreements are not resolved here: the dataset labels are not changed after this check, so the check measures noise instead of reducing it.
