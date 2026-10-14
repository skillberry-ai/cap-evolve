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

Infrastructure and missing cells (per_arm_report.json; counts only):

| key | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| B|1s | 450 | 447 | 31 | 3 | 0 | 0 | 0 | 0 | 0 |
| B|ao | 450 | 450 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|ctl | 450 | 434 | 104 | 16 | 0 | 0 | 0 | 0 | 0 |
| B|gepa | 300 | 300 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|mipro | 450 | 450 | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|nohist | 450 | 435 | 102 | 15 | 0 | 0 | 0 | 0 | 0 |
| B|p | 450 | 450 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|pt | 450 | 450 | 13 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|rulep | 450 | 450 | 18 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|seed | 300 | 300 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|seed-check | 150 | 150 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|t | 450 | 414 | 196 | 36 | 0 | 0 | 0 | 0 | 0 |
| TOTAL | 5550 | 5480 | 489 | 70 | 0 | 0 | 0 | 0 | 0 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| 1s | 300 | 260 | 200 | 59786 | 10.1 |
| ace | 300 | 253 | 219 | 150985 | 12.0 |
| ao | 300 | 229 | 215 | 60918 | 11.6 |
| ctl | 300 | 314 | 226 | 52315 | 8.9 |
| gepa | 300 | 279 | 230 | 111966 | 14.4 |
| gepafull | 300 | 264 | 234 | 124763 | 14.2 |
| mipro | 300 | 221 | 196 | 72257 | 11.2 |
| nohist | 300 | 342 | 239 | 52015 | 8.7 |
| p | 300 | 255 | 216 | 79918 | 12.0 |
| pt | 300 | 259 | 208 | 64512 | 10.8 |
| rulep | 300 | 269 | 214 | 61809 | 10.3 |
| seed | 200 | 230 | 199 | 58756 | 11.4 |
| seed-check | 100 | 217 | 202 | 61985 | 11.6 |
| t | 300 | 363 | 244 | 39444 | 7.5 |

Search cost (optimizer = Sonnet 5.5 at the proxy list price of protocol/pricing.json, from the run's cost_summary.json; blank = no cost_summary.json in the run dir; search rollouts = counted rollouts of the B* manifest for v1 windows, and for v2 windows the run's state.json metric_calls, which on tau includes the host-side finalize rollouts and is NOT the counted-rollout definition):

| arm | seed | optimizer USD (proxy) | optimizer non-cache-read tokens | optimizer calls | search rollouts | source |
|---|---|---|---|---|---|---|
| 1s | 0 | 3.79 | 657307 | 136 | 240 | cost_summary.json |
| 1s | 1 | 3.63 | 614040 | 136 | 230 | cost_summary.json |
| 1s | 2 | 3.52 | 578729 | 122 | 240 | cost_summary.json |
| ace | 0 | 4.50 | 1603016 | 166 | 290 | collect_metrics gateway ledger |
| ace | 1 | 5.03 | 1820665 | 175 | 297 | collect_metrics gateway ledger |
| ace | 2 | 4.87 | 1749600 | 175 | 300 | collect_metrics gateway ledger |
| ao | 0 | 1.52 | 213034 | 46 | 30 | cost_summary.json |
| ao | 1 | 4.21 | 1137921 | 70 | 310 | cost_summary.json |
| ao | 2 | 1.54 | 170533 | 51 | 30 | cost_summary.json |
| ctl | 0 | 0.86 | 113798 | 29 | 50 | cost_summary.json |
| ctl | 1 | 0.79 | 104730 | 26 | 60 | cost_summary.json |
| ctl | 2 | 0.71 | 108085 | 20 | 60 | cost_summary.json |
| gepa | 0 |  |  |  | 302 |  |
| gepa | 1 |  |  |  | 309 |  |
| gepa | 2 |  |  |  | 310 |  |
| gepafull | 0 | 4.21 | 994173 | 28 | 304 | collect_metrics gateway ledger |
| gepafull | 1 | 4.12 | 973867 | 30 | 303 | collect_metrics gateway ledger |
| gepafull | 2 | 4.39 | 983402 | 29 | 309 | collect_metrics gateway ledger |
| harnesslens | 0 |  |  |  |  |  |
| harnesslens | 1 |  |  |  |  |  |
| harnesslens | 2 |  |  |  |  |  |
| mipro | 0 | 0.29 | 90251 | 18 | 215 | collect_metrics gateway ledger |
| mipro | 1 | 0.33 | 101488 | 18 | 219 | collect_metrics gateway ledger |
| mipro | 2 | 0.33 | 107749 | 18 | 213 | collect_metrics gateway ledger |
| nohist | 0 | 5.81 | 852569 | 209 | 240 | cost_summary.json |
| nohist | 1 | 5.28 | 798572 | 192 | 240 | cost_summary.json |
| nohist | 2 | 5.78 | 848461 | 210 | 240 | cost_summary.json |
| p | 0 | 2.27 | 475251 | 88 | 240 | cost_summary.json |
| p | 1 | 2.95 | 600232 | 106 | 240 | cost_summary.json |
| p | 2 | 2.74 | 565690 | 95 | 240 | cost_summary.json |
| pt | 0 | 3.28 | 547570 | 128 | 240 | cost_summary.json |
| pt | 1 | 5.01 | 811105 | 166 | 240 | cost_summary.json |
| pt | 2 | 4.85 | 721468 | 171 | 230 | cost_summary.json |
| rulep | 0 | 3.49 | 551128 | 125 | 320 | cost_summary.json |
| rulep | 1 | 2.70 | 455040 | 102 | 320 | cost_summary.json |
| rulep | 2 | 3.78 | 546005 | 130 | 400 | cost_summary.json |
| t | 0 | 2.50 | 462440 | 105 | 240 | cost_summary.json |
| t | 1 | 3.34 | 555882 | 123 | 240 | cost_summary.json |
| t | 2 | 2.67 | 457860 | 111 | 240 | cost_summary.json |

