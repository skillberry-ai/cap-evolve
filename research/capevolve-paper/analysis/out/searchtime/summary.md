# Search-time results (latest run state)

Data: run artifacts under campaign-scratch/runs and analysis/out/metrics, newest gateway call 2026-10-12T15:51:17Z. Regenerate with `analysis/scripts/searchtime_results.py`.

**Caveat.** Every number here is search-time, on the search/selection split of its own method, not held-out. Selection-split scores are optimistic and not comparable across methods: GEPA selects the best candidate on its selection split, Meta-Harness's proposer saw val aggregates, CapEvolve screens on its own split, and Suites B and C use different split sizes per method. No cross-method ranking may be drawn from these numbers. Final results exist only after the 2026-10-13 06:00 UTC cutoff.

## Per arm and seed

| suite | arm | seed | split | rollouts | seed score | champion (id) | gain | gen/scr/prom | returned=seed | opt tok (non-cache) | cache read | USD | wall h | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | hc | 0 | val-40 | 568 | 0.579 | 0.750 (cand_0003) | 0.171 | 4/5/1 | False | 206870 | 926172 | 0.8051 | 25.1 | running |
| A | hc | 1 | val-40 | 600 | 0.590 | 0.692 (cand_0001) | 0.103 | 2/5/1 | False | 87560 | 399706 | 0.3373 | 21.2 | native finish (budget) |
| A | hc | 2 | val-40 | 480 | 0.568 | 0.568 (seed) | 0.000 | 9/7/0 | True | 446458 | 2010781 | 1.7377 | 25.2 | running |
| A | ao | 0 | val-20 | 262 | 0.462 | 0.462 (seed) | 0.000 | 1/1/0 | True | 3958447 | 1715039 | 10.3835 | 21.4 | native finish (budget) |
| A | ao | 1 | val-40 | 404 | 0.447 | 0.447 (seed) | 0.000 | 1/1/0 | True | 990763 | 1653780 | 2.9188 | 20.0 | stopped (unclassified) |
| A | ao | 2 | val-20 | 380 | 0.684 | 0.684 (seed) | 0.000 | 1/1/0 | True | 1602367 | 1707744 | 4.4682 | 20.6 | stopped (unclassified) |
| A | gepa | 0 | val-40 | 600 | 0.525 | 0.850 (c2) | 0.325 | 19/9/9 | False | 603717 | 0 | 2.1082 | 26.1 | crash |
| A | gepa | 1 | val-40 | 600 | 0.525 | 0.875 (c5) | 0.350 | 13/10/10 | False | 424746 | 0 | 1.4271 | 29.1 | crash |
| A | gepa | 2 | val-40 | 600 | 0.425 | 0.800 (c8) | 0.375 | 16/9/9 | False | 427579 | 0 | 1.3864 | 25.8 | crash |
| A | skillopt | 0 | val-40 | 526 | 0.625 | 0.775 (step_0004) | 0.150 | 8/4/3 | False | 3572673 | 0 | 8.1299 | 28.3 | native finish |
| A | skillopt | 1 | val-40 | 600 | 0.550 | 0.850 (step_0003) | 0.300 | 7/6/4 | False | 4778086 | 0 | 10.418 | 27.0 | crash |
| A | skillopt | 2 | val-40 | 566 | 0.525 | 0.800 (step_0005) | 0.275 | 8/5/6 | False | 5102141 | 0 | 11.1817 | 26.7 | native finish |
| A | metaharness | 0 | val-40 | 600 | 0.600 | 0.975 (example_calibration) | 0.375 | 8/8/3 | False | 161527 | 572668 | 0.6715 | 19.6 | native finish |
| A | metaharness | 1 | val-40 | 600 | 0.625 | 0.875 (typed_value_fidelity) | 0.250 | 8/8/4 | False | 175419 | 836229 | 0.7676 | 20.0 | native finish |
| A | metaharness | 2 | val-40 | 600 | 0.600 | 0.900 (example_reproduce) | 0.300 | 8/8/4 | False | 214291 | 905568 | 0.9386 | 22.4 | native finish |
| A | evoskill | 0 | val-40 | 332 | 0.550 | 0.800 (iter-skill-17) | 0.250 | 6/6/6 | False | 387197 | 497881 | 1.259 | 12.3 | native finish |
| A | evoskill | 1 | val-40 | 452 | 0.550 | 0.875 (iter-skill-14) | 0.325 | 9/9/7 | False | 785636 | 531669 | 2.331 | 18.4 | native finish |
| A | evoskill | 2 | val-40 | 452 | 0.550 | 0.850 (iter-skill-9) | 0.300 | 9/9/5 | False | 744375 | 574377 | 2.2246 | 17.1 | native finish |
| A | wikiskill | 0 | val-40 | 521 | 0.575 | 0.800 (it004) | 0.225 | 4/4/2 | False | 427282 | 351970 | 1.212 | 26.5 | running |
| A | wikiskill | 1 | val-40 | 371 | 0.525 | 0.825 (it002) | 0.300 | 3/2/2 | False | 313073 | 315890 | 0.9641 | 26.8 | running |
| A | wikiskill | 2 | val-40 | 350 | 0.500 | 0.650 (it001) | 0.150 | 2/2/1 | False | 201538 | 137826 | 0.5978 | 26.8 | running |
| A | trace2skill | 0 | val-40 | 200 | 0.500 | 0.700 (error) | 0.200 | 2/2/1 | False | 2202310 | 0 | 6.8207 | 15.6 | native finish |
| A | trace2skill | 1 | val-40 | 200 | 0.525 | 0.800 (combined) | 0.275 | 2/2/1 | False | 2225291 | 0 | 6.958 | 14.2 | native finish |
| A | trace2skill | 2 | val-40 | 200 | 0.525 | 0.750 (combined) | 0.225 | 2/2/1 | False | 2085988 | 0 | 6.4927 | 16.1 | native finish |
| A | ace | 0 | val-40 | 379 | 0.800 | 0.800 (epoch1_end) | 0.000 | 1/0/0 | True | 3902518 | 0 | 9.5622 | 14.9 | running |
| A | ace | 1 | -- | 160 | -- | -- (--) | -- | 0/0/0 | None | 1468887 | 0 | 3.8498 | 14.8 | running |
| A | ace | 2 | -- | 149 | -- | -- (--) | -- | 0/0/0 | None | 1346489 | 0 | 3.5812 | 14.7 | running |
| A | mipro | 0 | val-40 | 212 | 0.575 | 0.575 (3d5fee3dfdc1) | 0.000 | 9/0/0 | True | 178651 | 0 | 0.5792 | 26.8 | running |
| A | mipro | 1 | val-40 | 252 | 0.550 | 0.850 (cc2319ac81ff) | 0.300 | 12/1/0 | False | 181449 | 0 | 0.6009 | 26.8 | running |
| A | mipro | 2 | val-40 | 210 | 0.600 | 0.600 (3d5fee3dfdc1) | 0.000 | 8/0/0 | True | 178826 | 0 | 0.5906 | 26.8 | running |
| B | hc | 0 | opt-49 | 490 | 0.531 | 0.531 (seed) | 0.000 | 2/2/0 | True | 348306 | 4071946 | 2.0054 | 27.2 | running |
| B | hc | 1 | opt-49 | 539 | 0.653 | 0.653 (seed) | 0.000 | 10/10/0 | True | 705711 | 6452540 | 3.5336 | 27.2 | running |
| B | hc | 2 | opt-49 | 490 | 0.542 | 0.542 (seed) | 0.000 | 2/2/0 | True | 248637 | 3016017 | 1.4563 | 27.2 | running |
| B | ao | 0 | opt-49 | 198 | 0.604 | 0.604 (seed) | 0.000 | 2/0/0 | True | 1018932 | 9478573 | 4.9191 | 11.6 | native finish |
| B | ao | 1 | opt-49 | 197 | 0.612 | 0.612 (seed) | 0.000 | 1/0/0 | True | 842779 | 10229243 | 4.701 | 20.9 | native finish |
| B | ao | 2 | opt-49 | 172 | 0.612 | 0.612 (seed) | 0.000 | 0/0/0 | True | 1499933 | 16113691 | 7.7435 | 27.2 | running |
| B | gepa | 0 | sel-25 | 329 | 0.600 | 0.720 (cand_0004) | 0.120 | 19/6/6 | False | 550816 | 0 | 1.9925 | 27.2 | running |
| B | gepa | 1 | sel-25 | 361 | 0.400 | 0.760 (cand_0018) | 0.360 | 20/8/8 | False | 508228 | 0 | 1.829 | 27.2 | running |
| B | gepa | 2 | sel-25 | 338 | 0.600 | 0.720 (cand_0015) | 0.120 | 23/6/6 | False | 541878 | 0 | 1.8404 | 27.2 | running |
| B | harnesslens | 0 | -- | 123 | -- | -- (--) | -- | 0/0/0 | None | 4800127 | 669249 | 12.8626 | 17.6 | running |
| B | harnesslens | 1 | -- | 173 | -- | -- (--) | -- | 0/0/0 | None | 4879714 | 1964929 | 14.643 | 17.5 | running |
| B | harnesslens | 2 | -- | 162 | -- | -- (--) | -- | 0/0/0 | None | 6515450 | 1412242 | 17.6206 | 17.5 | running |
| B | oneshot | 0 | opt-49 | 123 | 0.562 | 0.562 (seed) | 0.000 | 1/1/0 | True | 174123 | 2014245 | 0.9993 | 5.1 | native finish (iterations) |
| B | oneshot | 1 | opt-49 | 148 | 0.571 | 0.714 (cand_0001) | 0.143 | 1/1/1 | False | 199013 | 3352636 | 1.3734 | 4.9 | native finish (iterations) |
| B | oneshot | 2 | opt-49 | 123 | 0.653 | 0.653 (seed) | 0.000 | 1/1/0 | True | 141128 | 1531722 | 0.7744 | 4.4 | native finish (iterations) |
| B | seed | 0 | opt/sel | 98 | opt 0.561 / sel 0.600 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.5 | native finish |
| B | seed | 1 | opt/sel | 98 | opt 0.602 / sel 0.580 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.5 | native finish |
| B | seed | 2 | opt/sel | 98 | opt 0.653 / sel 0.620 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.8 | native finish |
| C | hc | 0 | opt-20 | 320 | 0.450 | 0.600 (cand_0003) | 0.150 | 3/3/1 | False | 450271 | 4362982 | 2.3814 | 21.5 | running |
| C | hc | 1 | opt-20 | 240 | 0.450 | 0.450 (seed) | 0.000 | 5/5/0 | True | 385098 | 3352275 | 1.9114 | 21.5 | running |
| C | hc | 2 | opt-20 | 300 | 0.550 | 0.684 (cand_0005) | 0.134 | 8/8/1 | False | 605076 | 5287448 | 2.9597 | 21.5 | running |
| C | ao | 0 | opt-20 | 110 | 0.550 | 0.550 (seed) | 0.000 | 0/0/0 | True | 554012 | 5514194 | 2.7512 | 11.3 | native finish |
| C | ao | 1 | opt-20 | 110 | 0.550 | 0.550 (seed) | 0.000 | 0/0/0 | True | 564650 | 4051700 | 2.4403 | 7.7 | native finish |
| C | ao | 2 | opt-20 | 71 | 0.450 | 0.450 (seed) | 0.000 | 1/0/0 | True | 523420 | 2466110 | 1.975 | 9.8 | native finish |
| C | gepa | 0 | sel-10 | 198 | 0.800 | 1.000 (cand_0005) | 0.200 | 16/8/8 | False | 403234 | 0 | 1.6686 | 21.5 | running |
| C | gepa | 1 | sel-10 | 157 | 0.800 | 1.000 (cand_0013) | 0.200 | 13/6/6 | False | 340158 | 0 | 1.3661 | 21.5 | running |
| C | gepa | 2 | sel-10 | 191 | 0.900 | 1.000 (cand_0001) | 0.100 | 18/6/6 | False | 454657 | 0 | 1.6393 | 21.5 | running |
| C | oneshot | 0 | opt-20 | 60 | 0.500 | 0.737 (cand_0001) | 0.237 | 1/1/1 | False | 93027 | 1279390 | 0.5998 | 5.7 | native finish (iterations) |
| C | oneshot | 1 | opt-20 | 50 | 0.550 | 0.550 (seed) | 0.000 | 1/1/0 | True | 107372 | 1500867 | 0.7143 | 3.2 | native finish (iterations) |
| C | oneshot | 2 | opt-20 | 50 | 0.526 | 0.526 (seed) | 0.000 | 1/1/0 | True | 125833 | 1796170 | 0.8116 | 3.0 | native finish (iterations) |
| C | seed | 0 | opt/sel | 42 | opt 0.525 / sel 0.850 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.3 | native finish |
| C | seed | 1 | opt/sel | 40 | opt 0.550 / sel 0.850 | -- (--) | -- | 0/0/0 | None | None | None | None | 4.0 | native finish |
| C | seed | 2 | opt/sel | 42 | opt 0.575 / sel 0.750 | -- (--) | -- | 0/0/0 | None | None | None | None | 5.3 | native finish |
| A-E12 | hcstock | 0 | val-40 | 600 | 0.564 | 0.850 (cand_0007) | 0.286 | 12/12/2 | False | 496280 | 2086252 | 1.8706 | 17.0 | native finish (budget) |
| A-E12 | hcstock | 1 | val-40 | 600 | 0.526 | 0.875 (cand_0002) | 0.349 | 12/12/2 | False | 533805 | 2800926 | 2.1633 | 15.3 | native finish (budget) |
| A-E12 | hcstock | 2 | val-40 | 600 | 0.553 | 0.875 (cand_0004) | 0.322 | 12/12/3 | False | 520455 | 2128142 | 1.9638 | 15.4 | native finish (budget) |
| C-E12 | hcstock | 0 | opt-20 | 200 | 0.500 | 0.737 (cand_0001) | 0.237 | 9/9/1 | False | 663977 | 5433411 | 3.1357 | 18.8 | running |
| C-E12 | hcstock | 1 | opt-20 | 230 | 0.650 | 0.650 (seed) | 0.000 | 10/10/0 | True | 734093 | 7538800 | 3.9176 | 16.8 | native finish (iterations) |
| C-E12 | hcstock | 2 | opt-20 | 240 | 0.474 | 0.789 (cand_0002) | 0.316 | 10/10/2 | False | 749017 | 6133673 | 3.58 | 18.0 | native finish (iterations) |
| C-E12 | bestofk | 0 | opt-20 | 140 | 0.500 | 0.800 (prop_02) | 0.300 | 6/6/0 | False | 1327579 | 18298241 | 8.7779 | 13.6 | unknown |
| C-E12 | bestofk | 1 | opt-20 | 140 | 0.650 | 0.750 (prop_03) | 0.100 | 6/6/0 | False | 1150457 | 15406071 | 7.532 | 10.3 | unknown |
| C-E12 | bestofk | 2 | opt-20 | 160 | 0.474 | 0.800 (prop_01) | 0.326 | 7/7/0 | False | 1172177 | 16774685 | 7.7866 | 10.3 | unknown |

Notes: champion = what the method itself would return (CapEvolve: state best_id/best_val; GEPA, MIPRO, others: last selected or argmax of full selection-split evaluations). ACE and HarnessLens have no candidate/selection step yet. Optimizer USD covers priced (Claude) calls only; unpriced tokens are in runs.csv.

## Gate behaviour (CapEvolve)

| suite | arm | seed | cands | screens | confirms | promoted | rejected | vetoed | indecisive (reasons) | lost cands | lost attempts |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | hc | 0 | 4 | 2 | 1 | 1 | 0 | 1 | 1 coverage<0.95 (90%) x1 | 1 | 1 |
| A | hc | 1 | 2 | 1 | 1 | 1 | 0 | 0 | 0  | 1 | 1 |
| A | hc | 2 | 9 | 7 | 0 | 0 | 0 | 7 | 7 coverage<0.95 (92%) x7 | 2 | 3 |
| A | ao | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0  | 0 | 0 |
| A | ao | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0  | 0 | 0 |
| A | ao | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0  | 0 | 0 |
| B | hc | 0 | 2 | 2 | 1 | 0 | 2 | 0 | 0  | 0 | 0 |
| B | hc | 1 | 10 | 10 | 0 | 0 | 10 | 0 | 0  | 0 | 0 |
| B | hc | 2 | 2 | 2 | 1 | 0 | 2 | 0 | 0  | 0 | 0 |
| B | ao | 0 | 2 | 0 | 0 | 0 | 2 | 0 | 0  | 0 | 0 |
| B | ao | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0  | 0 | 0 |
| B | ao | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0  | 0 | 0 |
| C | hc | 0 | 3 | 3 | 2 | 1 | 2 | 0 | 0  | 0 | 0 |
| C | hc | 1 | 5 | 5 | 1 | 0 | 4 | 1 | 2 coverage<0.95 (90%) x2 | 0 | 0 |
| C | hc | 2 | 8 | 8 | 1 | 1 | 7 | 0 | 0  | 0 | 0 |
| C | ao | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0  | 0 | 0 |
| C | ao | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0  | 0 | 0 |
| C | ao | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 0  | 0 | 0 |
| A-E12 | hcstock | 0 | 12 | 12 | 0 | 2 | 10 | 0 | 0  | 0 | 0 |
| A-E12 | hcstock | 1 | 12 | 12 | 0 | 2 | 10 | 0 | 0  | 0 | 0 |
| A-E12 | hcstock | 2 | 12 | 12 | 0 | 3 | 9 | 0 | 0  | 0 | 0 |
| C-E12 | hcstock | 0 | 9 | 9 | 0 | 1 | 8 | 0 | 0  | 0 | 0 |
| C-E12 | hcstock | 1 | 10 | 10 | 0 | 0 | 10 | 0 | 0  | 0 | 0 |
| C-E12 | hcstock | 2 | 10 | 10 | 0 | 2 | 8 | 0 | 0  | 0 | 0 |

## Edits by capability surface (candidates touching surface / changed lines)

| suite | arm | cands | system_prompt | task_template | tool_code | mcp | skill_files | process_docs | reference | other |
|---|---|---|---|---|---|---|---|---|---|---|
| A | ao | 3 | 3 / 38 | 3 / 10 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | evoskill | 24 | 18 / 1499 | 0 / 0 | 0 / 0 | 0 / 0 | 18 / 1391 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | gepa | 48 | 43 / 3317 | 38 / 3205 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | hc | 12 | 12 / 212 | 12 / 26 | 0 / 0 | 0 / 0 | 0 / 0 | 10 / 3746 | 0 / 0 | 0 / 0 |
| A | metaharness | 24 | 24 / 394 | 24 / 197 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | mipro | 29 | 29 / 3541 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | skillopt | 23 | 23 / 253 | 23 / 959 | 0 / 0 | 0 / 0 | 23 / 1212 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | trace2skill | 6 | 6 / 224 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | wikiskill | 9 | 9 / 447 | 0 / 0 | 0 / 0 | 0 / 0 | 9 / 402 | 0 / 0 | 0 / 0 | 0 / 0 |
| A-E12 | hcstock | 36 | 36 / 829 | 36 / 165 | 0 / 0 | 0 / 0 | 0 / 0 | 36 / 13163 | 0 / 0 | 0 / 0 |
| B | ao | 3 | 3 / 35 | 0 / 0 | 3 / 306 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| B | gepa | 62 | 62 / 5310 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| B | hc | 14 | 9 / 110 | 0 / 0 | 14 / 607 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| B | oneshot | 3 | 3 / 53 | 0 / 0 | 3 / 217 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | ao | 1 | 1 / 13 | 0 / 0 | 1 / 151 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | gepa | 47 | 47 / 4105 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | hc | 16 | 16 / 182 | 0 / 0 | 16 / 1721 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | oneshot | 3 | 3 / 40 | 0 / 0 | 3 / 489 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C-E12 | bestofk | 19 | 19 / 540 | 0 / 0 | 19 / 4687 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C-E12 | hcstock | 29 | 28 / 394 | 0 / 0 | 29 / 3740 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

## Infra and errors (uniform classifier, main + chaser rows)

| suite | arm | rollouts | errors | infra | candidate | unverifiable |
|---|---|---|---|---|---|---|
| A | gepa | 826 | 24 | 24 | 0 | 0 |
| A | skillopt | 1780 | 187 | 66 | 121 | 0 |
| A | metaharness | 1800 | 90 | 90 | 0 | 0 |
| A | evoskill | 1250 | 41 | 41 | 0 | 0 |
| A | wikiskill | 1110 | 80 | 80 | 0 | 0 |
| A | trace2skill | 602 | 51 | 49 | 2 | 0 |
| A | ace | 709 | 33 | 33 | 0 | 0 |
| A | mipro | 664 | 21 | 20 | 1 | 0 |
| A | hc | 1680 | 113 | 31 | 82 | 0 |
| A | ao | 480 | 13 | 13 | 0 | 0 |
| A-E12 | hcstock | 2360 | 15 | 15 | 0 | 0 |
| B | seed | 444 | 0 | 0 | 0 | 0 |
| B | oneshot | 394 | 8 | 8 | 0 | 0 |
| B | gepa | 1016 | 0 | 0 | 0 | 0 |
| B | hc | 1519 | 7 | 7 | 0 | 0 |
| B | ao | 517 | 3 | 3 | 0 | 0 |
| C | seed | 180 | 0 | 0 | 0 | 0 |
| C | oneshot | 160 | 3 | 3 | 0 | 0 |
| C | gepa | 537 | 1 | 0 | 0 | 1 |
| C | hc | 860 | 14 | 14 | 0 | 0 |
| C | ao | 291 | 2 | 2 | 0 | 0 |
| C-E12 | hcstock | 810 | 6 | 6 | 0 | 0 |
