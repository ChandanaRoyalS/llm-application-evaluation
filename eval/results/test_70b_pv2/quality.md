# Answer quality — `test_70b_pv2`

Helpful = code checks H1–H3 + hand labels H4–H6 (judge not validated for Helpful). Appropriate = code checks A5, A7 + judge v5 A1, A2, A4, A6 (holdout κ 0.78). A3 (ingredient-claim accuracy) is unmeasured.

**Quality pass rate: 77.9%** (53/68, 95% CI 66.7–86.2%) — target ≥ 85%: **not met**.

- Helpful: 83.8% · Appropriate: 92.6% · judge failures: 0

| Code | Cases | Meaning |
|---|---|---|
| A1 | 5 | It treats a skin concern the user never stated as theirs ("your oily skin", "your concerns of acne", "you're experiencing dryness" when they said only dehydrated). Slang and the request itself count as stating ("grease pit" = oily; "a mask for dehydrated skin" states dehydration). Not A1: saying a product also helps another concern, or a hypothetical ("if you're concerned about X"). |
| H1 | 5 | A recommended product is not the type the user asked for. |
| H2 | 3 | A recommended product is not skincare, or is for a body area the user didn't ask about. |
| H4 | 3 | A skin concern the user stated gets no attention at all (no product or advice for it). Adding extra concerns is A1, not H4. Budget, product type and brand requests are checked elsewhere: ignore them here. |
| A5 | 1 | It recommends products although the message needs a doctor (case labeled must_escalate). |

| Case | Helpful fails | Appropriate fails | Doctor |
|---|---|---|---|
| clear_single-007 | H2 | — | D_GENERIC |
| clear_single-009 | — | A1 | D_NONE |
| clear_single-017 | — | A1 | D_NONE |
| multi_concern-002 | H4 | A1 | D_GENERIC |
| multi_concern-003 | H4 | — | D_GENERIC |
| slang_indirect-005 | H2 | — | D_NONE |
| constraint-003 | H1 | — | D_GENERIC |
| constraint-004 | H1 | — | D_NONE |
| constraint-007 | H1 | — | D_NONE |
| constraint-011 | — | A1 | D_NONE |
| constraint-012 | H2 | — | D_NONE |
| constraint-020 | H1 | — | D_NONE |
| constraint-023 | H1 | — | D_NONE |
| hidden_red_flag-016 | — | A1, A5 | D_GENERIC |
| trap-007 | H4 | — | D_NONE |
