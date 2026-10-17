# Window V3B1CHAIN/main: per-arm tables (descriptive window, amendment 12 errata 15, 16, 19)

Task set: 20 tasks, 20 families (cluster = family; split filter ('test',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 20 | 0.500 | 0.500 | [0.329, 0.671] | - | - | 0 | 0.500 |
| seed-check | 1 | 10 | 0.490 | 0.490 | [0.300, 0.680] | - | - | 0 | 0.490 |
| hc3_s0_cand_0002 | 1 | 10 | 0.545 | 0.545 | [0.358, 0.732] | s0:0.545 | 0/1 | 0 | 0.545 |
| hc3_s0_cand_0005 | 1 | 10 | 0.600 | 0.600 | [0.420, 0.780] | s0:0.600 | 0/1 | 0 | 0.600 |
| hc3_s1_cand_0002 | 1 | 10 | 0.525 | 0.525 | [0.339, 0.711] | s0:0.525 | 0/1 | 0 | 0.525 |
| hc3_s1_cand_0008 | 1 | 10 | 0.560 | 0.560 | [0.378, 0.742] | s0:0.560 | 0/1 | 0 | 0.560 |
| hc3_s1_cand_0009 | 1 | 10 | 0.575 | 0.575 | [0.384, 0.766] | s0:0.575 | 0/1 | 0 | 0.575 |
| hc3_s1_cand_0014 | 1 | 10 | 0.555 | 0.555 | [0.366, 0.744] | s0:0.555 | 0/1 | 0 | 0.555 |
| hc3_s1_cand_0018 | 1 | 10 | 0.545 | 0.545 | [0.361, 0.729] | s0:0.545 | 0/1 | 0 | 0.545 |
| hc3_s2_cand_0004 | 1 | 10 | 0.525 | 0.525 | [0.341, 0.709] | s0:0.525 | 0/1 | 0 | 0.525 |
| hc3_s2_cand_0007 | 1 | 10 | 0.575 | 0.575 | [0.387, 0.763] | s0:0.575 | 0/1 | 0 | 0.575 |
| hc3_s2_cand_0020 | 1 | 10 | 0.500 | 0.500 | [0.320, 0.680] | s0:0.500 | 0/1 | 0 | 0.500 |
| hcstock_s0_cand_0001 | 1 | 10 | 0.555 | 0.555 | [0.381, 0.729] | s0:0.555 | 0/1 | 0 | 0.555 |
| hcstock_s0_cand_0002 | 1 | 10 | 0.505 | 0.505 | [0.318, 0.692] | s0:0.505 | 0/1 | 0 | 0.505 |
| hcstock_s0_cand_0005 | 1 | 10 | 0.625 | 0.625 | [0.443, 0.807] | s0:0.625 | 0/1 | 0 | 0.625 |
| hcstock_s1_cand_0001 | 1 | 10 | 0.535 | 0.535 | [0.356, 0.714] | s0:0.535 | 0/1 | 0 | 0.535 |
| hcstock_s1_cand_0002 | 1 | 10 | 0.565 | 0.565 | [0.363, 0.767] | s0:0.565 | 0/1 | 0 | 0.565 |
| hcstock_s1_cand_0009 | 1 | 10 | 0.550 | 0.550 | [0.356, 0.744] | s0:0.550 | 0/1 | 0 | 0.550 |
| hcstock_s2_cand_0001 | 1 | 10 | 0.525 | 0.525 | [0.345, 0.705] | s0:0.525 | 0/1 | 0 | 0.525 |
| hcstock_s2_cand_0002 | 1 | 10 | 0.600 | 0.600 | [0.417, 0.783] | s0:0.600 | 0/1 | 0 | 0.600 |
| hcstock_s2_cand_0011 | 1 | 10 | 0.600 | 0.600 | [0.418, 0.782] | s0:0.600 | 0/1 | 0 | 0.600 |

**CHAIN window (descriptive; commissioned after the main results were seen, erratum 16). Per chain: held-out mean of each ACCEPTED intermediate candidate (k = 10, test-20) minus the in-window seed (n = 20), with the artifact-level CR1 CI; the last row of each chain is the final champion from the MAIN window, shown for reference and NOT in this window (different time block). 'search-time rollouts' = cumulative counted rollouts at the candidate's evaluation, from candidates.jsonl.**

| chain | step | candidate | search-time rollouts | held-out mean | delta vs in-window seed | 95% CI | step change |
|---|---|---|---|---|---|---|---|
| hc3 s0 | 1 | cand_0002 | None | 0.545 | +0.045 | [-0.012, 0.102] |  |
| hc3 s0 | 2 | cand_0005 | None | 0.600 | +0.100 | [0.002, 0.198] | +0.055 |
| hc3 s0 | final | cand_0016 (main window) | None | 0.585 | +0.087 vs main-window seed | [-0.009, 0.184] | -0.015 (cross-window) |
| hc3 s1 | 1 | cand_0002 | None | 0.525 | +0.025 | [-0.039, 0.089] |  |
| hc3 s1 | 2 | cand_0008 | None | 0.560 | +0.060 | [-0.024, 0.144] | +0.035 |
| hc3 s1 | 3 | cand_0009 | None | 0.575 | +0.075 | [-0.011, 0.161] | +0.015 |
| hc3 s1 | 4 | cand_0014 | None | 0.555 | +0.055 | [-0.059, 0.169] | -0.020 |
| hc3 s1 | 5 | cand_0018 | None | 0.545 | +0.045 | [-0.059, 0.149] | -0.010 |
| hc3 s1 | final | cand_0031 (main window) | None | 0.560 | +0.062 vs main-window seed | [-0.058, 0.183] | +0.015 (cross-window) |
| hc3 s2 | 1 | cand_0004 | None | 0.525 | +0.025 | [-0.108, 0.158] |  |
| hc3 s2 | 2 | cand_0007 | None | 0.575 | +0.075 | [-0.034, 0.184] | +0.050 |
| hc3 s2 | 3 | cand_0020 | None | 0.500 | +0.000 | [-0.106, 0.106] | -0.075 |
| hc3 s2 | final | cand_0021 (main window) | None | 0.500 | +0.002 vs main-window seed | [-0.124, 0.129] | +0.000 (cross-window) |
| hcstock s0 | 1 | cand_0001 | 300 | 0.555 | +0.055 | [-0.041, 0.151] |  |
| hcstock s0 | 2 | cand_0002 | 450 | 0.505 | +0.005 | [-0.082, 0.092] | -0.050 |
| hcstock s0 | 3 | cand_0005 | 900 | 0.625 | +0.125 | [0.029, 0.221] | +0.120 |
| hcstock s0 | final | cand_0012 (main window) | 1950 | 0.615 | +0.118 vs main-window seed | [-0.007, 0.242] | -0.010 (cross-window) |
| hcstock s1 | 1 | cand_0001 | 300 | 0.535 | +0.035 | [-0.046, 0.116] |  |
| hcstock s1 | 2 | cand_0002 | 450 | 0.565 | +0.065 | [-0.029, 0.159] | +0.030 |
| hcstock s1 | 3 | cand_0009 | 1500 | 0.550 | +0.050 | [-0.037, 0.137] | -0.015 |
| hcstock s1 | final | cand_0018 (main window) | 2850 | 0.645 | +0.148 vs main-window seed | [0.045, 0.250] | +0.095 (cross-window) |
| hcstock s2 | 1 | cand_0001 | 300 | 0.525 | +0.025 | [-0.050, 0.100] |  |
| hcstock s2 | 2 | cand_0002 | 450 | 0.600 | +0.100 | [0.005, 0.195] | +0.075 |
| hcstock s2 | 3 | cand_0011 | 1800 | 0.600 | +0.100 | [-0.020, 0.220] | -0.000 |
| hcstock s2 | final | cand_0019 (main window) | 3000 | 0.625 | +0.128 vs main-window seed | [-0.020, 0.275] | +0.025 (cross-window) |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: -0.050 (SE 0.032, n=123); 1: +0.022 (SE 0.031, n=127); 2: +0.024 (SE 0.036, n=95); 3: +0.019 (SE 0.047, n=55). Range 0.073, SE of difference 0.053, drift flag (>2 SE): False.

Seed-check minus seed (empirical null of window noise, 9D(ii)): -0.010, 95% CI [-0.084, 0.064], p 0.780.

Infrastructure and missing cells (per_arm_report.json of THIS window; counts only; key prefix is the scoring mode):

| mode\|arm (mode B = matched-checkpoint artifacts; it is NOT the suite letter) | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| TOTAL | 4400 | 4400 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| hc3_s0_cand_0002 | 200 | 280 | 216 | 94409 | 12.5 |
| hc3_s0_cand_0005 | 200 | 318 | 226 | 115784 | 13.0 |
| hc3_s1_cand_0002 | 200 | 287 | 216 | 92908 | 12.1 |
| hc3_s1_cand_0008 | 200 | 317 | 214 | 105591 | 12.9 |
| hc3_s1_cand_0009 | 200 | 291 | 221 | 103489 | 12.4 |
| hc3_s1_cand_0014 | 200 | 303 | 217 | 116161 | 13.0 |
| hc3_s1_cand_0018 | 200 | 314 | 228 | 120729 | 12.7 |
| hc3_s2_cand_0004 | 200 | 264 | 216 | 89185 | 11.8 |
| hc3_s2_cand_0007 | 200 | 255 | 210 | 97708 | 11.8 |
| hc3_s2_cand_0020 | 200 | 254 | 208 | 102032 | 12.0 |
| hcstock_s0_cand_0001 | 200 | 312 | 222 | 115840 | 12.8 |
| hcstock_s0_cand_0002 | 200 | 297 | 224 | 118067 | 11.0 |
| hcstock_s0_cand_0005 | 200 | 225 | 213 | 121508 | 10.7 |
| hcstock_s1_cand_0001 | 200 | 264 | 220 | 106984 | 12.1 |
| hcstock_s1_cand_0002 | 200 | 232 | 198 | 93602 | 10.8 |
| hcstock_s1_cand_0009 | 200 | 316 | 219 | 135833 | 12.4 |
| hcstock_s2_cand_0001 | 200 | 371 | 236 | 137595 | 14.6 |
| hcstock_s2_cand_0002 | 200 | 339 | 240 | 127537 | 13.6 |
| hcstock_s2_cand_0011 | 200 | 240 | 221 | 158267 | 11.4 |
| seed | 400 | 217 | 199 | 59103 | 10.9 |
| seed-check | 200 | 224 | 200 | 65881 | 11.5 |

