# Window A: per-arm tables (user-directed early unblinding, erratum 36)

Task set: 70 tasks, 70 families (cluster = family; split filter ('',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 2 | 0.357 | 0.357 | [0.249, 0.465] | - | - | 0 | 0.357 |
| seed-check | 1 | 1 | 0.357 | 0.357 | [0.242, 0.472] | - | - | 0 | 0.357 |
| ace | 3 | 1 | 0.486 | 0.486 | [0.373, 0.599] | s0:0.500, s1:0.457, s2:0.500 | 0/3 | 0 | 0.486 |
| ao | 3 | 1 | 0.376 | 0.357 | [0.249, 0.465] | s0:0.343, s1:0.414, s2:0.371 | 3/3 | 0 | 0.357 |
| evoskill | 3 | 1 | 0.467 | 0.467 | [0.356, 0.578] | s0:0.443, s1:0.486, s2:0.471 | 0/3 | 0 | 0.467 |
| gepa | 3 | 1 | 0.495 | 0.495 | [0.385, 0.606] | s0:0.529, s1:0.500, s2:0.457 | 0/3 | 0 | 0.495 |
| hc | 3 | 1 | 0.410 | 0.386 | [0.280, 0.491] | s0:0.386, s1:0.414, s2:0.429 | 1/3 | 0 | 0.386 |
| hcstock | 3 | 1 | 0.462 | 0.462 | [0.356, 0.568] | s0:0.414, s1:0.500, s2:0.471 | 0/3 | 0 | 0.462 |
| metaharness | 3 | 1 | 0.510 | 0.510 | [0.397, 0.622] | s0:0.529, s1:0.471, s2:0.529 | 0/3 | 0 | 0.510 |
| mipro | 3 | 1 | 0.481 | 0.481 | [0.371, 0.591] | s0:0.529, s1:0.471, s2:0.443 | 0/3 | 0 | 0.481 |
| skillopt | 3 | 1 | 0.510 | 0.510 | [0.401, 0.618] | s0:0.471, s1:0.543, s2:0.514 | 0/3 | 0 | 0.510 |
| trace2skill | 3 | 1 | 0.476 | 0.476 | [0.365, 0.587] | s0:0.471, s1:0.471, s2:0.486 | 0/3 | 0 | 0.476 |
| wikiskill | 3 | 1 | 0.476 | 0.476 | [0.366, 0.587] | s0:0.486, s1:0.500, s2:0.443 | 0/3 | 0 | 0.476 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: +0.000 (SE 0.049, n=12); 1: -0.045 (SE 0.051, n=11); 2: +0.000 (SE 0.042, n=16); 3: +0.083 (SE 0.040, n=18); 4: +0.000 (SE 0.060, n=8); 5: -0.042 (SE 0.049, n=12); 6: +0.000 (SE 0.040, n=18); 7: +0.023 (SE 0.036, n=22); 8: -0.042 (SE 0.049, n=12); 9: -0.045 (SE 0.051, n=11). Range 0.129, SE of difference 0.067, drift flag (>2 SE): False.

Seed-check minus seed (empirical null of window noise, 9D(ii)): +0.000, 95% CI [-0.076, 0.076], p 1.000.

Inert artifacts re-scored in this window (as measured minus in-window seed; identical content, so this is pure measurement noise; excluded from every contrast): ao/s0: -0.014 [-0.078, 0.050]; ao/s1: +0.057 [-0.006, 0.120]; ao/s2: +0.014 [-0.062, 0.090]; hc/s2: +0.071 [0.010, 0.133]

**Suite A primary 5A** (Holm m = 12; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc vs seed | +0.029 | [-0.025, 0.082] | [-0.107, 0.164] | 0.292 | 0.584 | equivalent within +-0.10 | +0.029 (0.584) | a 1/3, b 0/1 | +0.03, +0.06, +0.00 |
| hc vs gepa | -0.110 | [-0.159, -0.060] | [-0.237, 0.018] | <0.001 | <0.001 | inferior | -0.110 (<0.001) | a 1/3, b 0/3 | -0.11, -0.08, -0.14 |
| hc vs skillopt | -0.124 | [-0.188, -0.059] | [-0.280, 0.032] | <0.001 | 0.003 | inferior | -0.124 (0.003) | a 1/3, b 0/3 | -0.12, -0.10, -0.15 |
| hc vs metaharness | -0.124 | [-0.191, -0.057] | [-0.285, 0.038] | <0.001 | 0.004 | inferior | -0.124 (0.004) | a 1/3, b 0/3 | -0.12, -0.10, -0.15 |
| hc vs wikiskill | -0.090 | [-0.151, -0.030] | [-0.239, 0.058] | 0.004 | 0.023 | inferior | -0.090 (0.023) | a 1/3, b 0/3 | -0.09, -0.06, -0.12 |
| hc vs evoskill | -0.081 | [-0.143, -0.019] | [-0.232, 0.070] | 0.011 | 0.045 | inferior | -0.081 (0.045) | a 1/3, b 0/3 | -0.08, -0.05, -0.11 |
| ao vs seed | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 0/1 | +0.00, +0.00, +0.00 |
| ao vs gepa | -0.138 | [-0.212, -0.064] | [-0.298, 0.022] | <0.001 | 0.004 | inferior | -0.138 (0.004) | a 3/3, b 0/3 | -0.14, -0.14, -0.14 |
| ao vs skillopt | -0.152 | [-0.241, -0.063] | [-0.344, 0.039] | 0.001 | 0.007 | inferior | -0.152 (0.007) | a 3/3, b 0/3 | -0.15, -0.15, -0.15 |
| ao vs metaharness | -0.152 | [-0.236, -0.069] | [-0.333, 0.028] | <0.001 | 0.004 | inferior | -0.152 (0.004) | a 3/3, b 0/3 | -0.15, -0.15, -0.15 |
| ao vs wikiskill | -0.119 | [-0.204, -0.035] | [-0.301, 0.063] | 0.006 | 0.032 | inferior | -0.119 (0.032) | a 3/3, b 0/3 | -0.12, -0.12, -0.12 |
| ao vs evoskill | -0.110 | [-0.197, -0.022] | [-0.299, 0.080] | 0.015 | 0.046 | inferior | -0.110 (0.046) | a 3/3, b 0/3 | -0.11, -0.11, -0.11 |

**Suite A secondary 5B(i) vs seed** (Holm m = 9; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| gepa vs seed | +0.138 | [0.064, 0.212] | [-0.045, 0.321] | <0.001 | 0.004 | superior | +0.138 (0.004) | a 0/3, b 0/1 | +0.17, +0.14, +0.10 |
| skillopt vs seed | +0.152 | [0.063, 0.241] | [-0.059, 0.364] | 0.001 | 0.007 | superior | +0.152 (0.007) | a 0/3, b 0/1 | +0.11, +0.19, +0.16 |
| metaharness vs seed | +0.152 | [0.069, 0.236] | [-0.046, 0.350] | <0.001 | 0.004 | superior | +0.152 (0.004) | a 0/3, b 0/1 | +0.17, +0.11, +0.17 |
| evoskill vs seed | +0.110 | [0.022, 0.197] | [-0.088, 0.307] | 0.015 | 0.022 | superior | +0.110 (0.022) | a 0/3, b 0/1 | +0.09, +0.13, +0.11 |
| wikiskill vs seed | +0.119 | [0.035, 0.204] | [-0.078, 0.316] | 0.006 | 0.019 | superior | +0.119 (0.019) | a 0/3, b 0/1 | +0.13, +0.14, +0.09 |
| trace2skill vs seed | +0.119 | [0.046, 0.193] | [-0.041, 0.279] | 0.002 | 0.011 | superior | +0.119 (0.011) | a 0/3, b 0/1 | +0.11, +0.11, +0.13 |
| ace vs seed | +0.129 | [0.045, 0.212] | [-0.062, 0.319] | 0.003 | 0.016 | superior | +0.129 (0.016) | a 0/3, b 0/1 | +0.14, +0.10, +0.14 |
| mipro vs seed | +0.124 | [0.039, 0.209] | [-0.089, 0.336] | 0.005 | 0.019 | superior | +0.124 (0.019) | a 0/3, b 0/1 | +0.17, +0.11, +0.09 |
| hcstock vs seed | +0.105 | [0.025, 0.185] | [-0.099, 0.309] | 0.011 | 0.022 | superior | +0.105 (0.022) | a 0/3, b 0/1 | +0.06, +0.14, +0.11 |

**Suite A secondary 5B(ii) CapEvolve vs others** (Holm m = 7; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc vs ao | +0.029 | [-0.025, 0.082] | [-0.107, 0.164] | 0.292 | 0.292 | not testable (inert) | +0.029 (0.292) | a 1/3, b 3/3 | +0.03, +0.06, +0.00 |
| hc vs trace2skill | -0.090 | [-0.152, -0.029] | [-0.240, 0.059] | 0.004 | 0.016 | inferior | -0.090 (0.016) | a 1/3, b 0/3 | -0.09, -0.06, -0.12 |
| hc vs ace | -0.100 | [-0.165, -0.035] | [-0.258, 0.058] | 0.003 | 0.016 | inferior | -0.100 (0.016) | a 1/3, b 0/3 | -0.10, -0.07, -0.13 |
| hc vs mipro | -0.095 | [-0.156, -0.035] | [-0.244, 0.054] | 0.003 | 0.015 | inferior | -0.095 (0.015) | a 1/3, b 0/3 | -0.10, -0.07, -0.12 |
| ao vs trace2skill | -0.119 | [-0.193, -0.046] | [-0.278, 0.040] | 0.002 | 0.013 | inferior | -0.119 (0.013) | a 3/3, b 0/3 | -0.12, -0.12, -0.12 |
| ao vs ace | -0.129 | [-0.212, -0.045] | [-0.309, 0.052] | 0.003 | 0.016 | inferior | -0.129 (0.016) | a 3/3, b 0/3 | -0.13, -0.13, -0.13 |
| ao vs mipro | -0.124 | [-0.209, -0.039] | [-0.306, 0.059] | 0.005 | 0.016 | inferior | -0.124 (0.016) | a 3/3, b 0/3 | -0.12, -0.12, -0.12 |

**Suite A S-stock (5P-1)** (Holm m = 6; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hcstock vs seed | +0.105 | [0.025, 0.185] | [-0.099, 0.309] | 0.011 | 0.067 | inconclusive | +0.105 (0.067) | a 0/3, b 0/1 | +0.06, +0.14, +0.11 |
| hcstock vs gepa | -0.033 | [-0.081, 0.014] | [-0.182, 0.115] | 0.163 | 0.489 | equivalent within +-0.10 | -0.033 (0.489) | a 0/3, b 0/3 | -0.08, +0.00, -0.02 |
| hcstock vs skillopt | -0.048 | [-0.095, -0.000] | [-0.197, 0.101] | 0.049 | 0.246 | equivalent within +-0.10 | -0.048 (0.246) | a 0/3, b 0/3 | -0.10, -0.01, -0.04 |
| hcstock vs metaharness | -0.048 | [-0.095, -0.000] | [-0.197, 0.101] | 0.049 | 0.246 | equivalent within +-0.10 | -0.048 (0.246) | a 0/3, b 0/3 | -0.10, -0.01, -0.04 |
| hcstock vs wikiskill | -0.014 | [-0.072, 0.044] | [-0.180, 0.151] | 0.625 | 1.000 | equivalent within +-0.10 | -0.014 (1.000) | a 0/3, b 0/3 | -0.06, +0.02, -0.00 |
| hcstock vs evoskill | -0.005 | [-0.046, 0.037] | [-0.146, 0.136] | 0.820 | 1.000 | equivalent within +-0.10 | -0.005 (1.000) | a 0/3, b 0/3 | -0.05, +0.03, +0.00 |

Infrastructure and missing cells (per_arm_report.json of THIS window; counts only; key prefix is the scoring mode):

| mode\|arm (mode B = matched-checkpoint artifacts; it is NOT the suite letter) | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| B|seed | 140 | 140 | 1 | 0 | 0 | 0 | 0 | 8 | 21 |
| TOTAL | 2520 | 2520 | 1 | 0 | 0 | 0 | 0 | 33 | 77 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| ace | 210 | 388 | 136 | 270096 | 10.6 |
| ao | 210 | 418 | 270 | 145705 | 15.9 |
| evoskill | 210 | 273 | 110 | 124849 | 9.9 |
| gepa | 210 | 251 | 100 | 88909 | 8.9 |
| hc | 210 | 331 | 96 | 113827 | 13.1 |
| hcstock | 210 | 127 | 86 | 29821 | 5.0 |
| metaharness | 210 | 286 | 105 | 99803 | 9.3 |
| mipro | 210 | 677 | 726 | 288788 | 22.5 |
| seed | 140 | 382 | 234 | 135911 | 15.4 |
| seed-check | 70 | 336 | 139 | 119593 | 14.0 |
| skillopt | 210 | 178 | 95 | 58879 | 5.9 |
| trace2skill | 210 | 385 | 130 | 156206 | 12.1 |
| wikiskill | 210 | 394 | 130 | 160020 | 13.2 |

Search cost (optimizer = Sonnet 5.5 at the proxy list price of protocol/pricing.json, from the run's cost_summary.json; blank = no cost_summary.json in the run dir; search rollouts = counted rollouts of the B* manifest for v1 windows, and for v2 windows the run's state.json metric_calls, which on tau includes the host-side finalize rollouts and is NOT the counted-rollout definition):

| arm | seed | optimizer USD (proxy) | optimizer non-cache-read tokens | optimizer calls | search rollouts | source |
|---|---|---|---|---|---|---|
| ace | 0 | 9.56 | 3902518 | 238 | 390 | collect_metrics gateway ledger |
| ace | 1 | 9.61 | 3951431 | 259 | 409 | collect_metrics gateway ledger |
| ace | 2 | 9.80 | 4018892 | 252 | 361 | collect_metrics gateway ledger |
| ao | 0 | 10.38 | 3958447 | 75 | 262 | collect_metrics gateway ledger |
| ao | 1 | 2.92 | 990763 | 40 | 318 | collect_metrics gateway ledger |
| ao | 2 | 4.47 | 1602367 | 51 | 293 | collect_metrics gateway ledger |
| evoskill | 0 | 1.26 | 387197 | 36 | 332 | collect_metrics gateway ledger |
| evoskill | 1 | 2.33 | 785636 | 53 | 452 | collect_metrics gateway ledger |
| evoskill | 2 | 2.22 | 744375 | 54 | 452 | collect_metrics gateway ledger |
| gepa | 0 | 2.11 | 603717 | 20 | 600 | collect_metrics gateway ledger |
| gepa | 1 | 1.43 | 424746 | 14 | 600 | collect_metrics gateway ledger |
| gepa | 2 | 1.39 | 427579 | 17 | 600 | collect_metrics gateway ledger |
| hc | 0 | 0.81 | 206870 | 28 | 600 | collect_metrics gateway ledger |
| hc | 1 | 0.34 | 87560 | 13 | 600 | collect_metrics gateway ledger |
| hc | 2 | 2.47 | 649254 | 92 | 600 | collect_metrics gateway ledger |
| hcstock | 0 |  |  |  | 600 |  |
| hcstock | 1 |  |  |  | 600 |  |
| hcstock | 2 |  |  |  | 600 |  |
| metaharness | 0 | 0.67 | 161527 | 34 | 600 | collect_metrics gateway ledger |
| metaharness | 1 | 0.77 | 175419 | 41 | 600 | collect_metrics gateway ledger |
| metaharness | 2 | 0.94 | 214291 | 43 | 600 | collect_metrics gateway ledger |
| mipro | 0 | 0.58 | 178651 | 27 | 468 | collect_metrics gateway ledger |
| mipro | 1 | 0.60 | 181449 | 27 | 523 | collect_metrics gateway ledger |
| mipro | 2 | 0.59 | 178826 | 27 | 522 | collect_metrics gateway ledger |
| skillopt | 0 | 8.13 | 3572673 | 62 | 526 | collect_metrics gateway ledger |
| skillopt | 1 | 10.42 | 4778086 | 59 | 600 | collect_metrics gateway ledger |
| skillopt | 2 | 11.18 | 5102141 | 61 | 566 | collect_metrics gateway ledger |
| trace2skill | 0 | 6.82 | 2202310 | 372 | 200 | collect_metrics gateway ledger |
| trace2skill | 1 | 6.96 | 2225291 | 371 | 200 | collect_metrics gateway ledger |
| trace2skill | 2 | 6.49 | 2085988 | 374 | 200 | collect_metrics gateway ledger |
| wikiskill | 0 | 1.21 | 779252 | 31 | 521 | collect_metrics gateway ledger |
| wikiskill | 1 | 1.31 | 861649 | 33 | 523 | collect_metrics gateway ledger |
| wikiskill | 2 | 1.40 | 881298 | 31 | 524 | collect_metrics gateway ledger |

