# Window V3B1/main: per-arm tables (released under the V3 B1 freeze declaration, amendment 12 erratum 8)

Task set: 20 tasks, 20 families (cluster = family; split filter ('test',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 20 | 0.498 | 0.498 | [0.323, 0.672] | - | - | 0 | 0.498 |
| seed-check | 1 | 10 | 0.480 | 0.480 | [0.294, 0.666] | - | - | 0 | 0.480 |
| ao22 | 3 | 10 | 0.592 | 0.592 | [0.429, 0.755] | s0:0.660, s1:0.555, s2:0.560 | 0/3 | 0 | 0.592 |
| evoskill | 3 | 10 | 0.533 | 0.533 | [0.349, 0.717] | s0:0.550, s1:0.520, s2:0.530 | 0/3 | 0 | 0.533 |
| gepa | 3 | 10 | 0.552 | 0.552 | [0.382, 0.721] | s0:0.550, s1:0.605, s2:0.500 | 0/3 | 0 | 0.552 |
| gepafull | 3 | 10 | 0.560 | 0.560 | [0.390, 0.730] | s0:0.555, s1:0.530, s2:0.595 | 0/3 | 0 | 0.560 |
| hc3 | 3 | 10 | 0.548 | 0.548 | [0.369, 0.728] | s0:0.585, s1:0.560, s2:0.500 | 0/3 | 0 | 0.548 |
| hcstock | 3 | 10 | 0.628 | 0.628 | [0.444, 0.812] | s0:0.615, s1:0.645, s2:0.625 | 0/3 | 0 | 0.628 |
| metaharness | 3 | 10 | 0.535 | 0.535 | [0.360, 0.710] | s0:0.535, s1:0.535, s2:0.535 | 0/3 | 0 | 0.535 |
| mipro | 3 | 10 | 0.517 | 0.517 | [0.340, 0.693] | s0:0.535, s1:0.530, s2:0.485 | 0/3 | 0 | 0.517 |
| skillopt | 3 | 10 | 0.558 | 0.558 | [0.394, 0.723] | s0:0.590, s1:0.495, s2:0.590 | 0/3 | 0 | 0.558 |
| trace2skill | 3 | 10 | 0.502 | 0.502 | [0.326, 0.678] | s0:0.515, s1:0.515, s2:0.475 | 0/3 | 0 | 0.502 |
| wikiskill | 3 | 10 | 0.553 | 0.553 | [0.379, 0.728] | s0:0.565, s1:0.530, s2:0.565 | 0/3 | 0 | 0.553 |

**Per-framework test mean (T = 20, k = 10 trials/task; mean of the 3 per-seed means; SE = SD of the 3 per-seed means / sqrt(3), n = 3 search seeds; per-seed means as measured)**

| framework | mean | SE across seeds | per-seed means | 95% CI of mean (artifact-level, CR1) |
|---|---|---|---|---|
| seed (n = 20 trials/task) | 0.498 | - | - | [0.323, 0.672] |
| seed-check (n = - trials/task) | 0.480 | - | - | [0.294, 0.666] |
| ao22 | 0.592 | 0.034 | 0.660, 0.555, 0.560 | [0.429, 0.755] |
| evoskill | 0.533 | 0.009 | 0.550, 0.520, 0.530 | [0.349, 0.717] |
| gepa | 0.552 | 0.030 | 0.550, 0.605, 0.500 | [0.382, 0.721] |
| gepafull | 0.560 | 0.019 | 0.555, 0.530, 0.595 | [0.390, 0.730] |
| hc3 | 0.548 | 0.025 | 0.585, 0.560, 0.500 | [0.369, 0.728] |
| hcstock | 0.628 | 0.009 | 0.615, 0.645, 0.625 | [0.444, 0.812] |
| metaharness | 0.535 | 0.000 | 0.535, 0.535, 0.535 | [0.360, 0.710] |
| mipro | 0.517 | 0.016 | 0.535, 0.530, 0.485 | [0.340, 0.693] |
| skillopt | 0.558 | 0.032 | 0.590, 0.495, 0.590 | [0.394, 0.723] |
| trace2skill | 0.502 | 0.013 | 0.515, 0.515, 0.475 | [0.326, 0.678] |
| wikiskill | 0.553 | 0.012 | 0.565, 0.530, 0.565 | [0.379, 0.728] |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: +0.004 (SE 0.027, n=158); 1: -0.008 (SE 0.026, n=170); 2: +0.011 (SE 0.040, n=72). Range 0.019, SE of difference 0.045, drift flag (>2 SE): False.

Seed-check minus seed (empirical null of window noise, 9D(ii)): -0.018, 95% CI [-0.068, 0.033], p 0.477.

**V3 B1 family P1: each CapEvolve arm vs the seed (Holm m = 3)** (Holm m = 3; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| hcstock vs seed | +0.131 | [0.013, 0.248] | [-0.113, 0.375] | 0.031 | 0.092 | 0.616 | n.s. | +0.131 (0.092) | a 0/3, b 0/1 | +0.12, +0.15, +0.13 |
| hc3 vs seed | +0.051 | [-0.054, 0.156] | [-0.191, 0.293] | 0.325 | 0.325 | 1.000 | n.s. | +0.051 (0.325) | a 0/3, b 0/1 | +0.09, +0.06, +0.00 |
| ao22 vs seed | +0.094 | [-0.005, 0.194] | [-0.158, 0.346] | 0.062 | 0.125 | 0.881 | n.s. | +0.094 (0.125) | a 0/3, b 0/1 | +0.16, +0.06, +0.06 |

**V3 B1 family P2: hcstock vs each competitor (Holm m = 8)** (Holm m = 8; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| hcstock vs evoskill | +0.095 | [0.015, 0.175] | [-0.075, 0.265] | 0.023 | 0.092 | 0.506 | n.s. | +0.095 (0.092) | a 0/3, b 0/3 | +0.08, +0.11, +0.09 |
| hcstock vs gepa | +0.077 | [0.015, 0.138] | [-0.055, 0.208] | 0.017 | 0.084 | 0.385 | n.s. | +0.077 (0.084) | a 0/3, b 0/3 | +0.06, +0.09, +0.07 |
| hcstock vs gepafull | +0.068 | [-0.016, 0.153] | [-0.109, 0.246] | 0.106 | 0.106 | 1.000 | n.s. | +0.068 (0.106) | a 0/3, b 0/3 | +0.06, +0.09, +0.07 |
| hcstock vs metaharness | +0.093 | [0.029, 0.158] | [-0.045, 0.232] | 0.007 | 0.050 | 0.177 | superior | +0.093 (0.050) | a 0/3, b 0/3 | +0.08, +0.11, +0.09 |
| hcstock vs mipro | +0.112 | [0.027, 0.196] | [-0.066, 0.289] | 0.012 | 0.073 | 0.291 | n.s. | +0.112 (0.073) | a 0/3, b 0/3 | +0.10, +0.13, +0.11 |
| hcstock vs skillopt | +0.070 | [0.003, 0.137] | [-0.073, 0.213] | 0.041 | 0.101 | 0.694 | n.s. | +0.070 (0.101) | a 0/3, b 0/3 | +0.06, +0.09, +0.07 |
| hcstock vs trace2skill | +0.127 | [0.042, 0.211] | [-0.050, 0.304] | 0.005 | 0.042 | 0.137 | superior | +0.127 (0.042) | a 0/3, b 0/3 | +0.11, +0.14, +0.12 |
| hcstock vs wikiskill | +0.075 | [0.006, 0.144] | [-0.071, 0.221] | 0.034 | 0.101 | 0.643 | n.s. | +0.075 (0.101) | a 0/3, b 0/3 | +0.06, +0.09, +0.07 |

**V3 B1 family P2: hc3 vs each competitor (Holm m = 8)** (Holm m = 8; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| hc3 vs evoskill | +0.015 | [-0.051, 0.081] | [-0.159, 0.189] | 0.639 | 1.000 | 1.000 | n.s. | +0.015 (1.000) | a 0/3, b 0/3 | +0.05, +0.03, -0.03 |
| hc3 vs gepa | -0.003 | [-0.041, 0.034] | [-0.136, 0.130] | 0.854 | 1.000 | 1.000 | n.s. | -0.003 (1.000) | a 0/3, b 0/3 | +0.03, +0.01, -0.05 |
| hc3 vs gepafull | -0.012 | [-0.068, 0.044] | [-0.170, 0.146] | 0.668 | 1.000 | 1.000 | n.s. | -0.012 (1.000) | a 0/3, b 0/3 | +0.03, +0.00, -0.06 |
| hc3 vs metaharness | +0.013 | [-0.038, 0.065] | [-0.139, 0.165] | 0.596 | 1.000 | 1.000 | n.s. | +0.013 (1.000) | a 0/3, b 0/3 | +0.05, +0.03, -0.03 |
| hc3 vs mipro | +0.032 | [-0.028, 0.091] | [-0.132, 0.196] | 0.281 | 1.000 | 1.000 | n.s. | +0.032 (1.000) | a 0/3, b 0/3 | +0.07, +0.04, -0.02 |
| hc3 vs skillopt | -0.010 | [-0.052, 0.032] | [-0.149, 0.129] | 0.627 | 1.000 | 1.000 | n.s. | -0.010 (1.000) | a 0/3, b 0/3 | +0.03, +0.00, -0.06 |
| hc3 vs trace2skill | +0.047 | [-0.010, 0.103] | [-0.112, 0.205] | 0.099 | 0.788 | 1.000 | n.s. | +0.047 (0.788) | a 0/3, b 0/3 | +0.08, +0.06, -0.00 |
| hc3 vs wikiskill | -0.005 | [-0.065, 0.055] | [-0.169, 0.159] | 0.863 | 1.000 | 1.000 | n.s. | -0.005 (1.000) | a 0/3, b 0/3 | +0.03, +0.01, -0.05 |

**V3 B1 family P2: ao22 vs each competitor (Holm m = 8)** (Holm m = 8; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| ao22 vs evoskill | +0.058 | [-0.002, 0.119] | [-0.135, 0.251] | 0.059 | 0.235 | 0.881 | n.s. | +0.058 (0.235) | a 0/3, b 0/3 | +0.13, +0.02, +0.03 |
| ao22 vs gepa | +0.040 | [0.002, 0.078] | [-0.127, 0.207] | 0.040 | 0.231 | 0.694 | n.s. | +0.040 (0.231) | a 0/3, b 0/3 | +0.11, +0.00, +0.01 |
| ao22 vs gepafull | +0.032 | [-0.025, 0.088] | [-0.155, 0.219] | 0.253 | 0.417 | 1.000 | n.s. | +0.032 (0.417) | a 0/3, b 0/3 | +0.10, -0.00, +0.00 |
| ao22 vs metaharness | +0.057 | [0.003, 0.110] | [-0.127, 0.240] | 0.039 | 0.231 | 0.694 | n.s. | +0.057 (0.231) | a 0/3, b 0/3 | +0.13, +0.02, +0.03 |
| ao22 vs mipro | +0.075 | [0.010, 0.140] | [-0.123, 0.273] | 0.026 | 0.179 | 0.537 | n.s. | +0.075 (0.179) | a 0/3, b 0/3 | +0.14, +0.04, +0.04 |
| ao22 vs skillopt | +0.033 | [-0.012, 0.079] | [-0.141, 0.207] | 0.140 | 0.417 | 1.000 | n.s. | +0.033 (0.417) | a 0/3, b 0/3 | +0.10, -0.00, +0.00 |
| ao22 vs trace2skill | +0.090 | [0.034, 0.146] | [-0.097, 0.277] | 0.003 | 0.027 | 0.093 | superior | +0.090 (0.027) | a 0/3, b 0/3 | +0.16, +0.05, +0.06 |
| ao22 vs wikiskill | +0.038 | [-0.014, 0.090] | [-0.143, 0.220] | 0.139 | 0.417 | 1.000 | n.s. | +0.038 (0.417) | a 0/3, b 0/3 | +0.11, +0.00, +0.01 |

Infrastructure and missing cells (per_arm_report.json of THIS window; counts only; key prefix is the scoring mode):

| mode\|arm (mode B = matched-checkpoint artifacts; it is NOT the suite letter) | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| TOTAL | 7200 | 7200 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| ao22 | 600 | 75 | 63 | 119445 | 12.4 |
| evoskill | 600 | 71 | 59 | 122423 | 11.7 |
| gepa | 600 | 70 | 58 | 117771 | 12.2 |
| gepafull | 600 | 74 | 60 | 140940 | 12.3 |
| hc3 | 600 | 72 | 60 | 113638 | 12.1 |
| hcstock | 600 | 70 | 57 | 166177 | 11.1 |
| metaharness | 600 | 70 | 58 | 107320 | 11.9 |
| mipro | 600 | 66 | 53 | 99314 | 11.7 |
| seed | 400 | 60 | 49 | 56971 | 10.7 |
| seed-check | 200 | 60 | 48 | 60228 | 11.0 |
| skillopt | 600 | 73 | 60 | 137811 | 12.1 |
| trace2skill | 600 | 81 | 66 | 127770 | 12.9 |
| wikiskill | 600 | 69 | 57 | 92100 | 11.8 |

Search cost (optimizer = Sonnet 5.5 at the proxy list price of protocol/pricing.json, from the run's cost_summary.json; blank = no cost_summary.json in the run dir; search rollouts = counted rollouts of the B* manifest for v1 windows, and for v2 windows the run's logs/rollout_counter.json total on A, or state.json metric_calls on tau, which includes the host-side finalize rollouts and is NOT the counted-rollout definition):

| arm | seed | optimizer USD (proxy) | optimizer non-cache-read tokens | optimizer calls | search rollouts | source |
|---|---|---|---|---|---|---|
| ao22 | 0 | 39.44 | 13811497 | 3150 | 2960 | run_summary.json (usd_total 112.725, wall_s 27881) |
| ao22 | 1 | 44.99 | 15626903 | 3251 | 2840 | run_summary.json (usd_total 128.9855, wall_s 28664) |
| ao22 | 2 | 47.41 | 16464396 | 3617 | 2860 | run_summary.json (usd_total 140.0098, wall_s 31744) |
| evoskill | 0 |  |  |  | 2850 |  |
| evoskill | 1 |  |  |  | 2850 |  |
| evoskill | 2 |  |  |  | 2910 |  |
| gepa | 0 | 7.10 |  |  | 2970 | run_summary.json (usd_total None, wall_s 26184.6) |
| gepa | 1 | 5.15 |  |  | 2910 | run_summary.json (usd_total None, wall_s 20997.4) |
| gepa | 2 | 6.38 |  |  | 2865 | run_summary.json (usd_total None, wall_s 21679.4) |
| gepafull | 0 | 9.28 |  |  | 2880 | run_summary.json (usd_total None, wall_s 24204.7) |
| gepafull | 1 | 6.31 |  |  | 2835 | run_summary.json (usd_total None, wall_s 22142.7) |
| gepafull | 2 | 8.11 |  |  | 2970 | run_summary.json (usd_total None, wall_s 24304.7) |
| harnesslens | 0 |  |  |  | 1142 |  |
| harnesslens | 1 |  |  |  | 1021 |  |
| harnesslens | 2 |  |  |  | 213 |  |
| harnesslens_archive_premature_end | 0 |  |  |  | 212 |  |
| harnesslens_archive_premature_end | 1 |  |  |  | 150 |  |
| harnesslens_archive_premature_end | 2 |  |  |  | 213 |  |
| hc3 | 0 | 6.60 | 2759708 | 573 | 1980 | run_summary.json (usd_total 41.8169, wall_s 36735) |
| hc3 | 1 | 5.45 | 2421587 | 492 | 2160 | run_summary.json (usd_total 44.5713, wall_s 41260) |
| hc3 | 2 | 6.51 | 2744867 | 572 | 2000 | run_summary.json (usd_total 41.1406, wall_s 37169) |
| hcstock | 0 | 9.11 | 3116954 | 727 | 3000 | run_summary.json (usd_total 67.5921, wall_s 25610) |
| hcstock | 1 | 11.13 | 4040730 | 819 | 3000 | run_summary.json (usd_total 75.2986, wall_s 30752) |
| hcstock | 2 | 12.71 | 4339313 | 954 | 3000 | run_summary.json (usd_total 77.7293, wall_s 32067) |
| metaharness | 0 | 4.90 |  |  | 2950 | run_summary.json (usd_total None, wall_s None) |
| metaharness | 1 | 5.89 |  |  | 2950 | run_summary.json (usd_total None, wall_s None) |
| metaharness | 2 | 5.65 |  |  | 2950 | run_summary.json (usd_total None, wall_s None) |
| mipro | 0 |  |  |  | 2865 |  |
| mipro | 1 |  |  |  | 2870 |  |
| mipro | 2 |  |  |  | 2880 |  |
| skillopt | 0 |  |  |  | 2950 |  |
| skillopt | 1 |  |  |  | 2950 |  |
| skillopt | 2 |  |  |  | 2950 |  |
| trace2skill | 0 |  |  |  |  |  |
| trace2skill | 1 |  |  |  |  |  |
| trace2skill | 2 |  |  |  |  |  |
| wikiskill | 0 |  |  | 191 | 3000 |  |
| wikiskill | 1 |  |  | 172 | 2900 |  |
| wikiskill | 2 |  |  | 175 | 2900 |  |

