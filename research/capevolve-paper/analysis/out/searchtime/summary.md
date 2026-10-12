# Search-time results (latest run state)

Data: run artifacts under campaign-scratch/runs and analysis/out/metrics, newest gateway call 2026-10-12T16:48:44Z. Regenerate with `analysis/scripts/searchtime_results.py`.

**Caveat.** Every number here is search-time, on the search/selection split of its own method, not held-out. Selection-split scores are optimistic and not comparable across methods: GEPA selects the best candidate on its selection split, Meta-Harness's proposer saw val aggregates, CapEvolve screens on its own split, and Suites B and C use different split sizes per method. No cross-method ranking may be drawn from these numbers. Final results exist only after the 2026-10-13 06:00 UTC cutoff.

## Per arm and seed

| suite | arm | seed | split | rollouts | seed score | champion (id) | gain | gen/scr/prom | returned=seed | opt tok (non-cache) | cache read | USD | wall h | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | hc | 0 | val-40 | 600 | 0.579 | 0.750 (cand_0003) | 0.171 | 4/3/1 | False | 206870 | 926172 | 0.8051 | 25.6 | native finish (budget) |
| A | hc | 1 | val-40 | 600 | 0.590 | 0.692 (cand_0001) | 0.103 | 2/1/1 | False | 87560 | 399706 | 0.3373 | 21.2 | native finish (budget) |
| A | hc | 2 | val-40 | 534 | 0.568 | 0.568 (seed) | 0.000 | 12/10/0 | True | 543765 | 2386052 | 2.0976 | 26.1 | running |
| A | ao | 0 | val-20 | 262 | 0.462 | 0.462 (seed) | 0.000 | 1/1/0 | True | 3958447 | 1715039 | 10.3835 | 21.4 | native finish (budget) |
| A | ao | 1 | val-40 | 404 | 0.447 | 0.447 (seed) | 0.000 | 1/1/0 | True | 990763 | 1653780 | 2.9188 | 20.0 | stopped (unclassified) |
| A | ao | 2 | val-20 | 380 | 0.684 | 0.684 (seed) | 0.000 | 1/1/0 | True | 1602367 | 1707744 | 4.4682 | 20.6 | stopped (unclassified) |
| A | gepa | 0 | val-40 | 600 | 0.525 | 0.850 (c2) | 0.325 | 19/9/9 | False | 603717 | 0 | 2.1082 | 26.1 | native finish (budget_cap) |
| A | gepa | 1 | val-40 | 600 | 0.525 | 0.875 (c5) | 0.350 | 13/10/10 | False | 424746 | 0 | 1.4271 | 29.1 | native finish (budget_cap) |
| A | gepa | 2 | val-40 | 600 | 0.425 | 0.800 (c8) | 0.375 | 16/9/9 | False | 427579 | 0 | 1.3864 | 25.8 | native finish (budget_cap) |
| A | skillopt | 0 | val-40 | 526 | 0.625 | 0.775 (step_0004) | 0.150 | 8/4/3 | False | 3572673 | 0 | 8.1299 | 28.3 | native finish |
| A | skillopt | 1 | val-40 | 600 | 0.550 | 0.850 (step_0003) | 0.300 | 7/6/4 | False | 4778086 | 0 | 10.418 | 27.0 | native finish (budget_cap) |
| A | skillopt | 2 | val-40 | 566 | 0.525 | 0.800 (step_0005) | 0.275 | 8/5/6 | False | 5102141 | 0 | 11.1817 | 26.7 | native finish |
| A | metaharness | 0 | val-40 | 600 | 0.600 | 0.975 (example_calibration) | 0.375 | 8/8/3 | False | 161527 | 572668 | 0.6715 | 19.6 | native finish |
| A | metaharness | 1 | val-40 | 600 | 0.625 | 0.875 (typed_value_fidelity) | 0.250 | 8/8/4 | False | 175419 | 836229 | 0.7676 | 20.0 | native finish |
| A | metaharness | 2 | val-40 | 600 | 0.600 | 0.900 (example_reproduce) | 0.300 | 8/8/4 | False | 214291 | 905568 | 0.9386 | 22.4 | native finish |
| A | evoskill | 0 | val-40 | 332 | 0.550 | 0.800 (iter-skill-17) | 0.250 | 6/6/6 | False | 387197 | 497881 | 1.259 | 12.3 | native finish |
| A | evoskill | 1 | val-40 | 452 | 0.550 | 0.875 (iter-skill-14) | 0.325 | 9/9/7 | False | 785636 | 531669 | 2.331 | 18.4 | native finish |
| A | evoskill | 2 | val-40 | 452 | 0.550 | 0.850 (iter-skill-9) | 0.300 | 9/9/5 | False | 744375 | 574377 | 2.2246 | 17.1 | native finish |
| A | wikiskill | 0 | val-40 | 521 | 0.575 | 0.800 (it004) | 0.225 | 4/4/2 | False | 427282 | 351970 | 1.212 | 26.5 | crash |
| A | wikiskill | 1 | val-40 | 426 | 0.525 | 0.825 (it002) | 0.300 | 3/3/2 | False | 313073 | 315890 | 0.9641 | 27.8 | running |
| A | wikiskill | 2 | val-40 | 364 | 0.500 | 0.650 (it001) | 0.150 | 3/2/1 | False | 201538 | 137826 | 0.5978 | 27.8 | running |
| A | trace2skill | 0 | val-40 | 200 | 0.500 | 0.700 (error) | 0.200 | 2/2/1 | False | 2202310 | 0 | 6.8207 | 15.6 | native finish |
| A | trace2skill | 1 | val-40 | 200 | 0.525 | 0.800 (combined) | 0.275 | 2/2/1 | False | 2225291 | 0 | 6.958 | 14.2 | native finish |
| A | trace2skill | 2 | val-40 | 200 | 0.525 | 0.750 (combined) | 0.225 | 2/2/1 | False | 2085988 | 0 | 6.4927 | 16.1 | native finish |
| A | ace | 0 | val-40 | 390 | 0.800 | 0.800 (epoch1_end) | 0.000 | 1/1/0 | True | 3902518 | 0 | 9.5622 | 15.1 | native finish |
| A | ace | 1 | -- | 181 | -- | -- (--) | -- | 0/0/0 | None | 1772164 | 0 | 4.5882 | 15.8 | running |
| A | ace | 2 | -- | 149 | -- | -- (--) | -- | 0/0/0 | None | 1346489 | 0 | 3.5812 | 15.8 | running |
| A | mipro | 0 | val-40 | 221 | 0.575 | 0.575 (3d5fee3dfdc1) | 0.000 | 9/0/0 | True | 178651 | 0 | 0.5792 | 27.8 | running |
| A | mipro | 1 | val-40 | 273 | 0.550 | 0.850 (cc2319ac81ff) | 0.300 | 14/1/0 | False | 181449 | 0 | 0.6009 | 27.8 | running |
| A | mipro | 2 | val-40 | 221 | 0.600 | 0.650 (779ef0083958) | 0.050 | 9/1/0 | False | 178826 | 0 | 0.5906 | 27.8 | running |
| B | hc | 0 | opt-49 | 490 | 0.531 | 0.531 (seed) | 0.000 | 2/2/0 | True | 348306 | 4071946 | 2.0054 | 28.2 | running |
| B | hc | 1 | opt-49 | 564 | 0.653 | 0.653 (seed) | 0.000 | 10/10/0 | True | 705711 | 6452540 | 3.5336 | 27.3 | native finish (budget) |
| B | hc | 2 | opt-49 | 490 | 0.542 | 0.542 (seed) | 0.000 | 2/2/0 | True | 248637 | 3016017 | 1.4563 | 28.2 | running |
| B | ao | 0 | opt-49 | 198 | 0.604 | 0.604 (seed) | 0.000 | 2/0/0 | True | 1018932 | 9478573 | 4.9191 | 11.6 | native finish |
| B | ao | 1 | opt-49 | 197 | 0.612 | 0.612 (seed) | 0.000 | 1/0/0 | True | 842779 | 10229243 | 4.701 | 20.9 | native finish |
| B | ao | 2 | opt-49 | 172 | 0.612 | 0.612 (seed) | 0.000 | 0/0/0 | True | 1499933 | 16113691 | 7.7435 | 28.2 | running |
| B | gepa | 0 | sel-25 | 338 | 0.600 | 0.720 (cand_0004) | 0.120 | 22/6/6 | False | 574391 | 0 | 2.0694 | 28.1 | running |
| B | gepa | 1 | sel-25 | 389 | 0.400 | 0.760 (cand_0018) | 0.360 | 21/9/9 | False | 531528 | 0 | 1.9177 | 28.2 | running |
| B | gepa | 2 | sel-25 | 344 | 0.600 | 0.720 (cand_0015) | 0.120 | 24/6/6 | False | 566612 | 0 | 1.9288 | 28.2 | running |
| B | harnesslens | 0 | -- | 123 | -- | -- (--) | -- | 0/0/0 | None | 5701991 | 1246006 | 15.665 | 18.5 | running |
| B | harnesslens | 1 | -- | 173 | -- | -- (--) | -- | 0/0/0 | None | 4879714 | 1964929 | 14.643 | 17.5 | stopped (unclassified) |
| B | harnesslens | 2 | -- | 163 | -- | -- (--) | -- | 0/0/0 | None | 6796933 | 1697346 | 18.4037 | 18.5 | running |
| B | oneshot | 0 | opt-49 | 123 | 0.562 | 0.562 (seed) | 0.000 | 1/1/0 | True | 174123 | 2014245 | 0.9993 | 5.1 | native finish (iterations) |
| B | oneshot | 1 | opt-49 | 148 | 0.571 | 0.714 (cand_0001) | 0.143 | 1/1/1 | False | 199013 | 3352636 | 1.3734 | 4.9 | native finish (iterations) |
| B | oneshot | 2 | opt-49 | 123 | 0.653 | 0.653 (seed) | 0.000 | 1/1/0 | True | 141128 | 1531722 | 0.7744 | 4.4 | native finish (iterations) |
| B | seed | 0 | opt/sel | 98 | opt 0.561 / sel 0.600 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.5 | native finish |
| B | seed | 1 | opt/sel | 98 | opt 0.602 / sel 0.580 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.5 | native finish |
| B | seed | 2 | opt/sel | 98 | opt 0.653 / sel 0.620 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.8 | native finish |
| C | hc | 0 | opt-20 | 320 | 0.450 | 0.600 (cand_0003) | 0.150 | 4/4/1 | False | 450271 | 4362982 | 2.3814 | 22.4 | running |
| C | hc | 1 | opt-20 | 240 | 0.450 | 0.450 (seed) | 0.000 | 5/5/0 | True | 385098 | 3352275 | 1.9114 | 22.5 | running |
| C | hc | 2 | opt-20 | 320 | 0.550 | 0.684 (cand_0005) | 0.134 | 9/9/1 | False | 657664 | 5425411 | 3.1332 | 22.5 | running |
| C | ao | 0 | opt-20 | 110 | 0.550 | 0.550 (seed) | 0.000 | 0/0/0 | True | 554012 | 5514194 | 2.7512 | 11.3 | native finish |
| C | ao | 1 | opt-20 | 110 | 0.550 | 0.550 (seed) | 0.000 | 0/0/0 | True | 564650 | 4051700 | 2.4403 | 7.7 | native finish |
| C | ao | 2 | opt-20 | 71 | 0.450 | 0.450 (seed) | 0.000 | 1/0/0 | True | 523420 | 2466110 | 1.975 | 9.8 | native finish |
| C | gepa | 0 | sel-10 | 207 | 0.800 | 1.000 (cand_0005) | 0.200 | 18/8/8 | False | 430906 | 0 | 1.7689 | 22.5 | running |
| C | gepa | 1 | sel-10 | 166 | 0.800 | 1.000 (cand_0013) | 0.200 | 15/6/6 | False | 399633 | 0 | 1.5829 | 22.5 | running |
| C | gepa | 2 | sel-10 | 203 | 0.900 | 1.000 (cand_0001) | 0.100 | 21/6/6 | False | 508386 | 0 | 1.8486 | 22.4 | running |
| C | oneshot | 0 | opt-20 | 60 | 0.500 | 0.737 (cand_0001) | 0.237 | 1/1/1 | False | 93027 | 1279390 | 0.5998 | 5.7 | native finish (iterations) |
| C | oneshot | 1 | opt-20 | 50 | 0.550 | 0.550 (seed) | 0.000 | 1/1/0 | True | 107372 | 1500867 | 0.7143 | 3.2 | native finish (iterations) |
| C | oneshot | 2 | opt-20 | 50 | 0.526 | 0.526 (seed) | 0.000 | 1/1/0 | True | 125833 | 1796170 | 0.8116 | 3.0 | native finish (iterations) |
| C | seed | 0 | opt/sel | 42 | opt 0.525 / sel 0.850 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.3 | native finish |
| C | seed | 1 | opt/sel | 40 | opt 0.550 / sel 0.850 | -- (--) | -- | 0/0/0 | None | None | None | None | 4.0 | native finish |
| C | seed | 2 | opt/sel | 42 | opt 0.575 / sel 0.750 | -- (--) | -- | 0/0/0 | None | None | None | None | 5.3 | native finish |
| A-E12 | hcstock | 0 | val-40 | 600 | 0.564 | 0.850 (cand_0007) | 0.286 | 12/12/2 | False | 496280 | 2086252 | 1.8706 | 17.0 | native finish (budget) |
| A-E12 | hcstock | 1 | val-40 | 600 | 0.526 | 0.875 (cand_0002) | 0.349 | 12/12/2 | False | 533805 | 2800926 | 2.1633 | 15.3 | native finish (budget) |
| A-E12 | hcstock | 2 | val-40 | 600 | 0.553 | 0.875 (cand_0004) | 0.322 | 12/12/3 | False | 520455 | 2128142 | 1.9638 | 15.4 | native finish (budget) |
| C-E12 | hcstock | 0 | opt-20 | 220 | 0.500 | 0.737 (cand_0001) | 0.237 | 10/10/1 | False | 663977 | 5433411 | 3.1357 | 19.8 | running |
| C-E12 | hcstock | 1 | opt-20 | 230 | 0.650 | 0.650 (seed) | 0.000 | 10/10/0 | True | 734093 | 7538800 | 3.9176 | 16.8 | native finish (iterations) |
| C-E12 | hcstock | 2 | opt-20 | 240 | 0.474 | 0.789 (cand_0002) | 0.316 | 10/10/2 | False | 749017 | 6133673 | 3.58 | 18.0 | native finish (iterations) |
| C-E12 | bestofk | 0 | opt-20 | 140 | 0.500 | 0.800 (prop_02) | 0.300 | 9/6/0 | False | 1327579 | 18298241 | 8.7779 | 13.6 | paused (truncated at k=6, 140 rollouts) |
| C-E12 | bestofk | 1 | opt-20 | 140 | 0.650 | 0.750 (prop_03) | 0.100 | 9/6/0 | False | 1150457 | 15406071 | 7.532 | 10.3 | paused (truncated at k=6, 140 rollouts) |
| C-E12 | bestofk | 2 | opt-20 | 180 | 0.474 | 0.800 (prop_01) | 0.326 | 10/8/0 | False | 1172177 | 16774685 | 7.7866 | 10.3 | paused (truncated at k=8, 180 rollouts) |
| D | E20-CTL | 0 | opt-49 | 148 | 0.592 | 0.723 (cand_0001) | 0.132 | 1/1/1 | False | 109955 | 1494578 | 0.6797 | 2.2 | native finish (iterations) |
| D | E20-CTL | 1 | opt-49 | 148 | 0.571 | 0.673 (cand_0001) | 0.102 | 1/1/1 | False | 102028 | 1334969 | 0.6451 | 2.7 | native finish (iterations) |
| D | E20-CTL | 2 | opt-49 | 123 | 0.667 | 0.667 (seed) | 0.000 | 1/1/0 | True | 113406 | 1365781 | 0.694 | 2.0 | native finish (iterations) |
| D | E20-GEPA | 0 | sel-25 | 402 | 0.640 | 0.640 (cand_0000) | 0.000 | 18/10/10 | True | 432859 | 0 | 1.7672 | 6.4 | running |
| D | E20-GEPA | 1 | sel-25 | 394 | 0.560 | 0.800 (cand_0019) | 0.240 | 21/10/10 | False | 487081 | 0 | 1.7579 | 6.4 | running |
| D | E20-GEPA | 2 | sel-25 | 393 | 0.560 | 0.680 (cand_0020) | 0.120 | 23/9/9 | False | 463333 | 0 | 1.5769 | 6.4 | running |
| D | E20-P | 0 | opt-49 | 589 | 0.531 | 0.833 (cand_0004) | 0.303 | 10/10/3 | False | 527503 | 4138699 | 2.5194 | 7.0 | running |
| D | E20-P | 1 | opt-49 | 589 | 0.562 | 0.688 (cand_0002) | 0.125 | 10/10/1 | False | 477875 | 3223475 | 2.1783 | 7.4 | running |
| D | E20-P | 2 | opt-49 | 589 | 0.625 | 0.755 (cand_0005) | 0.130 | 10/10/1 | False | 499819 | 3333588 | 2.271 | 7.0 | running |
| D | E20-PT | 0 | opt-49 | 589 | 0.531 | 0.750 (cand_0005) | 0.219 | 10/10/2 | False | 652749 | 7420284 | 3.6884 | 7.4 | running |
| D | E20-PT | 1 | opt-49 | 392 | 0.571 | 0.792 (cand_0002) | 0.220 | 8/8/1 | False | 498344 | 6099741 | 2.9204 | 7.4 | running |
| D | E20-PT | 2 | opt-49 | 490 | 0.510 | 0.714 (cand_0003) | 0.204 | 9/9/2 | False | 664739 | 5748023 | 3.2565 | 7.4 | running |
| D | E20-T | 0 | opt-49 | 392 | 0.551 | 0.551 (seed) | 0.000 | 7/7/0 | True | 558013 | 7292129 | 3.397 | 7.4 | running |
| D | E20-T | 1 | opt-49 | 441 | 0.571 | 0.688 (cand_0003) | 0.116 | 9/9/1 | False | 487812 | 5316658 | 2.7116 | 7.4 | running |
| D | E20-T | 2 | opt-49 | 564 | 0.612 | 0.612 (seed) | 0.000 | 10/10/0 | True | 471256 | 5008749 | 2.5453 | 7.3 | running |
| D-E21 | E21-1S | 0 | opt-49 | 441 | 0.521 | 0.787 (cand_0009) | 0.266 | 9/9/2 | False | 499903 | 4169331 | 2.4722 | 6.4 | running |
| D-E21 | E21-1S | 1 | opt-49 | 441 | 0.633 | 0.816 (cand_0005) | 0.184 | 9/9/2 | False | 585464 | 7905219 | 3.638 | 6.4 | running |
| D-E21 | E21-1S | 2 | opt-49 | 392 | 0.500 | 0.694 (cand_0001) | 0.194 | 7/7/1 | False | 435285 | 4735085 | 2.437 | 6.4 | running |
| D-E21 | E21-ruleP | 0 | opt-49 | 637 | 0.612 | 0.714 (cand_0006) | 0.102 | 6/6/1 | False | 378120 | 4161126 | 2.0723 | 7.4 | running |
| D-E21 | E21-ruleP | 1 | opt-49 | 441 | 0.551 | 0.551 (seed) | 0.000 | 1/1/0 | True | 194749 | 3100617 | 1.3397 | 7.4 | running |
| D-E21 | E21-ruleP | 2 | opt-49 | 441 | 0.479 | 0.673 (cand_0001) | 0.194 | 1/1/1 | False | 157107 | 2249214 | 1.0133 | 7.4 | running |
| D-E26 | E26-NOHIST | 0 | opt-49 | 589 | 0.592 | 0.796 (cand_0009) | 0.204 | 10/10/2 | False | None | None | 4.912208399999999 | 4.6 | native finish (budget) |
| D-E26 | E26-NOHIST | 1 | opt-49 | 539 | 0.633 | 0.771 (cand_0006) | 0.138 | 10/10/1 | False | None | None | 4.5320538 | 5.0 | running |
| D-E26 | E26-NOHIST | 2 | opt-49 | 441 | 0.531 | 0.761 (cand_0007) | 0.230 | 8/8/2 | False | None | None | 3.9749757 | 4.6 | running |

Notes: champion = what the method itself would return (CapEvolve: state best_id/best_val; GEPA, MIPRO, others: last selected or argmax of full selection-split evaluations). ACE and HarnessLens have no candidate/selection step yet. Optimizer USD covers priced (Claude) calls only; unpriced tokens are in runs.csv.

## Gate behaviour (CapEvolve)

| suite | arm | seed | cands | screens | confirms | promoted | rejected | vetoed | indecisive (reasons) | lost cands | lost attempts | cap-truncated |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | hc | 0 | 4 | 3 | 2 | 1 | 1 | 1 | 1 coverage<0.95 (90%) x1 | 1 | 1 | 0 |
| A | hc | 1 | 2 | 1 | 1 | 1 | 0 | 0 | 0  | 0 | 0 | 1 |
| A | hc | 2 | 12 | 10 | 0 | 0 | 0 | 10 | 10 coverage<0.95 (92%) x10 | 2 | 3 | 0 |
| A | ao | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0  | 0 | 0 | 0 |
| A | ao | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0  | 0 | 0 | 0 |
| A | ao | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0  | 0 | 0 | 0 |
| B | hc | 0 | 2 | 2 | 1 | 0 | 2 | 0 | 0  | 0 | 0 | 0 |
| B | hc | 1 | 10 | 10 | 0 | 0 | 10 | 0 | 0  | 0 | 0 | 0 |
| B | hc | 2 | 2 | 2 | 1 | 0 | 2 | 0 | 0  | 0 | 0 | 0 |
| B | ao | 0 | 2 | 0 | 0 | 0 | 2 | 0 | 0  | 0 | 0 | 0 |
| B | ao | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0  | 0 | 0 | 0 |
| B | ao | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0  | 0 | 0 | 0 |
| C | hc | 0 | 4 | 4 | 2 | 1 | 3 | 0 | 0  | 0 | 0 | 0 |
| C | hc | 1 | 5 | 5 | 1 | 0 | 4 | 1 | 2 coverage<0.95 (90%) x2 | 0 | 0 | 0 |
| C | hc | 2 | 9 | 9 | 1 | 1 | 8 | 0 | 0  | 0 | 0 | 0 |
| C | ao | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0  | 0 | 0 | 0 |
| C | ao | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0  | 0 | 0 | 0 |
| C | ao | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 0  | 0 | 0 | 0 |
| A-E12 | hcstock | 0 | 12 | 12 | 0 | 2 | 10 | 0 | 0  | 0 | 0 | 0 |
| A-E12 | hcstock | 1 | 12 | 12 | 0 | 2 | 10 | 0 | 0  | 0 | 0 | 0 |
| A-E12 | hcstock | 2 | 12 | 12 | 0 | 3 | 9 | 0 | 0  | 0 | 0 | 0 |
| C-E12 | hcstock | 0 | 10 | 10 | 0 | 1 | 9 | 0 | 0  | 0 | 0 | 0 |
| C-E12 | hcstock | 1 | 10 | 10 | 0 | 0 | 10 | 0 | 0  | 0 | 0 | 0 |
| C-E12 | hcstock | 2 | 10 | 10 | 0 | 2 | 8 | 0 | 0  | 0 | 0 | 0 |
| D | E20-CTL | 0 | 1 | 1 | 0 | 1 | 0 | 0 | 0  | 0 | 0 | 0 |
| D | E20-CTL | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0  | 0 | 0 | 0 |
| D | E20-CTL | 2 | 1 | 1 | 0 | 0 | 1 | 0 | 0  | 0 | 0 | 0 |
| D | E20-P | 0 | 10 | 10 | 0 | 3 | 7 | 0 | 0  | 0 | 0 | 0 |
| D | E20-P | 1 | 10 | 10 | 0 | 1 | 9 | 0 | 0  | 0 | 0 | 0 |
| D | E20-P | 2 | 10 | 10 | 0 | 1 | 9 | 0 | 0  | 0 | 0 | 0 |
| D | E20-PT | 0 | 10 | 10 | 0 | 2 | 8 | 0 | 0  | 0 | 0 | 0 |
| D | E20-PT | 1 | 8 | 8 | 0 | 1 | 7 | 0 | 0  | 0 | 0 | 0 |
| D | E20-PT | 2 | 9 | 9 | 0 | 2 | 7 | 0 | 0  | 0 | 0 | 0 |
| D | E20-T | 0 | 7 | 7 | 0 | 0 | 7 | 0 | 0  | 0 | 0 | 0 |
| D | E20-T | 1 | 9 | 9 | 0 | 1 | 8 | 0 | 0  | 0 | 0 | 0 |
| D | E20-T | 2 | 10 | 10 | 0 | 0 | 10 | 0 | 0  | 0 | 0 | 0 |
| D-E21 | E21-1S | 0 | 9 | 9 | 0 | 2 | 7 | 0 | 0  | 0 | 0 | 0 |
| D-E21 | E21-1S | 1 | 9 | 9 | 0 | 2 | 7 | 0 | 0  | 0 | 0 | 0 |
| D-E21 | E21-1S | 2 | 7 | 7 | 0 | 1 | 6 | 0 | 6 coverage<0.95 (88%) x3; coverage<0.95 (90%) x1; coverage<0.95 (86%) x2 | 0 | 0 | 0 |
| D-E21 | E21-ruleP | 0 | 6 | 6 | 1 | 1 | 5 | 0 | 0  | 0 | 0 | 0 |
| D-E21 | E21-ruleP | 1 | 1 | 1 | 1 | 0 | 1 | 0 | 0  | 0 | 0 | 0 |
| D-E21 | E21-ruleP | 2 | 1 | 1 | 1 | 1 | 0 | 0 | 0  | 0 | 0 | 0 |
| D-E26 | E26-NOHIST | 0 | 10 | 10 | 0 | 2 | 8 | 0 | 0  | 0 | 0 | 0 |
| D-E26 | E26-NOHIST | 1 | 10 | 10 | 0 | 1 | 9 | 0 | 0  | 0 | 0 | 0 |
| D-E26 | E26-NOHIST | 2 | 8 | 8 | 0 | 2 | 6 | 0 | 0  | 0 | 0 | 0 |

## Edits by capability surface (candidates touching surface / changed lines)

| suite | arm | cands | system_prompt | task_template | tool_code | mcp | skill_files | process_docs | reference | other |
|---|---|---|---|---|---|---|---|---|---|---|
| A | ao | 3 | 3 / 38 | 3 / 10 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | evoskill | 24 | 18 / 1499 | 0 / 0 | 0 / 0 | 0 / 0 | 18 / 1391 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | gepa | 48 | 43 / 3317 | 38 / 3205 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | hc | 15 | 15 / 276 | 15 / 32 | 0 / 0 | 0 / 0 | 0 / 0 | 14 / 5259 | 0 / 0 | 0 / 0 |
| A | metaharness | 24 | 24 / 394 | 24 / 197 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | mipro | 32 | 32 / 3856 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | skillopt | 23 | 23 / 253 | 23 / 959 | 0 / 0 | 0 / 0 | 23 / 1212 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | trace2skill | 6 | 6 / 224 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | wikiskill | 10 | 10 / 506 | 0 / 0 | 0 / 0 | 0 / 0 | 10 / 456 | 0 / 0 | 0 / 0 | 0 / 0 |
| A-E12 | hcstock | 36 | 36 / 829 | 36 / 165 | 0 / 0 | 0 / 0 | 0 / 0 | 36 / 13163 | 0 / 0 | 0 / 0 |
| B | ao | 3 | 3 / 35 | 0 / 0 | 3 / 306 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| B | gepa | 67 | 67 / 5806 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| B | hc | 14 | 9 / 110 | 0 / 0 | 14 / 607 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| B | oneshot | 3 | 3 / 53 | 0 / 0 | 3 / 217 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | ao | 1 | 1 / 13 | 0 / 0 | 1 / 151 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | gepa | 54 | 54 / 4858 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | hc | 18 | 18 / 206 | 0 / 0 | 18 / 2010 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | oneshot | 3 | 3 / 40 | 0 / 0 | 3 / 489 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C-E12 | bestofk | 19 | 19 / 540 | 0 / 0 | 19 / 4687 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C-E12 | hcstock | 30 | 29 / 407 | 0 / 0 | 30 / 3865 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| D | E20-CTL | 3 | 3 / 93 | 0 / 0 | 3 / 242 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| D | E20-GEPA | 62 | 62 / 5538 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| D | E20-P | 30 | 30 / 1213 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| D | E20-PT | 27 | 27 / 1002 | 0 / 0 | 27 / 2387 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| D | E20-T | 26 | 0 / 0 | 0 / 0 | 25 / 1328 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| D-E21 | E21-1S | 25 | 25 / 957 | 0 / 0 | 25 / 2457 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| D-E21 | E21-ruleP | 8 | 8 / 212 | 0 / 0 | 8 / 694 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| D-E26 | E26-NOHIST | 28 | 28 / 970 | 0 / 0 | 28 / 2156 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

## Infra and errors (uniform classifier, main + chaser rows)

| suite | arm | rollouts | errors | infra | candidate | unverifiable |
|---|---|---|---|---|---|---|
| A | gepa | 826 | 24 | 24 | 0 | 0 |
| A | skillopt | 1780 | 187 | 66 | 121 | 0 |
| A | metaharness | 1800 | 90 | 90 | 0 | 0 |
| A | evoskill | 1250 | 41 | 41 | 0 | 0 |
| A | wikiskill | 1181 | 80 | 80 | 0 | 0 |
| A | trace2skill | 602 | 51 | 49 | 2 | 0 |
| A | ace | 741 | 33 | 33 | 0 | 0 |
| A | mipro | 703 | 24 | 23 | 1 | 0 |
| A | hc | 2080 | 273 | 31 | 242 | 0 |
| A | ao | 480 | 13 | 13 | 0 | 0 |
| A-E12 | hcstock | 2360 | 15 | 15 | 0 | 0 |
| B | seed | 444 | 0 | 0 | 0 | 0 |
| B | oneshot | 394 | 8 | 8 | 0 | 0 |
| B | gepa | 1037 | 0 | 0 | 0 | 0 |
| B | hc | 1544 | 7 | 7 | 0 | 0 |
| B | ao | 517 | 3 | 3 | 0 | 0 |
| C | seed | 180 | 0 | 0 | 0 | 0 |
| C | oneshot | 160 | 3 | 3 | 0 | 0 |
| C | gepa | 567 | 1 | 0 | 0 | 1 |
| C | hc | 880 | 14 | 14 | 0 | 0 |
| C | ao | 291 | 2 | 2 | 0 | 0 |
| C-E12 | hcstock | 850 | 6 | 6 | 0 | 0 |
