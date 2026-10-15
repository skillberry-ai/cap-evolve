# Window V3B1/traineval: per-arm tables (released under the V3 B1 freeze declaration, amendment 12 erratum 8)

Task set: 30 tasks, 30 families (cluster = family; split filter ('train',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 5 | 0.540 | 0.540 | [0.405, 0.675] | - | - | 0 | 0.540 |
| ao22 | 3 | 5 | 0.713 | 0.713 | [0.594, 0.833] | s0:0.733, s1:0.720, s2:0.687 | 0/3 | 0 | 0.713 |
| evoskill | 3 | 5 | 0.727 | 0.727 | [0.611, 0.842] | s0:0.747, s1:0.700, s2:0.733 | 0/3 | 0 | 0.727 |
| gepa | 3 | 5 | 0.729 | 0.729 | [0.620, 0.838] | s0:0.707, s1:0.780, s2:0.700 | 0/3 | 0 | 0.729 |
| gepafull | 3 | 5 | 0.722 | 0.722 | [0.615, 0.830] | s0:0.780, s1:0.673, s2:0.713 | 0/3 | 0 | 0.722 |
| hc3 | 3 | 5 | 0.718 | 0.718 | [0.586, 0.849] | s0:0.713, s1:0.753, s2:0.687 | 0/3 | 0 | 0.718 |
| hcstock | 3 | 5 | 0.836 | 0.836 | [0.762, 0.909] | s0:0.833, s1:0.820, s2:0.853 | 0/3 | 0 | 0.836 |
| metaharness | 3 | 5 | 0.667 | 0.667 | [0.539, 0.794] | s0:0.700, s1:0.647, s2:0.653 | 0/3 | 0 | 0.667 |
| mipro | 3 | 5 | 0.607 | 0.607 | [0.465, 0.748] | s0:0.587, s1:0.620, s2:0.613 | 0/3 | 0 | 0.607 |
| skillopt | 3 | 5 | 0.722 | 0.722 | [0.601, 0.843] | s0:0.740, s1:0.747, s2:0.680 | 0/3 | 0 | 0.722 |
| trace2skill | 3 | 5 | 0.702 | 0.702 | [0.594, 0.811] | s0:0.660, s1:0.720, s2:0.727 | 0/3 | 0 | 0.702 |
| wikiskill | 3 | 5 | 0.673 | 0.673 | [0.539, 0.808] | s0:0.667, s1:0.673, s2:0.680 | 0/3 | 0 | 0.673 |

**Per-framework train-30 re-evaluation (descriptive, k = 5) mean (T = 30; mean of the 3 per-seed means; SE = SD of the 3 per-seed means / sqrt(3), n = 3 search seeds; per-seed means as measured)**

| framework | mean | SE across seeds | per-seed means | 95% CI of mean (artifact-level, CR1) |
|---|---|---|---|---|
| seed (n = 5 trials/task) | 0.540 | - | - | [0.405, 0.675] |
| ao22 | 0.713 | 0.014 | 0.733, 0.720, 0.687 | [0.594, 0.833] |
| evoskill | 0.727 | 0.014 | 0.747, 0.700, 0.733 | [0.611, 0.842] |
| gepa | 0.729 | 0.026 | 0.707, 0.780, 0.700 | [0.620, 0.838] |
| gepafull | 0.722 | 0.031 | 0.780, 0.673, 0.713 | [0.615, 0.830] |
| hc3 | 0.718 | 0.019 | 0.713, 0.753, 0.687 | [0.586, 0.849] |
| hcstock | 0.836 | 0.010 | 0.833, 0.820, 0.853 | [0.762, 0.909] |
| metaharness | 0.667 | 0.017 | 0.700, 0.647, 0.653 | [0.539, 0.794] |
| mipro | 0.607 | 0.010 | 0.587, 0.620, 0.613 | [0.465, 0.748] |
| skillopt | 0.722 | 0.021 | 0.740, 0.747, 0.680 | [0.601, 0.843] |
| trace2skill | 0.702 | 0.021 | 0.660, 0.720, 0.727 | [0.594, 0.811] |
| wikiskill | 0.673 | 0.004 | 0.667, 0.673, 0.680 | [0.539, 0.808] |

**Train re-evaluation vs test, per framework (descriptive; delta = framework minus the seed scored in the same block; train = the 30 official train ids re-scored at k = 5 with fresh seeds, test = the 20 official test ids at k = 10; 'train minus test' = the selection-to-final gap in the sense of 5P-2, with the train re-score in place of the search-time selection split; SE across the 3 seeds)**

| framework | train delta vs seed | SE | test delta vs seed | SE | train minus test |
|---|---|---|---|---|---|
| ao22 | +0.173 | 0.014 | +0.094 | 0.034 | +0.079 |
| evoskill | +0.187 | 0.014 | +0.036 | 0.009 | +0.151 |
| gepa | +0.189 | 0.026 | +0.054 | 0.030 | +0.135 |
| gepafull | +0.182 | 0.031 | +0.062 | 0.019 | +0.120 |
| hc3 | +0.178 | 0.019 | +0.051 | 0.025 | +0.127 |
| hcstock | +0.296 | 0.010 | +0.131 | 0.009 | +0.165 |
| metaharness | +0.127 | 0.017 | +0.037 | 0.000 | +0.089 |
| mipro | +0.067 | 0.010 | +0.019 | 0.016 | +0.048 |
| skillopt | +0.182 | 0.021 | +0.061 | 0.032 | +0.121 |
| trace2skill | +0.162 | 0.021 | +0.004 | 0.013 | +0.158 |
| wikiskill | +0.133 | 0.004 | +0.056 | 0.012 | +0.078 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: -0.026 (SE 0.051, n=47); 1: +0.070 (SE 0.055, n=40); 2: -0.015 (SE 0.048, n=53); 3: -0.080 (SE 0.111, n=10). Range 0.150, SE of difference 0.101, drift flag (>2 SE): False.

Infrastructure and missing cells (per_arm_report.json of THIS window; counts only; key prefix is the scoring mode):

| mode\|arm (mode B = matched-checkpoint artifacts; it is NOT the suite letter) | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| TOTAL | 5100 | 5100 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| ao22 | 450 | 64 | 53 | 102783 | 10.9 |
| evoskill | 450 | 71 | 61 | 125832 | 11.8 |
| gepa | 450 | 58 | 52 | 97722 | 10.6 |
| gepafull | 450 | 65 | 59 | 124492 | 11.3 |
| hc3 | 450 | 66 | 59 | 105637 | 11.6 |
| hcstock | 450 | 59 | 50 | 139043 | 9.4 |
| metaharness | 450 | 66 | 56 | 108018 | 11.9 |
| mipro | 450 | 61 | 55 | 94251 | 11.3 |
| seed | 150 | 55 | 48 | 55845 | 10.2 |
| skillopt | 450 | 72 | 61 | 136728 | 11.9 |
| trace2skill | 450 | 71 | 63 | 115134 | 11.7 |
| wikiskill | 450 | 64 | 58 | 85463 | 11.1 |

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

