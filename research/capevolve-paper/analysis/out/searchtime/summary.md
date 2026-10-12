# Search-time results (latest run state)

Data: run artifacts under campaign-scratch/runs and analysis/out/metrics, newest gateway call 2026-10-12T09:42:47Z. Regenerate with `analysis/scripts/searchtime_results.py`.

**Caveat.** Every number here is search-time, on the search/selection split of its own method, not held-out. Selection-split scores are optimistic and not comparable across methods: GEPA selects the best candidate on its selection split, Meta-Harness's proposer saw val aggregates, CapEvolve screens on its own split, and Suites B and C use different split sizes per method. No cross-method ranking may be drawn from these numbers. Final results exist only after the 2026-10-13 06:00 UTC cutoff.

## Per arm and seed

| suite | arm | seed | split | rollouts | seed score | champion (id) | gain | gen/scr/prom | returned=seed | opt tok (non-cache) | cache read | USD | wall h | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | hc | 0 | val-40 | 302 | 0.579 | 0.579 (seed) | 0.000 | 3/2/0 | True | 147446 | 566624 | 0.542 | 19.0 | running |
| A | hc | 1 | val-40 | 479 | 0.590 | 0.692 (cand_0001) | 0.103 | 2/4/1 | False | 87560 | 399706 | 0.3373 | 19.0 | running |
| A | hc | 2 | val-40 | 240 | 0.568 | 0.568 (seed) | 0.000 | 3/1/0 | True | 196569 | 972146 | 0.7915 | 19.0 | running |
| A | ao | 0 | val-20 | 232 | 0.462 | 0.462 (seed) | 0.000 | 1/1/0 | True | 2836713 | 1469691 | 7.5029 | 19.0 | running |
| A | ao | 1 | val-40 | 392 | 0.447 | 0.447 (seed) | 0.000 | 1/1/0 | True | 990763 | 1653780 | 2.9188 | 19.0 | running |
| A | ao | 2 | val-20 | 363 | 0.684 | 0.684 (seed) | 0.000 | 1/1/0 | True | 1602367 | 1707744 | 4.4682 | 19.0 | running |
| A | gepa | 0 | val-40 | 581 | 0.525 | 0.850 (c2) | 0.325 | 19/9/9 | False | 566562 | 0 | 1.9621 | 25.4 | running |
| A | gepa | 1 | val-40 | 438 | 0.525 | 0.875 (c5) | 0.350 | 8/7/7 | False | 257604 | 0 | 0.8807 | 25.4 | running |
| A | gepa | 2 | val-40 | 600 | 0.425 | 0.800 (c8) | 0.375 | 16/9/9 | False | 427579 | 0 | 1.3864 | 25.3 | running |
| A | skillopt | 0 | val-40 | 446 | 0.625 | 0.775 (step_0004) | 0.150 | 6/3/2 | False | 2577921 | 0 | 5.9954 | 25.3 | running |
| A | skillopt | 1 | val-40 | 559 | 0.550 | 0.850 (step_0003) | 0.300 | 6/5/4 | False | 4778086 | 0 | 10.418 | 25.4 | running |
| A | skillopt | 2 | val-40 | 546 | 0.525 | 0.800 (step_0005) | 0.275 | 7/5/5 | False | 4674105 | 0 | 10.2766 | 25.4 | running |
| A | metaharness | 0 | val-40 | 600 | 0.600 | 0.975 (example_calibration) | 0.375 | 8/8/3 | False | 161527 | 572668 | 0.6715 | 19.6 | native finish |
| A | metaharness | 1 | val-40 | 600 | 0.625 | 0.875 (typed_value_fidelity) | 0.250 | 8/8/4 | False | 175419 | 836229 | 0.7676 | 20.0 | native finish |
| A | metaharness | 2 | val-40 | 600 | 0.600 | 0.900 (example_reproduce) | 0.300 | 8/8/4 | False | 214291 | 905568 | 0.9386 | 22.4 | running |
| A | evoskill | 0 | val-40 | 332 | 0.550 | 0.800 (iter-skill-17) | 0.250 | 6/6/6 | False | 387197 | 497881 | 1.259 | 12.3 | native finish |
| A | evoskill | 1 | val-40 | 364 | 0.550 | 0.875 (iter-skill-10) | 0.325 | 7/7/6 | False | 584636 | 400985 | 1.7335 | 15.2 | running |
| A | evoskill | 2 | val-40 | 364 | 0.550 | 0.850 (iter-skill-9) | 0.300 | 7/7/5 | False | 569326 | 399024 | 1.7018 | 15.2 | running |
| A | wikiskill | 0 | val-40 | 241 | 0.575 | 0.625 (S0) | 0.050 | 1/1/0 | True | 106541 | 92902 | 0.3033 | 20.6 | running |
| A | wikiskill | 1 | val-40 | 244 | 0.525 | 0.725 (it001) | 0.200 | 2/1/1 | False | 100612 | 77412 | 0.2987 | 20.7 | running |
| A | wikiskill | 2 | val-40 | 229 | 0.500 | 0.650 (it001) | 0.150 | 1/1/1 | False | 85738 | 41108 | 0.2476 | 20.7 | running |
| A | trace2skill | 0 | val-40 | 200 | 0.500 | 0.700 (error) | 0.200 | 2/2/1 | False | 2202310 | 0 | 6.8207 | 15.6 | native finish |
| A | trace2skill | 1 | val-40 | 200 | 0.525 | 0.800 (combined) | 0.275 | 2/2/1 | False | 2225291 | 0 | 6.958 | 14.2 | native finish |
| A | trace2skill | 2 | val-40 | 200 | 0.525 | 0.750 (combined) | 0.225 | 2/2/1 | False | 2085988 | 0 | 6.4927 | 16.1 | native finish |
| A | ace | 0 | -- | 151 | -- | -- (--) | -- | 0/0/0 | None | 1385426 | 0 | 3.705 | 8.7 | running |
| A | ace | 1 | -- | 89 | -- | -- (--) | -- | 0/0/0 | None | 728098 | 0 | 1.9735 | 8.7 | running |
| A | ace | 2 | -- | 83 | -- | -- (--) | -- | 0/0/0 | None | 607122 | 0 | 1.6776 | 8.7 | running |
| A | mipro | 0 | val-40 | 143 | 0.575 | 0.575 (3d5fee3dfdc1) | 0.000 | 7/0/0 | True | 178651 | 0 | 0.5792 | 20.7 | running |
| A | mipro | 1 | val-40 | 158 | 0.550 | 0.550 (3d5fee3dfdc1) | 0.000 | 9/0/0 | True | 181449 | 0 | 0.6009 | 20.7 | running |
| A | mipro | 2 | val-40 | 156 | 0.600 | 0.600 (3d5fee3dfdc1) | 0.000 | 8/0/0 | True | 178826 | 0 | 0.5906 | 20.7 | running |
| B | hc | 0 | opt-49 | 294 | 0.531 | 0.531 (seed) | 0.000 | 1/1/0 | True | 277835 | 3423249 | 1.65 | 21.1 | running |
| B | hc | 1 | opt-49 | 392 | 0.653 | 0.653 (seed) | 0.000 | 8/8/0 | True | 622609 | 5926534 | 3.179 | 21.1 | running |
| B | hc | 2 | opt-49 | 392 | 0.542 | 0.542 (seed) | 0.000 | 2/2/0 | True | 205171 | 2490339 | 1.1977 | 21.1 | running |
| B | ao | 0 | opt-49 | 198 | 0.604 | 0.604 (seed) | 0.000 | 2/0/0 | True | 1018932 | 9478573 | 4.9191 | 11.6 | native finish |
| B | ao | 1 | opt-49 | 197 | 0.612 | 0.612 (seed) | 0.000 | 1/0/0 | True | 842779 | 10229243 | 4.701 | 20.9 | running |
| B | ao | 2 | opt-49 | 172 | 0.612 | 0.612 (seed) | 0.000 | 0/0/0 | True | 1039149 | 15545003 | 6.4566 | 17.6 | native finish |
| B | gepa | 0 | sel-25 | 262 | 0.600 | 0.720 (cand_0004) | 0.120 | 13/5/5 | False | 348501 | 0 | 1.2593 | 21.1 | running |
| B | gepa | 1 | sel-25 | 286 | 0.400 | 0.680 (cand_0014) | 0.280 | 16/6/6 | False | 393102 | 0 | 1.3974 | 21.1 | running |
| B | gepa | 2 | sel-25 | 296 | 0.600 | 0.720 (cand_0015) | 0.120 | 18/5/5 | False | 419022 | 0 | 1.4427 | 21.1 | running |
| B | harnesslens | 0 | -- | 108 | -- | -- (--) | -- | 0/0/0 | None | 4039960 | 318388 | 10.6346 | 10.8 | stopped (unclassified) |
| B | harnesslens | 1 | -- | 105 | -- | -- (--) | -- | 0/0/0 | None | 2443426 | 387315 | 7.0014 | 11.4 | running |
| B | harnesslens | 2 | -- | 105 | -- | -- (--) | -- | 0/0/0 | None | 4091565 | 227833 | 10.6905 | 10.8 | stopped (unclassified) |
| B | oneshot | 0 | opt-49 | 123 | 0.562 | 0.562 (seed) | 0.000 | 1/1/0 | True | 174123 | 2014245 | 0.9993 | 5.1 | native finish (iterations) |
| B | oneshot | 1 | opt-49 | 148 | 0.571 | 0.714 (cand_0001) | 0.143 | 1/1/1 | False | 199013 | 3352636 | 1.3734 | 4.9 | native finish (iterations) |
| B | oneshot | 2 | opt-49 | 123 | 0.653 | 0.653 (seed) | 0.000 | 1/1/0 | True | 141128 | 1531722 | 0.7744 | 4.4 | native finish (iterations) |
| B | seed | 0 | opt/sel | 98 | opt 0.561 / sel 0.600 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.5 | native finish |
| B | seed | 1 | opt/sel | 98 | opt 0.602 / sel 0.580 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.5 | native finish |
| B | seed | 2 | opt/sel | 98 | opt 0.653 / sel 0.620 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.8 | native finish |
| C | hc | 0 | opt-20 | 200 | 0.450 | 0.450 (seed) | 0.000 | 2/2/0 | True | 373678 | 3697567 | 2.0022 | 15.4 | running |
| C | hc | 1 | opt-20 | 100 | 0.450 | 0.450 (seed) | 0.000 | 3/3/0 | True | 285571 | 2990763 | 1.5649 | 15.4 | running |
| C | hc | 2 | opt-20 | 180 | 0.550 | 0.550 (seed) | 0.000 | 4/4/0 | True | 324428 | 3238356 | 1.6796 | 15.4 | running |
| C | ao | 0 | opt-20 | 110 | 0.550 | 0.550 (seed) | 0.000 | 0/0/0 | True | 554012 | 5514194 | 2.7512 | 11.3 | native finish |
| C | ao | 1 | opt-20 | 110 | 0.550 | 0.550 (seed) | 0.000 | 0/0/0 | True | 564650 | 4051700 | 2.4403 | 7.7 | native finish |
| C | ao | 2 | opt-20 | 71 | 0.450 | 0.450 (seed) | 0.000 | 1/0/0 | True | 523420 | 2466110 | 1.975 | 9.8 | native finish |
| C | gepa | 0 | sel-10 | 139 | 0.800 | 1.000 (cand_0005) | 0.200 | 10/6/6 | False | 245812 | 0 | 1.0047 | 15.4 | running |
| C | gepa | 1 | sel-10 | 107 | 0.800 | 0.900 (cand_0001) | 0.100 | 9/4/4 | False | 231843 | 0 | 0.9399 | 15.4 | running |
| C | gepa | 2 | sel-10 | 129 | 0.900 | 1.000 (cand_0001) | 0.100 | 12/4/4 | False | 269218 | 0 | 0.977 | 15.3 | running |
| C | oneshot | 0 | opt-20 | 60 | 0.500 | 0.737 (cand_0001) | 0.237 | 1/1/1 | False | 93027 | 1279390 | 0.5998 | 5.7 | native finish (iterations) |
| C | oneshot | 1 | opt-20 | 50 | 0.550 | 0.550 (seed) | 0.000 | 1/1/0 | True | 107372 | 1500867 | 0.7143 | 3.2 | native finish (iterations) |
| C | oneshot | 2 | opt-20 | 50 | 0.526 | 0.526 (seed) | 0.000 | 1/1/0 | True | 125833 | 1796170 | 0.8116 | 3.0 | native finish (iterations) |
| C | seed | 0 | opt/sel | 42 | opt 0.525 / sel 0.850 | -- (--) | -- | 0/0/0 | None | None | None | None | 6.3 | native finish |
| C | seed | 1 | opt/sel | 40 | opt 0.550 / sel 0.850 | -- (--) | -- | 0/0/0 | None | None | None | None | 4.0 | native finish |
| C | seed | 2 | opt/sel | 42 | opt 0.575 / sel 0.750 | -- (--) | -- | 0/0/0 | None | None | None | None | 5.3 | native finish |
| A-E12 | hcstock | 0 | val-40 | 344 | 0.564 | 0.775 (cand_0001) | 0.211 | 6/5/1 | False | 244673 | 1176730 | 0.9747 | 12.3 | running |
| A-E12 | hcstock | 1 | val-40 | 421 | 0.526 | 0.875 (cand_0002) | 0.349 | 8/7/2 | False | 364786 | 1980222 | 1.5074 | 12.3 | running |
| A-E12 | hcstock | 2 | val-40 | 405 | 0.553 | 0.875 (cand_0004) | 0.322 | 8/7/3 | False | 381597 | 1754116 | 1.5044 | 12.3 | running |
| C-E12 | hcstock | 0 | opt-20 | 120 | 0.500 | 0.737 (cand_0001) | 0.237 | 5/5/1 | False | 491389 | 4595287 | 2.4714 | 12.7 | running |
| C-E12 | hcstock | 1 | opt-20 | 160 | 0.650 | 0.650 (seed) | 0.000 | 7/7/0 | True | 629047 | 7040976 | 3.5051 | 12.7 | running |
| C-E12 | hcstock | 2 | opt-20 | 160 | 0.474 | 0.789 (cand_0002) | 0.316 | 7/7/2 | False | 651328 | 5783524 | 3.2349 | 12.7 | running |
| C-E12 | bestofk | 0 | opt-20 | 140 | 0.500 | 0.800 (prop_02) | 0.300 | 6/6/0 | False | 1327579 | 18298241 | 8.7779 | 12.2 | running |
| C-E12 | bestofk | 1 | opt-20 | 140 | 0.650 | 0.750 (prop_03) | 0.100 | 6/6/0 | False | 1150457 | 15406071 | 7.532 | 8.9 | running |
| C-E12 | bestofk | 2 | opt-20 | 160 | 0.474 | 0.800 (prop_01) | 0.326 | 7/7/0 | False | 1051091 | 15304257 | 7.0602 | 8.9 | running |

Notes: champion = what the method itself would return (CapEvolve: state best_id/best_val; GEPA, MIPRO, others: last selected or argmax of full selection-split evaluations). ACE and HarnessLens have no candidate/selection step yet. Optimizer USD covers priced (Claude) calls only; unpriced tokens are in runs.csv.

## Gate behaviour (CapEvolve)

| suite | arm | seed | cands | screens | confirms | promoted | rejected | vetoed | indecisive (reasons) | infra-missing |
|---|---|---|---|---|---|---|---|---|---|---|
| A | hc | 0 | 3 | 1 | 0 | 0 | 0 | 1 | 1 coverage<0.95 (90%) x1 | 1 |
| A | hc | 1 | 2 | 1 | 1 | 1 | 0 | 0 | 0  | 0 |
| A | hc | 2 | 3 | 1 | 0 | 0 | 0 | 1 | 1 coverage<0.95 (92%) x1 | 3 |
| A | ao | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0  | 0 |
| A | ao | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0  | 0 |
| A | ao | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0  | 0 |
| B | hc | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0  | 0 |
| B | hc | 1 | 8 | 8 | 0 | 0 | 8 | 0 | 0  | 0 |
| B | hc | 2 | 2 | 2 | 1 | 0 | 2 | 0 | 0  | 0 |
| B | ao | 0 | 2 | 0 | 0 | 0 | 2 | 0 | 0  | 0 |
| B | ao | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 0  | 0 |
| B | ao | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0  | 0 |
| C | hc | 0 | 2 | 2 | 1 | 0 | 2 | 0 | 0  | 0 |
| C | hc | 1 | 3 | 3 | 0 | 0 | 3 | 0 | 1 coverage<0.95 (90%) x1 | 0 |
| C | hc | 2 | 4 | 4 | 0 | 0 | 4 | 0 | 0  | 0 |
| C | ao | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0  | 0 |
| C | ao | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0  | 0 |
| C | ao | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 0  | 0 |
| A-E12 | hcstock | 0 | 6 | 5 | 0 | 1 | 4 | 0 | 0  | 0 |
| A-E12 | hcstock | 1 | 8 | 7 | 0 | 2 | 5 | 0 | 0  | 0 |
| A-E12 | hcstock | 2 | 8 | 7 | 0 | 3 | 4 | 0 | 0  | 0 |
| C-E12 | hcstock | 0 | 5 | 5 | 0 | 1 | 4 | 0 | 0  | 0 |
| C-E12 | hcstock | 1 | 7 | 7 | 0 | 0 | 7 | 0 | 0  | 0 |
| C-E12 | hcstock | 2 | 7 | 7 | 0 | 2 | 5 | 0 | 0  | 0 |

## Edits by capability surface (candidates touching surface / changed lines)

| suite | arm | cands | system_prompt | task_template | tool_code | mcp | skill_files | process_docs | reference | other |
|---|---|---|---|---|---|---|---|---|---|---|
| A | ao | 3 | 3 / 38 | 3 / 10 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | evoskill | 20 | 17 / 1391 | 0 / 0 | 0 / 0 | 0 / 0 | 17 / 1289 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | gepa | 43 | 38 / 2748 | 33 / 2756 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | hc | 6 | 6 / 73 | 6 / 14 | 0 / 0 | 0 / 0 | 0 / 0 | 3 / 1125 | 0 / 0 | 0 / 0 |
| A | metaharness | 24 | 24 / 394 | 24 / 197 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | mipro | 24 | 24 / 2980 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | skillopt | 19 | 19 / 210 | 19 / 743 | 0 / 0 | 0 / 0 | 19 / 953 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | trace2skill | 6 | 6 / 224 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| A | wikiskill | 4 | 4 / 212 | 0 / 0 | 0 / 0 | 0 / 0 | 4 / 192 | 0 / 0 | 0 / 0 | 0 / 0 |
| A-E12 | hcstock | 22 | 22 / 505 | 22 / 98 | 0 / 0 | 0 / 0 | 0 / 0 | 19 / 6962 | 0 / 0 | 0 / 0 |
| B | ao | 3 | 3 / 35 | 0 / 0 | 3 / 306 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| B | gepa | 47 | 47 / 3886 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| B | hc | 11 | 8 / 97 | 0 / 0 | 11 / 507 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| B | oneshot | 3 | 3 / 53 | 0 / 0 | 3 / 217 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | ao | 1 | 1 / 13 | 0 / 0 | 1 / 151 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | gepa | 31 | 31 / 2528 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | hc | 9 | 9 / 101 | 0 / 0 | 9 / 947 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C | oneshot | 3 | 3 / 40 | 0 / 0 | 3 / 489 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C-E12 | bestofk | 19 | 19 / 540 | 0 / 0 | 19 / 4687 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| C-E12 | hcstock | 19 | 19 / 278 | 0 / 0 | 19 / 2671 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

## Infra and errors (uniform classifier, main + chaser rows)

| suite | arm | rollouts | errors | infra | candidate | unverifiable |
|---|---|---|---|---|---|---|
| A | gepa | 634 | 20 | 20 | 0 | 0 |
| A | skillopt | 1560 | 185 | 64 | 121 | 0 |
| A | metaharness | 1800 | 90 | 90 | 0 | 0 |
| A | evoskill | 1071 | 40 | 40 | 0 | 0 |
| A | wikiskill | 552 | 51 | 51 | 0 | 0 |
| A | trace2skill | 602 | 51 | 49 | 2 | 0 |
| A | ace | 336 | 23 | 23 | 0 | 0 |
| A | mipro | 441 | 19 | 18 | 1 | 0 |
| A | hc | 560 | 30 | 30 | 0 | 0 |
| A | ao | 480 | 23 | 23 | 0 | 0 |
| A-E12 | hcstock | 1160 | 15 | 15 | 0 | 0 |
| B | seed | 444 | 0 | 0 | 0 | 0 |
| B | oneshot | 394 | 8 | 8 | 0 | 0 |
| B | gepa | 811 | 0 | 0 | 0 | 0 |
| B | hc | 1078 | 7 | 7 | 0 | 0 |
| B | ao | 517 | 3 | 3 | 0 | 0 |
| C | seed | 180 | 0 | 0 | 0 | 0 |
| C | oneshot | 160 | 3 | 3 | 0 | 0 |
| C | gepa | 366 | 1 | 0 | 0 | 1 |
| C | hc | 499 | 5 | 5 | 0 | 0 |
| C | ao | 291 | 2 | 2 | 0 | 0 |
| C-E12 | hcstock | 500 | 6 | 6 | 0 | 0 |
