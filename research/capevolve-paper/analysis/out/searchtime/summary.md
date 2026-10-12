# Search-time results (latest run state)

Data: run artifacts under campaign-scratch/runs and analysis/out/metrics, newest gateway call 2026-10-12T08:42:20Z. Regenerate with `analysis/scripts/searchtime_results.py`.

**Caveat.** Every number here is search-time, on the search/selection split of its own method, not held-out. Selection-split scores are optimistic and not comparable across methods: GEPA selects the best candidate on its selection split, Meta-Harness's proposer saw val aggregates, CapEvolve screens on its own split, and Suites B and C use different split sizes per method. No cross-method ranking may be drawn from these numbers. Final results exist only after the 2026-10-13 06:00 UTC cutoff.

## Per arm and seed

| suite | arm | seed | split | rollouts | seed score | champion (id) | gain | gen/scr/prom | returned=seed | opt tok (non-cache) | cache read | USD | wall h | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | hc | 0 | val-40 | 283 | 0.579 | 0.579 (seed) | 0.000 | 3/3/0 | True | 147446 | 566624 | 0.542 | 18.0 | running |
| A | hc | 1 | val-40 | 421 | 0.590 | 0.692 (cand_0001) | 0.103 | 2/3/1 | False | 87560 | 399706 | 0.3373 | 18.0 | running |
| A | hc | 2 | val-40 | 210 | 0.568 | 0.568 (seed) | 0.000 | 3/1/0 | True | 196569 | 972146 | 0.7915 | 18.0 | running |
| A | ao | 0 | val-20 | 221 | 0.462 | 0.462 (seed) | 0.000 | 1/1/0 | True | 2331369 | 1452974 | 6.2272 | 18.0 | running |
| A | ao | 1 | val-40 | 376 | 0.447 | 0.447 (seed) | 0.000 | 1/1/0 | True | 990763 | 1653780 | 2.9188 | 18.0 | running |
| A | ao | 2 | val-20 | 340 | 0.684 | 0.684 (seed) | 0.000 | 1/1/0 | True | 1602367 | 1707744 | 4.4682 | 18.0 | running |
| A | gepa | 0 | val-40 | 556 | 0.525 | 0.850 (c2) | 0.325 | 18/8/8 | False | 566562 | 0 | 1.9621 | 24.3 | running |
| A | gepa | 1 | val-40 | 417 | 0.525 | 0.875 (c5) | 0.350 | 6/6/6 | False | 184802 | 0 | 0.6199 | 24.3 | running |
| A | gepa | 2 | val-40 | 569 | 0.425 | 0.800 (c8) | 0.375 | 16/9/9 | False | 393221 | 0 | 1.2778 | 24.3 | running |
| A | skillopt | 0 | val-40 | 420 | 0.625 | 0.775 (step_0004) | 0.150 | 6/3/2 | False | 2577921 | 0 | 5.9954 | 24.3 | running |
| A | skillopt | 1 | val-40 | 523 | 0.550 | 0.850 (step_0003) | 0.300 | 6/5/4 | False | 3686520 | 0 | 8.1247 | 24.2 | running |
| A | skillopt | 2 | val-40 | 505 | 0.525 | 0.800 (step_0005) | 0.275 | 6/4/5 | False | 4674105 | 0 | 10.2766 | 24.3 | running |
| A | metaharness | 0 | val-40 | 600 | 0.600 | 0.975 (example_calibration) | 0.375 | 8/8/3 | False | 161527 | 572668 | 0.6715 | 19.6 | native finish |
| A | metaharness | 1 | val-40 | 600 | 0.625 | 0.875 (typed_value_fidelity) | 0.250 | 8/8/4 | False | 175419 | 836229 | 0.7676 | 20.0 | native finish |
| A | metaharness | 2 | val-40 | 588 | 0.600 | 0.850 (values_first) | 0.250 | 8/7/3 | False | 214291 | 905568 | 0.9386 | 21.7 | running |
| A | evoskill | 0 | val-40 | 332 | 0.550 | 0.800 (iter-skill-17) | 0.250 | 6/6/6 | False | 387197 | 497881 | 1.259 | 12.3 | native finish |
| A | evoskill | 1 | val-40 | 331 | 0.550 | 0.875 (iter-skill-10) | 0.325 | 6/6/6 | False | 584636 | 400985 | 1.7335 | 14.2 | running |
| A | evoskill | 2 | val-40 | 327 | 0.550 | 0.850 (iter-skill-9) | 0.300 | 6/6/5 | False | 569326 | 399024 | 1.7018 | 14.2 | running |
| A | wikiskill | 0 | val-40 | 227 | 0.575 | 0.625 (S0) | 0.050 | 1/1/0 | True | 106541 | 92902 | 0.3033 | 19.6 | running |
| A | wikiskill | 1 | val-40 | 243 | 0.525 | 0.725 (it001) | 0.200 | 1/1/1 | False | 100612 | 77412 | 0.2987 | 19.6 | running |
| A | wikiskill | 2 | val-40 | 216 | 0.500 | 0.650 (it001) | 0.150 | 1/1/1 | False | 85738 | 41108 | 0.2476 | 19.6 | running |
| A | trace2skill | 0 | val-40 | 200 | 0.500 | 0.700 (error) | 0.200 | 2/2/1 | False | 2202310 | 0 | 6.8207 | 15.6 | native finish |
| A | trace2skill | 1 | val-40 | 200 | 0.525 | 0.800 (combined) | 0.275 | 2/2/1 | False | 2225291 | 0 | 6.958 | 14.2 | native finish |
| A | trace2skill | 2 | val-40 | 200 | 0.525 | 0.750 (combined) | 0.225 | 2/2/1 | False | 2085988 | 0 | 6.4927 | 16.1 | native finish |
| A | ace | 0 | -- | 137 | -- | -- (--) | -- | 0/0/0 | None | 1224344 | 0 | 3.2965 | 7.7 | running |
| A | ace | 1 | -- | 77 | -- | -- (--) | -- | 0/0/0 | None | 592944 | 0 | 1.6268 | 7.7 | running |
| A | ace | 2 | -- | 71 | -- | -- (--) | -- | 0/0/0 | None | 524738 | 0 | 1.4657 | 7.7 | running |
| A | mipro | 0 | val-40 | 134 | 0.575 | 0.575 (3d5fee3dfdc1) | 0.000 | 5/0/0 | True | 178651 | 0 | 0.5792 | 19.7 | running |
| A | mipro | 1 | val-40 | 150 | 0.550 | 0.550 (3d5fee3dfdc1) | 0.000 | 8/0/0 | True | 181449 | 0 | 0.6009 | 19.7 | running |
| A | mipro | 2 | val-40 | 138 | 0.600 | 0.600 (3d5fee3dfdc1) | 0.000 | 7/0/0 | True | 178826 | 0 | 0.5906 | 19.7 | running |
| B | hc | 0 | opt-49 | 294 | 0.531 | 0.531 (seed) | 0.000 | 1/1/0 | True | 277835 | 3423249 | 1.65 | 20.1 | running |
| B | hc | 1 | opt-49 | 392 | 0.653 | 0.653 (seed) | 0.000 | 7/7/0 | True | 622609 | 5926534 | 3.179 | 20.1 | running |
| B | hc | 2 | opt-49 | 392 | 0.542 | 0.542 (seed) | 0.000 | 1/1/0 | True | 205171 | 2490339 | 1.1977 | 20.1 | running |
| B | ao | 0 | opt-49 | 198 | 0.604 | 0.604 (seed) | 0.000 | 2/0/0 | True | 1018932 | 9478573 | 4.9191 | 11.6 | native finish |
| B | ao | 1 | opt-49 | 172 | 0.612 | 0.612 (seed) | 0.000 | 1/0/0 | True | 842779 | 10229243 | 4.701 | 20.1 | running |
| B | ao | 2 | opt-49 | 172 | 0.612 | 0.612 (seed) | 0.000 | 0/0/0 | True | 1039149 | 15545003 | 6.4566 | 17.6 | native finish |
| B | gepa | 0 | sel-25 | 256 | 0.600 | 0.720 (cand_0004) | 0.120 | 12/5/5 | False | 319243 | 0 | 1.1533 | 20.1 | running |
| B | gepa | 1 | sel-25 | 277 | 0.400 | 0.680 (cand_0014) | 0.280 | 14/6/6 | False | 362398 | 0 | 1.2867 | 20.1 | running |
| B | gepa | 2 | sel-25 | 271 | 0.600 | 0.720 (cand_0015) | 0.120 | 17/5/5 | False | 419022 | 0 | 1.4427 | 20.1 | running |
| B | harnesslens | 0 | -- | 108 | -- | -- (--) | -- | 0/0/0 | None | 1391293 | 318388 | 4.7549 | 9.3 | stopped (unclassified) |
| B | harnesslens | 1 | -- | 98 | -- | -- (--) | -- | 0/0/0 | None | None | None | None | 10.4 | running |
| B | harnesslens | 2 | -- | 105 | -- | -- (--) | -- | 0/0/0 | None | None | None | None | 7.8 | stopped (unclassified) |
| B | oneshot | 0 | opt-49 | 123 | 0.562 | 0.562 (seed) | 0.000 | 1/1/0 | True | 174123 | 2014245 | 0.9993 | 5.1 | native finish (iterations) |
| B | oneshot | 1 | opt-49 | 148 | 0.571 | 0.714 (cand_0001) | 0.143 | 1/1/1 | False | 199013 | 3352636 | 1.3734 | 4.9 | native finish (iterations) |
| B | oneshot | 2 | opt-49 | 123 | 0.653 | 0.653 (seed) | 0.000 | 1/1/0 | True | 141128 | 1531722 | 0.7744 | 4.4 | native finish (iterations) |
| B | seed | 0 | opt/sel | 98 | opt 0.561 / sel 0.600 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.5 | native finish |
| B | seed | 1 | opt/sel | 98 | opt 0.602 / sel 0.580 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.5 | native finish |
| B | seed | 2 | opt/sel | 98 | opt 0.653 / sel 0.620 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.8 | native finish |
| C | hc | 0 | opt-20 | 180 | 0.450 | 0.450 (seed) | 0.000 | 2/2/0 | True | 373678 | 3697567 | 2.0022 | 14.3 | running |
| C | hc | 1 | opt-20 | 100 | 0.450 | 0.450 (seed) | 0.000 | 3/3/0 | True | 285571 | 2990763 | 1.5649 | 14.3 | running |
| C | hc | 2 | opt-20 | 180 | 0.550 | 0.550 (seed) | 0.000 | 4/4/0 | True | 324428 | 3238356 | 1.6796 | 14.3 | running |
| C | ao | 0 | opt-20 | 110 | 0.550 | 0.550 (seed) | 0.000 | 0/0/0 | True | 554012 | 5514194 | 2.7512 | 11.3 | native finish |
| C | ao | 1 | opt-20 | 110 | 0.550 | 0.550 (seed) | 0.000 | 0/0/0 | True | 564650 | 4051700 | 2.4403 | 7.7 | native finish |
| C | ao | 2 | opt-20 | 71 | 0.450 | 0.450 (seed) | 0.000 | 1/0/0 | True | 523420 | 2466110 | 1.975 | 9.8 | native finish |
| C | gepa | 0 | sel-10 | 123 | 0.800 | 1.000 (cand_0005) | 0.200 | 9/5/5 | False | 221881 | 0 | 0.9032 | 14.4 | running |
| C | gepa | 1 | sel-10 | 98 | 0.800 | 0.900 (cand_0001) | 0.100 | 8/3/3 | False | 200590 | 0 | 0.8135 | 14.3 | running |
| C | gepa | 2 | sel-10 | 123 | 0.900 | 1.000 (cand_0001) | 0.100 | 10/4/4 | False | 238753 | 0 | 0.8702 | 14.3 | running |
| C | oneshot | 0 | opt-20 | 60 | 0.500 | 0.737 (cand_0001) | 0.237 | 1/1/1 | False | 93027 | 1279390 | 0.5998 | 5.7 | native finish (iterations) |
| C | oneshot | 1 | opt-20 | 50 | 0.550 | 0.550 (seed) | 0.000 | 1/1/0 | True | 107372 | 1500867 | 0.7143 | 3.2 | native finish (iterations) |
| C | oneshot | 2 | opt-20 | 50 | 0.526 | 0.526 (seed) | 0.000 | 1/1/0 | True | 125833 | 1796170 | 0.8116 | 3.0 | native finish (iterations) |
| C | seed | 0 | opt/sel | 42 | opt 0.525 / sel 0.850 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.3 | native finish |
| C | seed | 1 | opt/sel | 40 | opt 0.550 / sel 0.850 | -- (--) | -- | 0/0/0 | None | None | None | None | 4.0 | native finish |
| C | seed | 2 | opt/sel | 42 | opt 0.575 / sel 0.750 | -- (--) | -- | 0/0/0 | None | None | None | None | 5.3 | native finish |
| A-E12 | hcstock | 0 | val-40 | 314 | 0.564 | 0.775 (cand_0001) | 0.211 | 5/4/1 | False | 208379 | 1036501 | 0.8381 | 11.3 | running |
| A-E12 | hcstock | 1 | val-40 | 376 | 0.526 | 0.875 (cand_0002) | 0.349 | 7/6/2 | False | 320455 | 1785301 | 1.3311 | 11.3 | running |
| A-E12 | hcstock | 2 | val-40 | 364 | 0.553 | 0.875 (cand_0004) | 0.322 | 7/6/3 | False | 335193 | 1636109 | 1.3521 | 11.3 | running |
| C-E12 | hcstock | 0 | opt-20 | 100 | 0.500 | 0.737 (cand_0001) | 0.237 | 4/4/1 | False | 442160 | 4420851 | 2.2989 | 11.7 | running |
| C-E12 | hcstock | 1 | opt-20 | 140 | 0.650 | 0.650 (seed) | 0.000 | 6/6/0 | True | 575710 | 6810621 | 3.3041 | 11.7 | running |
| C-E12 | hcstock | 2 | opt-20 | 140 | 0.474 | 0.789 (cand_0002) | 0.316 | 6/6/2 | False | 530720 | 5249629 | 2.7678 | 11.7 | running |
| C-E12 | bestofk | 0 | opt-20 | 120 | 0.500 | 0.800 (prop_02) | 0.300 | 5/5/0 | False | 1028578 | 14103294 | 6.7635 | 11.2 | running |
| C-E12 | bestofk | 1 | opt-20 | 100 | 0.650 | 0.750 (prop_03) | 0.100 | 4/4/0 | False | 916623 | 12276795 | 6.0314 | 7.9 | running |
| C-E12 | bestofk | 2 | opt-20 | 140 | 0.474 | 0.800 (prop_01) | 0.326 | 6/6/0 | False | 1051091 | 15304257 | 7.0602 | 7.9 | running |

Notes: champion = what the method itself would return (CapEvolve: state best_id/best_val; GEPA, MIPRO, others: last selected or argmax of full selection-split evaluations). ACE and HarnessLens have no candidate/selection step yet. Optimizer USD covers priced (Claude) calls only; unpriced tokens are in runs.csv.

## Gate behaviour (CapEvolve)

| suite | arm | seed | cands | screens | confirms | promoted | rejected | vetoed | indecisive (reasons) |
|---|---|---|---|---|---|---|---|---|---|
| A | hc | 0 | 3 | 2 | 0 | 0 | 1 | 1 | 2 coverage<0.95 (90%) x2 |
| A | hc | 1 | 2 | 1 | 1 | 1 | 0 | 0 | 0  |
| A | hc | 2 | 3 | 1 | 0 | 0 | 2 | 1 | 3 coverage<0.95 (92%) x1; indecisive (evaluation error): candidate evaluation raised:  x2 |
| A | ao | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0  |
| A | ao | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0  |
| A | ao | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0  |
| B | hc | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0  |
| B | hc | 1 | 7 | 7 | 0 | 0 | 7 | 0 | 0  |
| B | hc | 2 | 1 | 1 | 1 | 0 | 1 | 0 | 0  |
| B | ao | 0 | 2 | 0 | 0 | 0 | 2 | 0 | 0  |
| B | ao | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0  |
| B | ao | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0  |
| C | hc | 0 | 2 | 2 | 1 | 0 | 2 | 0 | 0  |
| C | hc | 1 | 3 | 3 | 0 | 0 | 3 | 0 | 1 coverage<0.95 (90%) x1 |
| C | hc | 2 | 4 | 4 | 0 | 0 | 4 | 0 | 0  |
| C | ao | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0  |
| C | ao | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0  |
| C | ao | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 0  |
| A-E12 | hcstock | 0 | 5 | 4 | 0 | 1 | 3 | 0 | 0  |
| A-E12 | hcstock | 1 | 7 | 6 | 0 | 2 | 4 | 0 | 0  |
| A-E12 | hcstock | 2 | 7 | 6 | 0 | 3 | 3 | 0 | 0  |
| C-E12 | hcstock | 0 | 4 | 4 | 0 | 1 | 3 | 0 | 0  |
| C-E12 | hcstock | 1 | 6 | 6 | 0 | 0 | 6 | 0 | 0  |
| C-E12 | hcstock | 2 | 6 | 6 | 0 | 2 | 4 | 0 | 0  |

## Edits by capability surface (candidates touching surface / changed lines)

| suite | arm | cands | system_prompt | task_template | tool_code | mcp | skill_files | process_docs | reference | other |
|---|---|---|---|---|---|---|---|---|---|---|
| A | ao | 3 | 3 / 38 | 3 / 10 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | evoskill | 18 | 17 / 1391 | 0 / 0 | 0 / 0 | 0 / 0 | 17 / 1289 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | gepa | 40 | 35 / 2469 | 30 / 2503 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | hc | 8 | 8 / 102 | 8 / 18 | 0 / 0 | 0 / 0 | 0 / 0 | 5 / 1877 | 0 / 0 | 0 / 0 |
| A | metaharness | 24 | 24 / 394 | 24 / 197 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | mipro | 20 | 20 / 2632 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | skillopt | 18 | 18 / 190 | 18 / 682 | 0 / 0 | 0 / 0 | 18 / 872 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | trace2skill | 6 | 6 / 224 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | wikiskill | 3 | 3 / 150 | 0 / 0 | 0 / 0 | 0 / 0 | 3 / 135 | 0 / 0 | 0 / 0 | 0 / 0 |
| A-E12 | hcstock | 19 | 19 / 433 | 19 / 84 | 0 / 0 | 0 / 0 | 0 / 0 | 16 / 5873 | 0 / 0 | 0 / 0 |
| B | ao | 3 | 3 / 35 | 0 / 0 | 3 / 306 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| B | gepa | 43 | 43 / 3504 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| B | hc | 9 | 7 / 82 | 0 / 0 | 9 / 471 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| B | oneshot | 3 | 3 / 53 | 0 / 0 | 3 / 217 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | ao | 1 | 1 / 13 | 0 / 0 | 1 / 151 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | gepa | 27 | 27 / 2126 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | hc | 9 | 9 / 101 | 0 / 0 | 9 / 947 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | oneshot | 3 | 3 / 40 | 0 / 0 | 3 / 489 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C-E12 | bestofk | 15 | 15 / 408 | 0 / 0 | 15 / 3494 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C-E12 | hcstock | 16 | 16 / 239 | 0 / 0 | 16 / 2339 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

## Infra and errors (uniform classifier, main + chaser rows)

| suite | arm | rollouts | errors | infra | candidate | unverifiable |
|---|---|---|---|---|---|---|
| A | gepa | 553 | 18 | 18 | 0 | 0 |
| A | skillopt | 1480 | 185 | 64 | 121 | 0 |
| A | metaharness | 1740 | 86 | 86 | 0 | 0 |
| A | evoskill | 992 | 37 | 37 | 0 | 0 |
| A | wikiskill | 519 | 49 | 49 | 0 | 0 |
| A | trace2skill | 602 | 51 | 49 | 2 | 0 |
| A | ace | 300 | 22 | 22 | 0 | 0 |
| A | mipro | 413 | 19 | 18 | 1 | 0 |
| A | hc | 560 | 30 | 30 | 0 | 0 |
| A | ao | 480 | 23 | 23 | 0 | 0 |
| A-E12 | hcstock | 1040 | 15 | 15 | 0 | 0 |
| B | seed | 444 | 0 | 0 | 0 | 0 |
| B | oneshot | 394 | 8 | 8 | 0 | 0 |
| B | gepa | 793 | 0 | 0 | 0 | 0 |
| B | hc | 1078 | 7 | 7 | 0 | 0 |
| B | ao | 517 | 3 | 3 | 0 | 0 |
| C | seed | 180 | 0 | 0 | 0 | 0 |
| C | oneshot | 160 | 3 | 3 | 0 | 0 |
| C | gepa | 328 | 1 | 0 | 0 | 1 |
| C | hc | 419 | 5 | 5 | 0 | 0 |
| C | ao | 291 | 2 | 2 | 0 | 0 |
| C-E12 | hcstock | 440 | 6 | 6 | 0 | 0 |
