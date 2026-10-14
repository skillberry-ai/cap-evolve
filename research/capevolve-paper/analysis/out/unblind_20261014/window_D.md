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

Infrastructure and missing cells (per_arm_report.json; counts only):

| key | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| B|1s | 975 | 968 | 62 | 7 | 0 | 0 | 0 | 0 | 0 |
| B|1s-Tonly | 585 | 585 | 12 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|ctl | 975 | 964 | 104 | 11 | 0 | 0 | 0 | 0 | 0 |
| B|ctl-Ponly | 585 | 585 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|ctl-Tonly | 585 | 583 | 25 | 2 | 0 | 0 | 0 | 0 | 0 |
| B|gepa | 600 | 600 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|nohist | 975 | 972 | 58 | 3 | 0 | 0 | 0 | 0 | 0 |
| B|p | 975 | 975 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|pt | 975 | 969 | 65 | 6 | 0 | 0 | 0 | 0 | 0 |
| B|pt-Ponly | 585 | 585 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|pt-Tonly | 585 | 583 | 32 | 2 | 0 | 0 | 0 | 0 | 0 |
| B|rulep | 975 | 969 | 62 | 6 | 0 | 0 | 0 | 0 | 0 |
| B|rulep-Ponly | 585 | 585 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|rulep-Tonly | 585 | 585 | 28 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|seed | 650 | 650 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|seed-check | 325 | 325 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|t | 975 | 946 | 179 | 29 | 0 | 0 | 0 | 0 | 0 |
| TOTAL | 13080 | 13014 | 646 | 66 | 0 | 0 | 0 | 0 | 0 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| 1s | 600 | 291 | 237 | 75562 | 11.3 |
| 1s-Ponly | 360 | 251 | 228 | 78557 | 12.3 |
| 1s-Tonly | 360 | 321 | 264 | 70114 | 12.5 |
| ctl | 600 | 337 | 256 | 72843 | 11.6 |
| ctl-Ponly | 360 | 268 | 250 | 81840 | 13.2 |
| ctl-Tonly | 360 | 326 | 260 | 66397 | 12.1 |
| gepa | 600 | 278 | 256 | 93790 | 13.5 |
| nohist | 600 | 296 | 248 | 76364 | 12.0 |
| p | 600 | 251 | 236 | 81567 | 12.6 |
| pt | 600 | 304 | 252 | 73984 | 11.7 |
| pt-Ponly | 360 | 256 | 236 | 79322 | 12.7 |
| pt-Tonly | 360 | 341 | 262 | 64826 | 12.0 |
| rulep | 600 | 309 | 244 | 69898 | 11.4 |
| rulep-Ponly | 360 | 259 | 234 | 79103 | 12.8 |
| rulep-Tonly | 360 | 325 | 251 | 63660 | 11.9 |
| seed | 400 | 272 | 257 | 70367 | 13.1 |
| seed-check | 200 | 280 | 261 | 72656 | 13.3 |
| t | 600 | 333 | 260 | 56616 | 10.5 |

Search cost (optimizer = Sonnet 5.5 at the proxy list price of protocol/pricing.json, from the run's cost_summary.json; blank = no cost_summary.json in the run dir; search rollouts = counted rollouts of the B* manifest for v1 windows, and for v2 windows the run's state.json metric_calls, which on tau includes the host-side finalize rollouts and is NOT the counted-rollout definition):

| arm | seed | optimizer USD (proxy) | optimizer non-cache-read tokens | optimizer calls | search rollouts | source |
|---|---|---|---|---|---|---|
| 1s | 0 | 2.64 | 536548 | 99 | 589 | cost_summary.json |
| 1s | 1 | 3.81 | 623933 | 140 | 589 | cost_summary.json |
| 1s | 2 | 3.25 | 562813 | 128 | 589 | cost_summary.json |
| ctl | 0 | 0.68 | 109955 | 21 | 148 | cost_summary.json |
| ctl | 1 | 0.65 | 102028 | 20 | 148 | cost_summary.json |
| ctl | 2 | 0.69 | 113406 | 19 | 123 | cost_summary.json |
| gepa | 0 |  |  |  | 564 |  |
| gepa | 1 |  |  |  | 575 |  |
| gepa | 2 |  |  |  | 556 |  |
| nohist | 0 | 6.26 | 972179 | 207 | 589 | cost_summary.json |
| nohist | 1 | 5.76 | 938025 | 194 | 589 | cost_summary.json |
| nohist | 2 | 5.98 | 912829 | 209 | 589 | cost_summary.json |
| p | 0 | 2.52 | 527503 | 88 | 589 | cost_summary.json |
| p | 1 | 2.18 | 477875 | 75 | 589 | cost_summary.json |
| p | 2 | 2.27 | 499819 | 82 | 589 | cost_summary.json |
| pt | 0 | 3.69 | 652749 | 134 | 589 | cost_summary.json |
| pt | 1 | 3.27 | 592041 | 118 | 589 | cost_summary.json |
| pt | 2 | 3.26 | 664739 | 111 | 589 | cost_summary.json |
| rulep | 0 | 2.07 | 378120 | 79 | 687 | cost_summary.json |
| rulep | 1 | 1.34 | 194749 | 38 | 785 | cost_summary.json |
| rulep | 2 | 1.01 | 157107 | 37 | 785 | cost_summary.json |
| t | 0 | 3.76 | 623768 | 138 | 589 | cost_summary.json |
| t | 1 | 2.81 | 514943 | 103 | 589 | cost_summary.json |
| t | 2 | 2.55 | 471256 | 103 | 564 | cost_summary.json |

