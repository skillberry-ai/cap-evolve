# Unblinded results (user-directed early unblinding, analysis_plan erratum 36), 2026-10-14

Files: window_<W>.md, v1_vs_v2.md, unblind_results.json. Script `analysis/scripts/unblind_analysis.py`.

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

# Window B: per-arm tables (user-directed early unblinding, erratum 36)

Task set: 40 tasks, 40 families (cluster = family; split filter ('test',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 3 | 0.625 | 0.625 | [0.504, 0.746] | - | - | 0 | 0.625 |
| seed-check | 1 | 3 | 0.617 | 0.617 | [0.497, 0.736] | - | - | 0 | 0.617 |
| ao | 3 | 3 | 0.628 | 0.625 | [0.504, 0.746] | s0:0.575, s1:0.633, s2:0.675 | 3/3 | 0 | 0.625 |
| gepa | 3 | 3 | 0.653 | 0.653 | [0.550, 0.756] | s0:0.658, s1:0.608, s2:0.692 | 0/3 | 0 | 0.653 |
| harnesslens | 3 | 3 | 0.422 | 0.422 | [0.342, 0.503] | s0:0.317, s1:0.475, s2:0.475 | 0/3 | 0 | 0.422 |
| hc | 3 | 3 | 0.622 | 0.625 | [0.504, 0.746] | s0:0.600, s1:0.617, s2:0.650 | 3/3 | 0 | 0.625 |
| hcstock | 3 | 3 | 0.642 | 0.644 | [0.544, 0.745] | s0:0.642, s1:0.617, s2:0.667 | 1/3 | 0 | 0.644 |
| oneshot | 3 | 3 | 0.550 | 0.550 | [0.445, 0.655] | s0:0.400, s1:0.633, s2:0.617 | 0/3 | 19 | 0.560 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: -0.089 (SE 0.079, n=15); 2: -0.024 (SE 0.082, n=14); 4: +0.067 (SE 0.097, n=10); 5: +0.000 (SE 0.093, n=11); 6: +0.095 (SE 0.116, n=7); 7: +0.056 (SE 0.125, n=6); 8: +0.000 (SE 0.089, n=12); 9: +0.000 (SE 0.116, n=7); 10: +0.048 (SE 0.116, n=7); 11: +0.000 (SE 0.089, n=12); 12: -0.018 (SE 0.071, n=19). Range 0.184, SE of difference 0.140, drift flag (>2 SE): False.

Seed-check minus seed (empirical null of window noise, 9D(ii)): -0.008, 95% CI [-0.125, 0.109], p 0.886.

Inert artifacts re-scored in this window (as measured minus in-window seed; identical content, so this is pure measurement noise; excluded from every contrast): ao/s0: -0.050 [-0.145, 0.045]; ao/s1: +0.008 [-0.084, 0.100]; ao/s2: +0.050 [-0.039, 0.139]; hc/s0: -0.025 [-0.131, 0.081]; hc/s1: -0.008 [-0.100, 0.084]; hc/s2: +0.025 [-0.081, 0.131]; hcstock/s1: -0.008 [-0.109, 0.093]

**Suite B primary 5A** (Holm m = 8; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc vs seed | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 0/1 | +0.00, +0.00, +0.00 |
| hc vs oneshot | +0.075 | [-0.018, 0.168] | [-0.123, 0.273] | 0.112 | 0.672 | not testable (inert) | +0.065 (0.974) | a 3/3, b 0/3 | +0.08, +0.08, +0.08 |
| hc vs gepa | -0.028 | [-0.115, 0.060] | [-0.214, 0.159] | 0.525 | 1.000 | not testable (inert) | -0.028 (1.000) | a 3/3, b 0/3 | -0.03, -0.03, -0.03 |
| hc vs harnesslens | +0.203 | [0.108, 0.297] | [0.002, 0.404] | <0.001 | <0.001 | superior | +0.203 (<0.001) | a 3/3, b 0/3 | +0.20, +0.20, +0.20 |
| ao (dagger) vs seed | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 0/1 | +0.00, +0.00, +0.00 |
| ao (dagger) vs oneshot | +0.075 | [-0.018, 0.168] | [-0.123, 0.273] | 0.112 | 0.672 | not testable (inert) | +0.065 (0.974) | a 3/3, b 0/3 | +0.08, +0.08, +0.08 |
| ao (dagger) vs gepa | -0.028 | [-0.115, 0.060] | [-0.214, 0.159] | 0.525 | 1.000 | not testable (inert) | -0.028 (1.000) | a 3/3, b 0/3 | -0.03, -0.03, -0.03 |
| ao (dagger) vs harnesslens | +0.203 | [0.108, 0.297] | [0.002, 0.404] | <0.001 | <0.001 | superior | +0.203 (<0.001) | a 3/3, b 0/3 | +0.20, +0.20, +0.20 |

**Suite B primary 5A WITHOUT dagger arms ['ao'] (Holm rescaled)** (Holm m = 4; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc vs seed | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 0/1 | +0.00, +0.00, +0.00 |
| hc vs oneshot | +0.075 | [-0.018, 0.168] | [-0.123, 0.273] | 0.112 | 0.336 | not testable (inert) | +0.065 (0.487) | a 3/3, b 0/3 | +0.08, +0.08, +0.08 |
| hc vs gepa | -0.028 | [-0.115, 0.060] | [-0.214, 0.159] | 0.525 | 1.000 | not testable (inert) | -0.028 (1.000) | a 3/3, b 0/3 | -0.03, -0.03, -0.03 |
| hc vs harnesslens | +0.203 | [0.108, 0.297] | [0.002, 0.404] | <0.001 | <0.001 | superior | +0.203 (<0.001) | a 3/3, b 0/3 | +0.20, +0.20, +0.20 |

**Suite B secondary 5B(i) vs seed** (Holm m = 3; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| gepa vs seed | +0.028 | [-0.060, 0.115] | [-0.186, 0.241] | 0.525 | 1.000 | inconclusive | +0.028 (1.000) | a 0/3, b 0/1 | +0.03, -0.02, +0.07 |
| harnesslens vs seed | -0.203 | [-0.297, -0.108] | [-0.506, 0.100] | <0.001 | <0.001 | inferior | -0.203 (<0.001) | a 0/3, b 0/1 | -0.31, -0.15, -0.15 |
| hcstock vs seed | +0.019 | [-0.052, 0.090] | [-0.140, 0.179] | 0.583 | 1.000 | equivalent within +-0.10 | +0.019 (1.000) | a 1/3, b 0/1 | +0.02, +0.00, +0.04 |

**Suite B secondary 5B(ii) CapEvolve vs others** (Holm m = 1; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc vs ao (dagger) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 3/3 | +0.00, +0.00, +0.00 |

**Suite B S-stock (9G; hcstock = E12B stock-gate arm if present)** (Holm m = 3; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hcstock vs seed | +0.019 | [-0.052, 0.090] | [-0.140, 0.179] | 0.583 | 1.000 | equivalent within +-0.10 | +0.019 (1.000) | a 1/3, b 0/1 | +0.02, +0.00, +0.04 |
| hcstock vs gepa | -0.008 | [-0.067, 0.050] | [-0.144, 0.127] | 0.776 | 1.000 | equivalent within +-0.10 | -0.008 (1.000) | a 1/3, b 0/3 | -0.01, -0.03, +0.01 |
| hcstock vs harnesslens | +0.222 | [0.143, 0.301] | [0.046, 0.399] | <0.001 | <0.001 | superior | +0.222 (<0.001) | a 1/3, b 0/3 | +0.22, +0.20, +0.24 |

# Window C: per-arm tables (user-directed early unblinding, erratum 36)

Task set: 20 tasks, 20 families (cluster = family; split filter ('test',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 3 | 0.467 | 0.467 | [0.281, 0.652] | - | - | 0 | 0.467 |
| seed-check | 1 | 3 | 0.517 | 0.517 | [0.331, 0.702] | - | - | 0 | 0.517 |
| ao | 3 | 3 | 0.517 | 0.467 | [0.281, 0.652] | s0:0.500, s1:0.517, s2:0.533 | 3/3 | 0 | 0.467 |
| gepa | 3 | 3 | 0.544 | 0.544 | [0.393, 0.696] | s0:0.550, s1:0.550, s2:0.533 | 0/3 | 0 | 0.544 |
| hc | 3 | 3 | 0.511 | 0.517 | [0.338, 0.695] | s0:0.600, s1:0.450, s2:0.483 | 1/3 | 0 | 0.517 |
| hcstock | 3 | 3 | 0.594 | 0.567 | [0.393, 0.740] | s0:0.583, s1:0.550, s2:0.650 | 1/3 | 0 | 0.567 |
| oneshot | 3 | 3 | 0.600 | 0.600 | [0.425, 0.775] | s0:0.650, s1:0.583, s2:0.567 | 0/3 | 2 | 0.600 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: +0.037 (SE 0.105, n=9); 1: -0.167 (SE 0.158, n=4); 2: -0.083 (SE 0.158, n=4); 3: +0.000 (SE 0.183, n=3); 4: +0.056 (SE 0.129, n=6); 5: -0.111 (SE 0.129, n=6); 6: +0.030 (SE 0.095, n=11); 7: +0.042 (SE 0.112, n=8); 8: +0.167 (SE 0.129, n=6); 9: -0.222 (SE 0.183, n=3). Range 0.389, SE of difference 0.200, drift flag (>2 SE): False.

Seed-check minus seed (empirical null of window noise, 9D(ii)): +0.050, 95% CI [-0.042, 0.142], p 0.267.

Inert artifacts re-scored in this window (as measured minus in-window seed; identical content, so this is pure measurement noise; excluded from every contrast): ao/s0: +0.033 [-0.067, 0.133]; ao/s1: +0.050 [-0.104, 0.204]; ao/s2: +0.067 [-0.029, 0.163]; hc/s1: -0.017 [-0.164, 0.131]; hcstock/s1: +0.083 [-0.039, 0.206]

**Suite C primary 5A** (Holm m = 6; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc vs seed | +0.050 | [-0.021, 0.121] | [-0.181, 0.281] | 0.154 | 0.617 | n.s. | +0.050 (0.617) | a 1/3, b 0/1 | +0.13, +0.00, +0.02 |
| hc vs oneshot | -0.083 | [-0.190, 0.023] | [-0.367, 0.200] | 0.118 | 0.590 | n.s. | -0.083 (0.590) | a 1/3, b 0/3 | -0.00, -0.13, -0.12 |
| hc vs gepa | -0.028 | [-0.140, 0.084] | [-0.320, 0.264] | 0.609 | 1.000 | n.s. | -0.028 (1.000) | a 1/3, b 0/3 | +0.06, -0.08, -0.06 |
| ao (dagger) vs seed | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 0/1 | +0.00, +0.00, +0.00 |
| ao (dagger) vs oneshot | -0.133 | [-0.280, 0.013] | [-0.435, 0.168] | 0.072 | 0.434 | n.s. | -0.133 (0.434) | a 3/3, b 0/3 | -0.13, -0.13, -0.13 |
| ao (dagger) vs gepa | -0.078 | [-0.206, 0.051] | [-0.342, 0.187] | 0.221 | 0.663 | n.s. | -0.078 (0.663) | a 3/3, b 0/3 | -0.08, -0.08, -0.08 |

**Suite C primary 5A WITHOUT dagger arms ['ao'] (Holm rescaled)** (Holm m = 3; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc vs seed | +0.050 | [-0.021, 0.121] | [-0.181, 0.281] | 0.154 | 0.354 | n.s. | +0.050 (0.354) | a 1/3, b 0/1 | +0.13, +0.00, +0.02 |
| hc vs oneshot | -0.083 | [-0.190, 0.023] | [-0.367, 0.200] | 0.118 | 0.354 | n.s. | -0.083 (0.354) | a 1/3, b 0/3 | -0.00, -0.13, -0.12 |
| hc vs gepa | -0.028 | [-0.140, 0.084] | [-0.320, 0.264] | 0.609 | 0.609 | n.s. | -0.028 (0.609) | a 1/3, b 0/3 | +0.06, -0.08, -0.06 |

**Suite C secondary 5B(i) vs seed** (Holm m = 2; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| gepa vs seed | +0.078 | [-0.051, 0.206] | [-0.188, 0.343] | 0.221 | 0.221 | n.s. | +0.078 (0.221) | a 0/3, b 0/1 | +0.08, +0.08, +0.07 |
| hcstock vs seed | +0.100 | [-0.007, 0.207] | [-0.218, 0.418] | 0.064 | 0.129 | n.s. | +0.100 (0.129) | a 1/3, b 0/1 | +0.12, +0.00, +0.18 |

**Suite C secondary 5B(ii) CapEvolve vs others** (Holm m = 1; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc vs ao (dagger) | +0.050 | [-0.021, 0.121] | [-0.181, 0.281] | 0.154 | 0.154 | n.s. | +0.050 (0.154) | a 1/3, b 3/3 | +0.13, +0.00, +0.02 |

**Suite C S-stock (5P-1)** (Holm m = 2; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hcstock vs seed | +0.100 | [-0.007, 0.207] | [-0.218, 0.418] | 0.064 | 0.129 | n.s. | +0.100 (0.129) | a 1/3, b 0/1 | +0.12, +0.00, +0.18 |
| hcstock vs gepa | +0.022 | [-0.056, 0.101] | [-0.259, 0.304] | 0.560 | 0.560 | n.s. | +0.022 (0.560) | a 1/3, b 0/3 | +0.04, -0.08, +0.11 |

# Window D: per-arm tables (user-directed early unblinding, erratum 36)

Task set: 40 tasks, 40 families (cluster = family; split filter ('test',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 10 | 0.650 | 0.650 | [0.554, 0.746] | - | - | 0 | 0.650 |
| seed-check | 1 | 5 | 0.675 | 0.675 | [0.575, 0.775] | - | - | 0 | 0.675 |
| 1s | 3 | 5 | 0.735 | 0.735 | [0.649, 0.821] | s0:0.745, s1:0.715, s2:0.745 | 0/3 | 5 | 0.735 |
| ctl | 3 | 5 | 0.763 | 0.763 | [0.683, 0.844] | s0:0.810, s1:0.775, s2:0.705 | 0/3 | 7 | 0.766 |
| gepa | 3 | 5 | 0.708 | 0.708 | [0.611, 0.806] | s0:0.725, s1:0.725, s2:0.675 | 0/3 | 0 | 0.708 |
| nohist | 3 | 5 | 0.722 | 0.722 | [0.637, 0.807] | s0:0.785, s1:0.710, s2:0.670 | 0/3 | 3 | 0.722 |
| p | 3 | 5 | 0.688 | 0.688 | [0.591, 0.786] | s0:0.755, s1:0.595, s2:0.715 | 0/3 | 0 | 0.688 |
| pt | 3 | 5 | 0.765 | 0.765 | [0.681, 0.849] | s0:0.745, s1:0.795, s2:0.755 | 0/3 | 6 | 0.774 |
| rulep | 3 | 5 | 0.768 | 0.768 | [0.684, 0.853] | s0:0.785, s1:0.725, s2:0.795 | 0/3 | 5 | 0.769 |
| t | 3 | 5 | 0.623 | 0.602 | [0.502, 0.701] | s0:0.465, s1:0.690, s2:0.715 | 1/3 | 16 | 0.602 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: -0.024 (SE 0.058, n=42); 1: -0.082 (SE 0.061, n=38); 2: +0.002 (SE 0.056, n=44); 3: -0.071 (SE 0.054, n=48); 4: -0.037 (SE 0.061, n=38); 5: -0.000 (SE 0.058, n=41); 6: +0.053 (SE 0.064, n=34); 7: +0.155 (SE 0.052, n=51); 8: -0.028 (SE 0.062, n=36); 9: +0.004 (SE 0.071, n=28). Range 0.236, SE of difference 0.085, drift flag (>2 SE): True.

Seed-check minus seed (empirical null of window noise, 9D(ii)): +0.025, 95% CI [-0.030, 0.080], p 0.364.

Inert artifacts re-scored in this window (as measured minus in-window seed; identical content, so this is pure measurement noise; excluded from every contrast): t/s2: +0.065 [0.007, 0.123]

**5I block-adjusted headline (seed drift > 2 SE): delta vs seed after subtracting the seed's task-demeaned block effects from every trial (block effects {0: -0.024, 1: -0.082, 2: 0.002, 3: -0.071, 4: -0.037, 5: -0.0, 6: 0.053, 7: 0.155, 8: -0.028, 9: 0.038, 10: -0.1})**

| arm | block-adjusted delta vs seed | 95% CI (artifact, CR1) | per-seed |
|---|---|---|---|
| 1s | +0.094 | [0.015, 0.174] | +0.11, +0.07, +0.10 |
| ctl | +0.123 | [0.050, 0.196] | +0.17, +0.13, +0.07 |
| gepa | +0.066 | [0.007, 0.125] | +0.09, +0.08, +0.03 |
| nohist | +0.081 | [0.014, 0.148] | +0.14, +0.07, +0.02 |
| p | +0.049 | [0.010, 0.087] | +0.11, -0.05, +0.08 |
| pt | +0.123 | [0.037, 0.208] | +0.11, +0.16, +0.10 |
| rulep | +0.127 | [0.065, 0.189] | +0.14, +0.08, +0.16 |
| t | -0.042 | [-0.075, -0.010] | -0.18, +0.05, +0.00 |

**Suite D primary family (m = 11)** (Holm m = 11; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| p vs pt | -0.077 | [-0.150, -0.003] | [-0.336, 0.182] | 0.041 | 0.286 | inconclusive | -0.085 (0.232) | a 0/3, b 0/3 | -0.01, -0.17, -0.05 |
| t vs pt | -0.163 | [-0.253, -0.074] | [-0.517, 0.190] | <0.001 | 0.007 | inferior | -0.172 (0.006) | a 1/3, b 0/3 | -0.30, -0.07, -0.11 |
| p vs t | +0.087 | [0.041, 0.132] | [-0.142, 0.315] | <0.001 | 0.005 | superior | +0.087 (0.005) | a 0/3, b 1/3 | +0.15, -0.01, +0.11 |
| rulep vs pt | +0.003 | [-0.047, 0.054] | [-0.139, 0.146] | 0.894 | 1.000 | equivalent within +-0.10 | -0.005 (1.000) | a 0/3, b 0/3 | +0.02, -0.04, +0.03 |
| 1s vs pt | -0.030 | [-0.075, 0.015] | [-0.135, 0.075] | 0.186 | 0.742 | equivalent within +-0.10 | -0.038 (0.457) | a 0/3, b 0/3 | -0.02, -0.05, -0.02 |
| pt vs ctl | +0.002 | [-0.034, 0.038] | [-0.099, 0.103] | 0.926 | 1.000 | equivalent within +-0.10 | +0.008 (1.000) | a 0/3, b 0/3 | -0.02, +0.03, -0.01 |
| p vs gepa | -0.020 | [-0.064, 0.024] | [-0.247, 0.207] | 0.364 | 1.000 | equivalent within +-0.10 | -0.020 (1.000) | a 0/3, b 0/3 | +0.05, -0.11, +0.01 |
| p vs seed | +0.038 | [0.001, 0.075] | [-0.183, 0.260] | 0.043 | 0.286 | equivalent within +-0.10 | +0.038 (0.260) | a 0/3, b 0/1 | +0.10, -0.06, +0.06 |
| t vs seed | -0.048 | [-0.081, -0.015] | [-0.355, 0.258] | 0.005 | 0.048 | inferior | -0.048 (0.048) | a 1/3, b 0/1 | -0.18, +0.04, +0.00 |
| pt vs seed | +0.115 | [0.028, 0.202] | [-0.082, 0.312] | 0.011 | 0.088 | inconclusive | +0.124 (0.078) | a 0/3, b 0/1 | +0.10, +0.15, +0.11 |
| nohist vs pt | -0.043 | [-0.101, 0.014] | [-0.233, 0.147] | 0.136 | 0.682 | inconclusive | -0.052 (0.457) | a 0/3, b 0/3 | +0.02, -0.05, -0.09 |

**Suite D secondary family D-sec (m = 4)** (Holm m = 4; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| gepa vs seed | +0.058 | [-0.000, 0.117] | [-0.085, 0.202] | 0.050 | 0.074 | inconclusive | +0.058 (0.072) | a 0/3, b 0/1 | +0.07, +0.07, +0.03 |
| rulep vs seed | +0.118 | [0.057, 0.180] | [-0.043, 0.279] | <0.001 | 0.002 | superior | +0.119 (0.001) | a 0/3, b 0/1 | +0.14, +0.07, +0.15 |
| 1s vs seed | +0.085 | [0.005, 0.165] | [-0.090, 0.260] | 0.037 | 0.074 | inconclusive | +0.085 (0.072) | a 0/3, b 0/1 | +0.10, +0.07, +0.10 |
| ctl vs seed | +0.113 | [0.039, 0.187] | [-0.092, 0.319] | 0.004 | 0.011 | superior | +0.116 (0.009) | a 0/3, b 0/1 | +0.16, +0.13, +0.06 |

# Window E: per-arm tables (user-directed early unblinding, erratum 36)

Task set: 20 tasks, 20 families (cluster = family; split filter ('test',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 10 | 0.480 | 0.480 | [0.312, 0.648] | - | - | 0 | 0.480 |
| seed-check | 1 | 5 | 0.510 | 0.510 | [0.332, 0.688] | - | - | 0 | 0.510 |
| 1s | 3 | 5 | 0.620 | 0.607 | [0.447, 0.766] | s0:0.650, s1:0.520, s2:0.690 | 1/3 | 2 | 0.612 |
| ace | 3 | 5 | 0.603 | 0.603 | [0.415, 0.791] | s0:0.600, s1:0.620, s2:0.590 | 0/3 | 0 | 0.603 |
| ao | 3 | 5 | 0.510 | 0.480 | [0.312, 0.648] | s0:0.510, s1:0.500, s2:0.520 | 3/3 | 0 | 0.480 |
| ctl | 3 | 5 | 0.707 | 0.707 | [0.546, 0.867] | s0:0.680, s1:0.700, s2:0.740 | 0/3 | 11 | 0.728 |
| gepa | 3 | 5 | 0.607 | 0.607 | [0.438, 0.776] | s0:0.580, s1:0.640, s2:0.600 | 0/3 | 0 | 0.607 |
| gepafull | 3 | 5 | 0.643 | 0.643 | [0.486, 0.800] | s0:0.600, s1:0.630, s2:0.700 | 0/3 | 0 | 0.643 |
| mipro | 3 | 5 | 0.537 | 0.537 | [0.359, 0.714] | s0:0.560, s1:0.610, s2:0.440 | 0/3 | 0 | 0.537 |
| nohist | 3 | 5 | 0.657 | 0.657 | [0.487, 0.826] | s0:0.670, s1:0.610, s2:0.690 | 0/3 | 14 | 0.697 |
| p | 3 | 5 | 0.573 | 0.573 | [0.384, 0.763] | s0:0.510, s1:0.640, s2:0.570 | 0/3 | 0 | 0.573 |
| pt | 3 | 5 | 0.617 | 0.610 | [0.450, 0.770] | s0:0.630, s1:0.720, s2:0.500 | 1/3 | 0 | 0.610 |
| rulep | 3 | 5 | 0.727 | 0.727 | [0.562, 0.891] | s0:0.690, s1:0.780, s2:0.710 | 0/3 | 0 | 0.727 |
| t | 3 | 5 | 0.660 | 0.660 | [0.490, 0.830] | s0:0.580, s1:0.690, s2:0.710 | 0/3 | 23 | 0.678 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: +0.042 (SE 0.073, n=24); 1: -0.029 (SE 0.060, n=35); 2: -0.000 (SE 0.074, n=23); 3: +0.042 (SE 0.082, n=19); 4: +0.019 (SE 0.070, n=26); 5: -0.018 (SE 0.058, n=38); 6: -0.017 (SE 0.060, n=35). Range 0.071, SE of difference 0.097, drift flag (>2 SE): False.

Seed-check minus seed (empirical null of window noise, 9D(ii)): +0.030, 95% CI [-0.059, 0.119], p 0.487.

Inert artifacts re-scored in this window (as measured minus in-window seed; identical content, so this is pure measurement noise; excluded from every contrast): 1s/s1: +0.040 [-0.065, 0.145]; ao/s0: +0.030 [-0.066, 0.126]; ao/s1: +0.020 [-0.092, 0.132]; ao/s2: +0.040 [-0.077, 0.157]; pt/s2: +0.020 [-0.038, 0.078]

**Suite E primary family (m = 11)** (Holm m = 11; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| p vs pt | -0.037 | [-0.150, 0.077] | [-0.320, 0.247] | 0.506 | 1.000 | n.s. | -0.037 (1.000) | a 0/3, b 1/3 | -0.10, +0.03, -0.04 |
| t vs pt | +0.050 | [-0.019, 0.119] | [-0.174, 0.274] | 0.144 | 0.889 | n.s. | +0.068 (0.378) | a 0/3, b 1/3 | -0.03, +0.08, +0.10 |
| p vs t | -0.087 | [-0.200, 0.027] | [-0.371, 0.197] | 0.127 | 0.889 | n.s. | -0.105 (0.378) | a 0/3, b 0/3 | -0.15, -0.02, -0.09 |
| rulep vs pt | +0.117 | [0.035, 0.198] | [-0.088, 0.322] | 0.008 | 0.060 | n.s. | +0.117 (0.060) | a 0/3, b 1/3 | +0.08, +0.17, +0.10 |
| 1s vs pt | -0.003 | [-0.058, 0.052] | [-0.302, 0.296] | 0.900 | 1.000 | n.s. | +0.002 (1.000) | a 1/3, b 1/3 | +0.04, -0.13, +0.08 |
| pt vs ctl | -0.097 | [-0.149, -0.045] | [-0.416, 0.223] | <0.001 | 0.011 | inferior | -0.118 (<0.001) | a 1/3, b 0/3 | -0.08, +0.01, -0.23 |
| p vs gepa | -0.033 | [-0.127, 0.060] | [-0.285, 0.218] | 0.465 | 1.000 | n.s. | -0.033 (1.000) | a 0/3, b 0/3 | -0.10, +0.03, -0.04 |
| p vs seed | +0.093 | [-0.065, 0.251] | [-0.269, 0.456] | 0.231 | 1.000 | n.s. | +0.093 (0.924) | a 0/3, b 0/1 | +0.03, +0.16, +0.09 |
| t vs seed | +0.180 | [0.058, 0.302] | [-0.125, 0.485] | 0.006 | 0.053 | n.s. | +0.197 (0.042) | a 0/3, b 0/1 | +0.10, +0.21, +0.23 |
| pt vs seed | +0.130 | [0.044, 0.216] | [-0.219, 0.479] | 0.005 | 0.049 | superior | +0.130 (0.044) | a 1/3, b 0/1 | +0.15, +0.24, +0.00 |
| nohist vs pt | +0.047 | [-0.049, 0.142] | [-0.175, 0.268] | 0.319 | 1.000 | n.s. | +0.083 (0.378) | a 0/3, b 1/3 | +0.06, +0.00, +0.08 |

**Suite E secondary family E-sec (m = 4)** (Holm m = 4; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| gepa vs seed | +0.127 | [-0.028, 0.281] | [-0.200, 0.453] | 0.103 | 0.103 | n.s. | +0.127 (0.103) | a 0/3, b 0/1 | +0.10, +0.16, +0.12 |
| rulep vs seed | +0.247 | [0.102, 0.391] | [-0.073, 0.566] | 0.002 | 0.006 | superior | +0.247 (0.006) | a 0/3, b 0/1 | +0.21, +0.30, +0.23 |
| 1s vs seed | +0.127 | [0.016, 0.238] | [-0.232, 0.485] | 0.027 | 0.055 | n.s. | +0.132 (0.052) | a 1/3, b 0/1 | +0.17, +0.00, +0.21 |
| ctl vs seed | +0.227 | [0.119, 0.335] | [-0.008, 0.462] | <0.001 | 0.001 | superior | +0.242 (0.001) | a 0/3, b 0/1 | +0.20, +0.22, +0.26 |

**Suite E competitors E-comp** (Holm m = 4; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| pt vs ace | +0.007 | [-0.085, 0.098] | [-0.349, 0.362] | 0.881 | 0.993 | n.s. | +0.007 (0.993) | a 1/3, b 0/3 | +0.03, +0.12, -0.12 |
| pt vs mipro | +0.073 | [-0.016, 0.163] | [-0.280, 0.426] | 0.103 | 0.308 | n.s. | +0.073 (0.308) | a 1/3, b 0/3 | +0.09, +0.18, -0.06 |
| pt vs gepafull | -0.033 | [-0.134, 0.067] | [-0.399, 0.332] | 0.496 | 0.993 | n.s. | -0.033 (0.993) | a 1/3, b 0/3 | -0.01, +0.08, -0.16 |
| pt vs ao (dagger) | +0.130 | [0.044, 0.216] | [-0.219, 0.479] | 0.005 | 0.020 | superior | +0.130 (0.020) | a 1/3, b 3/3 | +0.15, +0.24, -0.00 |

# Window V2/D: per-arm tables (user-directed early unblinding, erratum 36)

Task set: 40 tasks, 40 families (cluster = family; split filter ('test',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

v2 note: hc2/ao2 searches that returned the seed have no scored cell (erratum 11 (3)); they enter at the in-window seed score, delta 0. ao21 (v2.1) is inert by construction and no window cell exists.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 10 | 0.630 | 0.630 | [0.516, 0.744] | - | - | 0 | 0.630 |
| seed-check | 1 | 5 | 0.645 | 0.645 | [0.530, 0.760] | - | - | 0 | 0.645 |
| ao2 | 3 | - | n/a | 0.630 | [0.516, 0.744] | s0:inert(not rescored), s1:inert(not rescored), s2:inert(not rescored) | 3/3 | 0 | 0.630 |
| gepa | 3 | 5 | 0.670 | 0.670 | [0.576, 0.764] | s0:0.705, s1:0.620, s2:0.685 | 0/3 | 0 | 0.670 |
| hc2 | 3 | - | n/a | 0.630 | [0.516, 0.744] | s0:inert(not rescored), s1:inert(not rescored), s2:inert(not rescored) | 3/3 | 0 | 0.630 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: +0.000 (SE 0.017, n=400). Range 0.000, SE of difference 0.023, drift flag (>2 SE): False.

Seed-check minus seed (empirical null of window noise, 9D(ii)): +0.015, 95% CI [-0.066, 0.096], p 0.711.

**v2 window Suite D: family V2 (11G, m = 4)** (Holm m = 4; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc2 vs seed | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 0/1 | +0.00, +0.00, +0.00 |
| ao2 vs seed | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 0/1 | +0.00, +0.00, +0.00 |
| hc2 vs gepa | -0.040 | [-0.106, 0.026] | [-0.180, 0.100] | 0.225 | 0.900 | n.s. | -0.040 (0.900) | a 3/3, b 0/3 | -0.04, -0.04, -0.04 |
| ao2 vs gepa | -0.040 | [-0.106, 0.026] | [-0.180, 0.100] | 0.225 | 0.900 | n.s. | -0.040 (0.900) | a 3/3, b 0/3 | -0.04, -0.04, -0.04 |

**v2 window Suite D: descriptive rows (no Holm claim)** (Holm m = 1; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc2 vs ao2 | -0.000 | [-0.000, 0.000] | [-0.000, 0.000] | 0.207 | 0.207 | both returned the seed (delta 0 by construction) | -0.000 (0.207) | a 3/3, b 3/3 | -0.00, -0.00, -0.00 |
| ao21 vs seed | arm absent | | | | | not run | | | |
| ao21 vs gepa | arm absent | | | | | not run | | | |

# Window V2/E: per-arm tables (user-directed early unblinding, erratum 36)

Task set: 20 tasks, 20 families (cluster = family; split filter ('test',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

v2 note: hc2/ao2 searches that returned the seed have no scored cell (erratum 11 (3)); they enter at the in-window seed score, delta 0. ao21 (v2.1) is inert by construction and no window cell exists.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 10 | 0.425 | 0.425 | [0.260, 0.590] | - | - | 0 | 0.425 |
| seed-check | 1 | 5 | 0.490 | 0.490 | [0.312, 0.668] | - | - | 0 | 0.490 |
| ao2 | 3 | - | n/a | 0.425 | [0.260, 0.590] | s0:inert(not rescored), s1:inert(not rescored), s2:inert(not rescored) | 3/3 | 0 | 0.425 |
| gepa | 3 | 5 | 0.580 | 0.580 | [0.408, 0.752] | s0:0.600, s1:0.570, s2:0.570 | 0/3 | 0 | 0.580 |
| hc2 | 3 | 5 | 0.575 | 0.525 | [0.352, 0.698] | s0:inert(not rescored), s1:0.530, s2:0.620 | 1/3 | 4 | 0.532 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: +0.000 (SE 0.025, n=200). Range 0.000, SE of difference 0.036, drift flag (>2 SE): False.

Seed-check minus seed (empirical null of window noise, 9D(ii)): +0.065, 95% CI [-0.013, 0.143], p 0.097.

**v2 window Suite E: family V2 (11G, m = 4)** (Holm m = 4; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc2 vs seed | +0.100 | [0.023, 0.177] | [-0.189, 0.389] | 0.013 | 0.040 | superior | +0.107 (0.035) | a 1/3, b 0/1 | +0.00, +0.10, +0.20 |
| ao2 vs seed | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 0/1 | +0.00, +0.00, +0.00 |
| hc2 vs gepa | -0.055 | [-0.148, 0.038] | [-0.364, 0.254] | 0.232 | 0.464 | n.s. | -0.048 (0.591) | a 1/3, b 0/3 | -0.15, -0.05, +0.04 |
| ao2 vs gepa | -0.155 | [-0.262, -0.048] | [-0.375, 0.065] | 0.007 | 0.028 | inferior | -0.155 (0.028) | a 3/3, b 0/3 | -0.15, -0.15, -0.15 |

**v2 window Suite E: descriptive rows (no Holm claim)** (Holm m = 1; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc2 vs ao2 | +0.100 | [0.023, 0.177] | [-0.189, 0.389] | 0.013 | 0.013 | superior | +0.107 (0.012) | a 1/3, b 3/3 | -0.00, +0.10, +0.19 |
| ao21 vs seed | arm absent | | | | | not run | | | |
| ao21 vs gepa | arm absent | | | | | not run | | | |

# Window V2/A: per-arm tables (user-directed early unblinding, erratum 36)

Task set: 70 tasks, 70 families (cluster = family; split filter ('',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 2 | 0.364 | 0.364 | [0.255, 0.473] | - | - | 0 | 0.364 |
| seed-check | 1 | 1 | 0.329 | 0.329 | [0.216, 0.441] | - | - | 0 | 0.329 |
| ao2 | 3 | 1 | 0.371 | 0.371 | [0.264, 0.478] | s0:0.386, s1:0.371, s2:0.357 | 0/3 | 0 | 0.371 |
| gepa | 3 | 1 | 0.505 | 0.505 | [0.394, 0.615] | s0:0.557, s1:0.514, s2:0.443 | 0/3 | 0 | 0.505 |
| hc2 | 3 | 1 | 0.505 | 0.505 | [0.395, 0.614] | s0:0.457, s1:0.543, s2:0.514 | 0/3 | 0 | 0.505 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: +0.032 (SE 0.028, n=31); 1: -0.019 (SE 0.030, n=27); 2: -0.026 (SE 0.026, n=38); 3: +0.014 (SE 0.026, n=37); 4: +0.000 (SE 0.060, n=7). Range 0.059, SE of difference 0.052, drift flag (>2 SE): False.

Seed-check minus seed (empirical null of window noise, 9D(ii)): -0.036, 95% CI [-0.120, 0.049], p 0.402.

**Suite A v2 start (erratum 38, 40):** v2 A started from the v1 seed + empty helper scaffold + 3 prompt lines; every helper script in the HC-2 champions was written by CapEvolve. AO-2 returned its v2 start (one artifact, three identical cells; artifact-level only). AO-2 vs seed = scaffold effect (descriptive); HC-2 vs AO-2 = search effect (descriptive); HC-2 vs seed is the registered row.

**v2 window Suite A: family V2 (11G, m = 4)** (Holm m = 4; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc2 vs seed | +0.140 | [0.045, 0.236] | [-0.093, 0.374] | 0.005 | 0.014 | superior | +0.140 (0.014) | a 0/3, b 0/1 | +0.09, +0.18, +0.15 |
| ao2 vs seed | +0.007 | [-0.045, 0.059] | [-0.111, 0.125] | 0.786 | 1.000 | n.s. | +0.007 (1.000) | a 0/3, b 0/1 | +0.02, +0.01, -0.01 |
| hc2 vs gepa | +0.000 | [-0.054, 0.054] | [-0.159, 0.159] | 1.000 | 1.000 | n.s. | +0.000 (1.000) | a 0/3, b 0/3 | -0.05, +0.04, +0.01 |
| ao2 vs gepa | -0.133 | [-0.212, -0.055] | [-0.306, 0.039] | 0.001 | 0.004 | inferior | -0.133 (0.004) | a 0/3, b 0/3 | -0.12, -0.13, -0.15 |

**v2 window Suite A: descriptive rows (no Holm claim)** (Holm m = 2; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| hc2 vs ao2 | +0.133 | [0.049, 0.217] | [-0.078, 0.344] | 0.002 | 0.005 | superior | +0.133 (0.005) | a 0/3, b 0/3 | +0.09, +0.17, +0.14 |
| ao2 vs seed | +0.007 | [-0.045, 0.059] | [-0.111, 0.125] | 0.786 | 0.786 | n.s. | +0.007 (0.786) | a 0/3, b 0/1 | +0.02, +0.01, -0.01 |

# Window V21/D: per-arm tables (user-directed early unblinding, erratum 36)

Task set: 40 tasks, 40 families (cluster = family; split filter ('test',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 10 | 0.590 | 0.590 | [0.476, 0.704] | - | - | 0 | 0.590 |
| seed-check | 1 | 5 | 0.635 | 0.635 | [0.532, 0.738] | - | - | 0 | 0.635 |
| ao21 | 3 | 5 | 0.610 | 0.597 | [0.491, 0.702] | s0:0.610, s1:inert(not rescored), s2:inert(not rescored) | 2/3 | 0 | 0.597 |
| gepa | 3 | 5 | 0.668 | 0.668 | [0.561, 0.776] | s0:0.710, s1:0.655, s2:0.640 | 0/3 | 0 | 0.668 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: -0.000 (SE 0.017, n=400). Range 0.000, SE of difference 0.024, drift flag (>2 SE): False.

Seed-check minus seed (empirical null of window noise, 9D(ii)): +0.045, 95% CI [-0.020, 0.110], p 0.168.

**v2.1-AO2 (erratum 43 champions)**: the P2-accepted candidates whose commit was voided by the pooled-mode defect; secondary version (11D). Literal-final-state reading beside it: all three champions = the seed, delta 0 by construction (no scoring needed).

**v2.1 window Suite D: AO-2 v2.1 (erratum 43; secondary under 11D, own Holm m = 2)** (Holm m = 2; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| ao21 vs seed | +0.007 | [-0.015, 0.028] | [-0.048, 0.061] | 0.539 | 0.539 | n.s. | +0.007 (0.539) | a 2/3, b 0/1 | +0.02, +0.00, +0.00 |
| ao21 vs gepa | -0.072 | [-0.138, -0.006] | [-0.215, 0.071] | 0.034 | 0.068 | n.s. | -0.072 (0.068) | a 2/3, b 0/3 | -0.06, -0.08, -0.08 |

Scored champion ao21 s0 alone (descriptive; the family row above averages it with the seeds that returned the seed): vs in-window seed: +0.020 [-0.045, 0.085], p 0.539; vs seed-check (same artifact, n as the arms): -0.025 [-0.101, 0.051], p 0.507.

# v1 versus v2 (descriptive; user-directed early unblinding)

Each delta is measured inside its own window against that window's own in-window seed (n = 10 trials per task on D and E). Windows are different time blocks and are never pooled. Rows are DESCRIPTIVE unless marked; the registered v2 confirmatory rows are family V2 (11G) in the v2 window files. Inert artifacts (champion = seed) enter at the seed score, delta 0.

## Suite A (SpreadsheetBench, T = 70, seed n = 2)

v2 A started from the v1 seed + empty helper scaffold + 3 prompt lines (erratum 40); every helper script is CapEvolve-written. The A v2.1-AO2 runs have no scored cell.

| arm (window) | delta vs in-window seed | 95% CI (artifact, CR1) | 95% CI (pipeline, t2) | inert seeds | per-seed delta (seed 0, 1, 2) |
|---|---|---|---|---|---|
| v1 hc (rule P hill-climb) (A) | +0.029 | [-0.025, 0.082] | [-0.107, 0.164] | 1/3 | +0.029, +0.057, +0.000 |
| v1 hcstock (stock-gate hill-climb) (A) | +0.105 | [0.025, 0.185] | [-0.099, 0.309] | 0/3 | +0.057, +0.143, +0.114 |
| v1 ao (agent-optimize, inert) (A) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |
| v2.0 HC-2 (V2/A) | +0.140 | [0.045, 0.236] | [-0.093, 0.374] | 0/3 | +0.093, +0.179, +0.150 |
| v2.0 AO-2 (= v2 start: scaffold effect; not inert) (V2/A) | +0.007 | [-0.045, 0.059] | [-0.111, 0.125] | 0/3 | +0.021, +0.007, -0.007 |

Window-shift controls (same GEPA artifact scored in both windows when the tree hashes match): GEPA delta vs seed v1 window +0.138 [0.064, 0.212], v2 window +0.140 [0.048, 0.233]. Seed mean v1 0.357 vs v2 0.364; GEPA mean v1 0.495 vs v2 0.505.
GEPA artifact tree hashes identical across windows: True.

Difference of deltas (v2 arm minus v1 arm, each against its own window's seed; task-paired CR1 on the per-task difference of seed-averaged deltas; descriptive):

| v2 arm | v1 arm | v2 minus v1 | 95% CI |
|---|---|---|---|
| v2.0 HC-2 | v1 hc (rule P hill-climb) | +0.112 | [0.024, 0.200] |
| v2.0 HC-2 | v1 hcstock (stock-gate hill-climb) | +0.036 | [-0.060, 0.132] |
| v2.0 HC-2 | v1 ao (agent-optimize, inert) | +0.140 | [0.045, 0.236] |
| v2.0 AO-2 (= v2 start: scaffold effect; not inert) | v1 hc (rule P hill-climb) | -0.021 | [-0.089, 0.046] |
| v2.0 AO-2 (= v2 start: scaffold effect; not inert) | v1 hcstock (stock-gate hill-climb) | -0.098 | [-0.188, -0.007] |
| v2.0 AO-2 (= v2 start: scaffold effect; not inert) | v1 ao (agent-optimize, inert) | +0.007 | [-0.045, 0.059] |

## Suite D (tau2 retail, test 40)

| arm (window) | delta vs in-window seed | 95% CI (artifact, CR1) | 95% CI (pipeline, t2) | inert seeds | per-seed delta (seed 0, 1, 2) |
|---|---|---|---|---|---|
| v1 pt (stock-gate hill-climb, reference) (D) | +0.115 | [0.028, 0.202] | [-0.082, 0.312] | 0/3 | +0.095, +0.145, +0.105 |
| v1 rulep (rule P hill-climb) (D) | +0.118 | [0.057, 0.180] | [-0.043, 0.279] | 0/3 | +0.135, +0.075, +0.145 |
| v2.0 HC-2 (V2/D) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |
| v2.0 AO-2 (V2/D) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |
| v2.1 AO-2 (inert by construction) (V2/D) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |

Window-shift controls (same GEPA artifact scored in both windows when the tree hashes match): GEPA delta vs seed v1 window +0.058 [-0.000, 0.117], v2 window +0.040 [-0.026, 0.106]. Seed mean v1 0.650 vs v2 0.630; GEPA mean v1 0.708 vs v2 0.670.
GEPA artifact tree hashes identical across windows: True.

Difference of deltas (v2 arm minus v1 arm, each against its own window's seed; task-paired CR1 on the per-task difference of seed-averaged deltas; descriptive):

| v2 arm | v1 arm | v2 minus v1 | 95% CI |
|---|---|---|---|
| v2.0 HC-2 | v1 pt (stock-gate hill-climb, reference) | -0.115 | [-0.202, -0.028] |
| v2.0 HC-2 | v1 rulep (rule P hill-climb) | -0.118 | [-0.180, -0.057] |
| v2.0 AO-2 | v1 pt (stock-gate hill-climb, reference) | -0.115 | [-0.202, -0.028] |
| v2.0 AO-2 | v1 rulep (rule P hill-climb) | -0.118 | [-0.180, -0.057] |
| v2.1 AO-2 (inert by construction) | v1 pt (stock-gate hill-climb, reference) | -0.115 | [-0.202, -0.028] |
| v2.1 AO-2 (inert by construction) | v1 rulep (rule P hill-climb) | -0.118 | [-0.180, -0.057] |

## Suite E (tau2 airline, test 20)

| arm (window) | delta vs in-window seed | 95% CI (artifact, CR1) | 95% CI (pipeline, t2) | inert seeds | per-seed delta (seed 0, 1, 2) |
|---|---|---|---|---|---|
| v1 pt (stock-gate hill-climb, reference) (E) | +0.130 | [0.044, 0.216] | [-0.219, 0.479] | 1/3 | +0.150, +0.240, +0.000 |
| v1 rulep (rule P hill-climb) (E) | +0.247 | [0.102, 0.391] | [-0.073, 0.566] | 0/3 | +0.210, +0.300, +0.230 |
| v1 ao (agent-optimize, dagger) (E) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |
| v2.0 HC-2 (V2/E) | +0.100 | [0.023, 0.177] | [-0.189, 0.389] | 1/3 | +0.000, +0.105, +0.195 |
| v2.0 AO-2 (V2/E) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |
| v2.1 AO-2 (inert by construction) (V2/E) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |

Window-shift controls (same GEPA artifact scored in both windows when the tree hashes match): GEPA delta vs seed v1 window +0.127 [-0.028, 0.281], v2 window +0.155 [0.048, 0.262]. Seed mean v1 0.480 vs v2 0.425; GEPA mean v1 0.607 vs v2 0.580.
GEPA artifact tree hashes identical across windows: True.

Difference of deltas (v2 arm minus v1 arm, each against its own window's seed; task-paired CR1 on the per-task difference of seed-averaged deltas; descriptive):

| v2 arm | v1 arm | v2 minus v1 | 95% CI |
|---|---|---|---|
| v2.0 HC-2 | v1 pt (stock-gate hill-climb, reference) | -0.030 | [-0.120, 0.060] |
| v2.0 HC-2 | v1 rulep (rule P hill-climb) | -0.147 | [-0.271, -0.023] |
| v2.0 HC-2 | v1 ao (agent-optimize, dagger) | +0.100 | [0.023, 0.177] |
| v2.0 AO-2 | v1 pt (stock-gate hill-climb, reference) | -0.130 | [-0.216, -0.044] |
| v2.0 AO-2 | v1 rulep (rule P hill-climb) | -0.247 | [-0.391, -0.102] |
| v2.0 AO-2 | v1 ao (agent-optimize, dagger) | +0.000 | [-0.000, 0.000] |
| v2.1 AO-2 (inert by construction) | v1 pt (stock-gate hill-climb, reference) | -0.130 | [-0.216, -0.044] |
| v2.1 AO-2 (inert by construction) | v1 rulep (rule P hill-climb) | -0.247 | [-0.391, -0.102] |
| v2.1 AO-2 (inert by construction) | v1 ao (agent-optimize, dagger) | +0.000 | [-0.000, 0.000] |

