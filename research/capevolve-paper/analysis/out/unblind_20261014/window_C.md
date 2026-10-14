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

Infrastructure and missing cells (per_arm_report.json; counts only):

| key | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| B|hc | 180 | 180 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|hcstock | 180 | 180 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|oneshot | 180 | 178 | 14 | 2 | 0 | 0 | 0 | 0 | 0 |
| TOTAL | 1020 | 1018 | 17 | 2 | 0 | 0 | 0 | 0 | 0 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| ao | 180 | 251 | 216 | 77454 | 13.2 |
| gepa | 180 | 336 | 248 | 128650 | 13.6 |
| hc | 180 | 305 | 222 | 83033 | 13.2 |
| hcstock | 180 | 284 | 202 | 80285 | 12.5 |
| oneshot | 180 | 287 | 208 | 79102 | 11.5 |
| seed | 60 | 236 | 176 | 64814 | 11.9 |
| seed-check | 60 | 249 | 180 | 76243 | 13.0 |

Search cost (optimizer = Sonnet 5.5 at the proxy list price of protocol/pricing.json, from the run's cost_summary.json; blank = no cost_summary.json in the run dir; search rollouts = counted rollouts of the B* manifest for v1 windows, and for v2 windows the run's state.json metric_calls, which on tau includes the host-side finalize rollouts and is NOT the counted-rollout definition):

| arm | seed | optimizer USD (proxy) | optimizer non-cache-read tokens | optimizer calls | search rollouts | source |
|---|---|---|---|---|---|---|
| ao | 0 | 2.75 | 554012 | 71 | 100 | cost_summary.json |
| ao | 1 | 2.44 | 564650 | 54 | 100 | cost_summary.json |
| ao | 2 | 1.97 | 523420 | 44 | 61 | cost_summary.json |
| gepa | 0 | 5.01 | 1192911 | 41 | 476 | collect_metrics gateway ledger |
| gepa | 1 | 3.99 | 1012954 | 34 | 388 | collect_metrics gateway ledger |
| gepa | 2 | 4.87 | 1292215 | 46 | 474 | collect_metrics gateway ledger |
| hc | 0 | 3.72 | 793836 | 118 | 460 | cost_summary.json |
| hc | 1 | 2.64 | 589979 | 96 | 580 | cost_summary.json |
| hc | 2 | 3.13 | 657664 | 112 | 340 | cost_summary.json |
| hcstock | 0 | 3.14 | 663977 | 103 | 220 | cost_summary.json |
| hcstock | 1 | 3.92 | 734093 | 134 | 220 | cost_summary.json |
| hcstock | 2 | 3.58 | 749017 | 121 | 220 | cost_summary.json |
| oneshot | 0 | 0.60 | 93027 | 20 | 60 | cost_summary.json |
| oneshot | 1 | 0.71 | 107372 | 21 | 50 | cost_summary.json |
| oneshot | 2 | 0.81 | 125833 | 25 | 50 | cost_summary.json |

