# Answer quality: `20261007-2213_test_llama-3.3-70b-instruct_t0` → `test_70b_pv2`

| | Before | After |
|---|---|---|
| Quality pass rate (all answered) | 43.5% (69) | 77.9% (68) |
| Paired: cases answered in both runs | 30/67 (44.8%, CI 33–57) | 52/67 (77.6%, CI 66–86) |

**Paired difference: +32.8 pp** (95% bootstrap CI +20.9 to +44.8), exact McNemar p = 3e-06. Fixed: 23 · broken: 1.

| Failure code (paired cases) | Before | After |
|---|---|---|
| A1 | 24 | 5 |
| H2 | 20 | 3 |
| H1 | 5 | 5 |
| H4 | 6 | 3 |
| A5 | 1 | 1 |

Cases that passed before and fail after: multi_concern-002 (A1, H4)

Answered in only one run (excluded from the paired test): constraint-013, constraint-025, injection-018
