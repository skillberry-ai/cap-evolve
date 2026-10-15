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

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| hc vs seed | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | - | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 0/1 | +0.00, +0.00, +0.00 |
| hc vs oneshot | +0.075 | [-0.018, 0.168] | [-0.123, 0.273] | 0.112 | 0.672 | - | not testable (inert) | +0.065 (0.974) | a 3/3, b 0/3 | +0.08, +0.08, +0.08 |
| hc vs gepa | -0.028 | [-0.115, 0.060] | [-0.214, 0.159] | 0.525 | 1.000 | - | not testable (inert) | -0.028 (1.000) | a 3/3, b 0/3 | -0.03, -0.03, -0.03 |
| hc vs harnesslens | +0.203 | [0.108, 0.297] | [0.002, 0.404] | <0.001 | <0.001 | - | superior | +0.203 (<0.001) | a 3/3, b 0/3 | +0.20, +0.20, +0.20 |
| ao (dagger) vs seed | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | - | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 0/1 | +0.00, +0.00, +0.00 |
| ao (dagger) vs oneshot | +0.075 | [-0.018, 0.168] | [-0.123, 0.273] | 0.112 | 0.672 | - | not testable (inert) | +0.065 (0.974) | a 3/3, b 0/3 | +0.08, +0.08, +0.08 |
| ao (dagger) vs gepa | -0.028 | [-0.115, 0.060] | [-0.214, 0.159] | 0.525 | 1.000 | - | not testable (inert) | -0.028 (1.000) | a 3/3, b 0/3 | -0.03, -0.03, -0.03 |
| ao (dagger) vs harnesslens | +0.203 | [0.108, 0.297] | [0.002, 0.404] | <0.001 | <0.001 | - | superior | +0.203 (<0.001) | a 3/3, b 0/3 | +0.20, +0.20, +0.20 |

**Suite B primary 5A WITHOUT dagger arms ['ao'] (Holm rescaled)** (Holm m = 4; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| hc vs seed | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | - | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 0/1 | +0.00, +0.00, +0.00 |
| hc vs oneshot | +0.075 | [-0.018, 0.168] | [-0.123, 0.273] | 0.112 | 0.336 | - | not testable (inert) | +0.065 (0.487) | a 3/3, b 0/3 | +0.08, +0.08, +0.08 |
| hc vs gepa | -0.028 | [-0.115, 0.060] | [-0.214, 0.159] | 0.525 | 1.000 | - | not testable (inert) | -0.028 (1.000) | a 3/3, b 0/3 | -0.03, -0.03, -0.03 |
| hc vs harnesslens | +0.203 | [0.108, 0.297] | [0.002, 0.404] | <0.001 | <0.001 | - | superior | +0.203 (<0.001) | a 3/3, b 0/3 | +0.20, +0.20, +0.20 |

**Suite B secondary 5B(i) vs seed** (Holm m = 3; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| gepa vs seed | +0.028 | [-0.060, 0.115] | [-0.186, 0.241] | 0.525 | 1.000 | - | inconclusive | +0.028 (1.000) | a 0/3, b 0/1 | +0.03, -0.02, +0.07 |
| harnesslens vs seed | -0.203 | [-0.297, -0.108] | [-0.506, 0.100] | <0.001 | <0.001 | - | inferior | -0.203 (<0.001) | a 0/3, b 0/1 | -0.31, -0.15, -0.15 |
| hcstock vs seed | +0.019 | [-0.052, 0.090] | [-0.140, 0.179] | 0.583 | 1.000 | - | equivalent within +-0.10 | +0.019 (1.000) | a 1/3, b 0/1 | +0.02, +0.00, +0.04 |

**Suite B secondary 5B(ii) CapEvolve vs others** (Holm m = 1; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| hc vs ao (dagger) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 1.000 | 1.000 | - | both returned the seed (delta 0 by construction) | +0.000 (1.000) | a 3/3, b 3/3 | +0.00, +0.00, +0.00 |

**Suite B S-stock (9G; hcstock = E12B stock-gate arm if present)** (Holm m = 3; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| hcstock vs seed | +0.019 | [-0.052, 0.090] | [-0.140, 0.179] | 0.583 | 1.000 | - | equivalent within +-0.10 | +0.019 (1.000) | a 1/3, b 0/1 | +0.02, +0.00, +0.04 |
| hcstock vs gepa | -0.008 | [-0.067, 0.050] | [-0.144, 0.127] | 0.776 | 1.000 | - | equivalent within +-0.10 | -0.008 (1.000) | a 1/3, b 0/3 | -0.01, -0.03, +0.01 |
| hcstock vs harnesslens | +0.222 | [0.143, 0.301] | [0.046, 0.399] | <0.001 | <0.001 | - | superior | +0.222 (<0.001) | a 1/3, b 0/3 | +0.22, +0.20, +0.24 |

Infrastructure and missing cells (per_arm_report.json of THIS window; counts only; key prefix is the scoring mode):

| mode\|arm (mode B = matched-checkpoint artifacts; it is NOT the suite letter) | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| B|ao | 360 | 360 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|harnesslens | 360 | 360 | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|hc | 360 | 360 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|hcstock | 360 | 360 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|hl-v0 | 120 | 120 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|oneshot | 360 | 341 | 100 | 19 | 0 | 0 | 0 | 0 | 0 |
| B|seed | 120 | 120 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|seed-check | 120 | 120 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| TOTAL | 2520 | 2501 | 122 | 19 | 0 | 0 | 0 | 0 | 0 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| ao | 360 | 203 | 167 | 73576 | 12.4 |
| gepa | 360 | 210 | 189 | 107023 | 12.9 |
| harnesslens | 360 | 565 | 460 | n/a | 12.2 |
| hc | 360 | 196 | 178 | 72031 | 12.4 |
| hcstock | 360 | 204 | 174 | 75952 | 12.1 |
| hl-v0 | 120 | 536 | 442 | n/a | 11.6 |
| oneshot | 360 | 248 | 178 | 60101 | 9.4 |
| seed | 120 | 196 | 165 | 71976 | 12.4 |
| seed-check | 120 | 188 | 163 | 73572 | 12.6 |

Search cost (optimizer = Sonnet 5.5 at the proxy list price of protocol/pricing.json, from the run's cost_summary.json; blank = no cost_summary.json in the run dir; search rollouts = counted rollouts of the B* manifest for v1 windows, and for v2 windows the run's logs/rollout_counter.json total on A, or state.json metric_calls on tau, which includes the host-side finalize rollouts and is NOT the counted-rollout definition):

| arm | seed | optimizer USD (proxy) | optimizer non-cache-read tokens | optimizer calls | search rollouts | source |
|---|---|---|---|---|---|---|
| ao | 0 | 5.80 | 1145701 | 165 | 148 | cost_summary.json |
| ao | 1 | 5.69 | 976598 | 172 | 147 | cost_summary.json |
| ao | 2 | 11.53 | 2667353 | 234 | 882 | cost_summary.json |
| gepa | 0 | 3.67 | 998171 | 36 | 613 | collect_metrics gateway ledger |
| gepa | 1 | 3.60 | 990402 | 38 | 603 | collect_metrics gateway ledger |
| gepa | 2 | 3.06 | 884196 | 36 | 607 | collect_metrics gateway ledger |
| harnesslens | 0 | 19.26 | 8899307 | 157 | 176 | collect_metrics gateway ledger |
| harnesslens | 1 | 14.64 | 6844643 | 126 | 173 | collect_metrics gateway ledger |
| harnesslens | 2 | 18.40 | 8494279 | 134 | 163 | collect_metrics gateway ledger |
| hc | 0 | 2.01 | 348306 | 66 | 637 | collect_metrics gateway ledger |
| hc | 1 | 4.19 | 808424 | 151 | 539 | cost_summary.json |
| hc | 2 | 1.46 | 248637 | 57 | 637 | collect_metrics gateway ledger |
| hcstock | 0 |  |  |  | 441 |  |
| hcstock | 1 | 2.83 | 549811 | 107 | 539 | cost_summary.json |
| hcstock | 2 |  |  |  | 490 |  |
| hlext | 0 |  |  |  | 284 |  |
| hlext | 1 |  |  |  |  |  |
| hlext | 2 |  |  |  |  |  |
| oneshot | 0 | 1.23 | 210157 | 35 | 123 | cost_summary.json |
| oneshot | 1 | 1.61 | 228607 | 49 | 148 | cost_summary.json |
| oneshot | 2 | 0.95 | 165091 | 31 | 123 | cost_summary.json |

