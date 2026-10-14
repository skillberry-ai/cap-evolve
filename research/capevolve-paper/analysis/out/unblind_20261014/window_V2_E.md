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

Infrastructure and missing cells (per_arm_report.json of THIS window; counts only; key prefix is the scoring mode):

| mode\|arm (mode B = matched-checkpoint artifacts; it is NOT the suite letter) | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| B|gepa | 300 | 300 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|hc2 | 200 | 196 | 25 | 4 | 0 | 0 | 0 | 0 | 0 |
| TOTAL | 800 | 796 | 28 | 4 | 0 | 0 | 0 | 0 | 0 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| gepa | 300 | 264 | 226 | 113338 | 14.6 |
| hc2 | 200 | 237 | 198 | 60747 | 10.8 |
| seed | 200 | 204 | 181 | 64415 | 12.2 |
| seed-check | 100 | 213 | 178 | 66095 | 12.4 |

Search cost (optimizer = Sonnet 5.5 at the proxy list price of protocol/pricing.json, from the run's cost_summary.json; blank = no cost_summary.json in the run dir; search rollouts = counted rollouts of the B* manifest for v1 windows, and for v2 windows the run's state.json metric_calls, which on tau includes the host-side finalize rollouts and is NOT the counted-rollout definition):

| arm | seed | optimizer USD (proxy) | optimizer non-cache-read tokens | optimizer calls | search rollouts | source |
|---|---|---|---|---|---|---|
| ao2 | 0 | 11.28 | 2233206 | 692 | 164 | cost_summary.json |
| ao2 | 1 | 2.20 | 465362 | 107 | 164 | cost_summary.json |
| ao2 | 2 | 2.57 | 518399 | 119 | 164 | cost_summary.json |
| ao21 | 0 | 3.49 | 726817 | 161 | 296 | cost_summary.json |
| ao21 | 1 | 3.89 | 765022 | 186 | 294 | cost_summary.json |
| ao21 | 2 | 2.91 | 534913 | 158 | 296 | cost_summary.json |
| hc2 | 0 | 5.84 | 1058307 | 236 | 288 | cost_summary.json |
| hc2 | 1 | 5.29 | 1008602 | 218 | 236 | cost_summary.json |
| hc2 | 2 | 1.77 | 332806 | 67 | 204 | cost_summary.json |

