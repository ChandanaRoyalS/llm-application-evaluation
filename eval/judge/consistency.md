# Labeler consistency check

The same labeler (Claude) labeled 20 of the 80 judge items a second time, blind to the first labels; the sample was drawn with a fixed seed (10 calibration, 10 holdout). Only the reading codes are compared.

| Criterion | Raw agreement (95% Wilson CI) | κ (bootstrap 95% CI) | Fails, first pass | Fails, second pass |
|---|---|---|---|---|
| helpful (reading codes) | 100% (84%–100%) | 1.00 (1.00–1.00) | 1 | 1 |
| appropriate (reading codes) | 100% (84%–100%) | 1.00 (1.00–1.00) | 7 | 7 |
| refers to a doctor | 100% (84%–100%) | 1.00 (1.00–1.00) | 2 | 2 |

| Code | Both passes | First only | Second only |
|---|---|---|---|
| H4 | 1 | 0 | 0 |
| H5 | 0 | 0 | 0 |
| H6 | 0 | 0 | 0 |
| A1 | 7 | 0 | 0 |
| A4 | 0 | 0 | 0 |
| A2 | 0 | 0 | 0 |
| A6 | 0 | 0 | 0 |

Doctor code (D_YES / D_GENERIC / D_NONE) identical on 20/20 items.

## Disagreements

None.

## How to read this

- κ is undefined (—) when a criterion has no failures in either pass. When the two passes agree on every item, the bootstrap interval collapses to a point; the Wilson interval on raw agreement is the honest range (20/20 is consistent with true agreement as low as about 84%).
- Failures are rare (a handful per criterion), so this mostly confirms the passes agree on the common cases and on the few failures sampled; it cannot rule out disagreement on rarer codes (H5, H6, A2, A4, A6 never occurred in the sample).
- Both passes were made by the same AI model with the same written checklist. Agreement shows the checklist is applied the same way twice; it does not show the labels are right. That needs an independent (ideally expert) labeler, which the project doesn't have.
