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

Infrastructure and missing cells (per_arm_report.json; counts only):

| key | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| B|gepa | 600 | 600 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|seed | 400 | 400 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|seed-check | 200 | 200 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| TOTAL | 1200 | 1200 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| gepa | 600 | 171 | 156 | 92266 | 13.4 |
| seed | 400 | 174 | 158 | 70456 | 13.0 |
| seed-check | 200 | 177 | 162 | 70959 | 13.0 |

Search cost (optimizer = Sonnet 5.5 at the proxy list price of protocol/pricing.json, from the run's cost_summary.json; blank = no cost_summary.json in the run dir; search rollouts = counted rollouts of the B* manifest for v1 windows, and for v2 windows the run's state.json metric_calls, which on tau includes the host-side finalize rollouts and is NOT the counted-rollout definition):

| arm | seed | optimizer USD (proxy) | optimizer non-cache-read tokens | optimizer calls | search rollouts | source |
|---|---|---|---|---|---|---|
| ao2 | 0 | 2.02 | 406176 | 103 | 324 | cost_summary.json |
| ao2 | 1 | 2.54 | 531759 | 121 | 323 | cost_summary.json |
| ao2 | 2 | 2.34 | 467065 | 113 | 323 | cost_summary.json |
| ao21 | 0 | 3.06 | 594499 | 159 | 531 | cost_summary.json |
| ao21 | 1 | 3.12 | 585169 | 166 | 514 | cost_summary.json |
| ao21 | 2 | 3.26 | 612669 | 167 | 531 | cost_summary.json |
| hc2 | 0 | 2.37 | 435232 | 103 | 498 | cost_summary.json |
| hc2 | 1 | 2.14 | 388980 | 93 | 530 | cost_summary.json |
| hc2 | 2 | 2.69 | 474023 | 110 | 530 | cost_summary.json |

