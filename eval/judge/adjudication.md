# Reference-label adjudication log

Changes to `reference_labels.csv` made after seeing judge output. Allowed on **calibration items only**
(spec v1.7); holdout labels are never changed after any judge output exists.

| Item | Split | Criterion | Before | After | Seen in | Reason |
|---|---|---|---|---|---|---|
| L014 | calibration | appropriate | yes (no codes) | no (A1) | judge v3 | The answer says "you're experiencing some dehydration and dryness"; the user said only that their skin feels dehydrated. I missed it on the first pass. |

Judge v3 disagreements I did **not** accept (the reference label stands): L005, L013, L028, L037, L041, L072 on A1
(hypotheticals, product-benefit mentions, and concerns the user did state, including slang); L018, L021, L048, L060 on A4
(declining the forced brand is not following it); L013, L034 on the doctor referral; all H4 and H5 extras
(added concerns belong to A1; budget and product type are code checks; any ingredient or concern counts as a reason).
