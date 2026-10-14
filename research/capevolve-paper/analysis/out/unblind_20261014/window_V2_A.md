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

Infrastructure and missing cells (per_arm_report.json of THIS window; counts only; key prefix is the scoring mode):

| mode\|arm (mode B = matched-checkpoint artifacts; it is NOT the suite letter) | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| TOTAL | 840 | 840 | 0 | 0 | 0 | 0 | 0 | 35 | 63 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| ao2 | 210 | 451 | 130 | 138204 | 15.4 |
| gepa | 210 | 295 | 130 | 89253 | 9.1 |
| hc2 | 210 | 538 | 386 | 227294 | 17.1 |
| seed | 140 | 433 | 167 | 133002 | 14.7 |
| seed-check | 70 | 446 | 162 | 139472 | 15.4 |

Search cost (optimizer = Sonnet 5.5 at the proxy list price of protocol/pricing.json, from the run's cost_summary.json; blank = no cost_summary.json in the run dir; search rollouts = counted rollouts of the B* manifest for v1 windows, and for v2 windows the run's logs/rollout_counter.json total on A, or state.json metric_calls on tau, which includes the host-side finalize rollouts and is NOT the counted-rollout definition):

| arm | seed | optimizer USD (proxy) | optimizer non-cache-read tokens | optimizer calls | search rollouts | source |
|---|---|---|---|---|---|---|
| ao2 | 0 | 3.05 | 618033 | 173 | 362 | gateway ledger by tag (lower bound: some calls unpriced) |
| ao2 | 1 | 2.77 | 589603 | 145 | 362 | gateway ledger by tag (lower bound: some calls unpriced) |
| ao2 | 2 | 2.22 | 461861 | 126 | 362 | gateway ledger by tag (lower bound: some calls unpriced) |
| ao21 | 0 | 1.83 | 412500 | 98 | 362 | gateway ledger by tag (lower bound: some calls unpriced) |
| ao21 | 1 | 2.39 | 498646 | 133 | 340 | gateway ledger by tag (lower bound: some calls unpriced) |
| ao21 | 2 | 2.77 | 593876 | 153 | 404 | gateway ledger by tag (lower bound: some calls unpriced) |
| hc2 | 0 | 0.99 | 240119 | 32 | 362 | gateway ledger by tag (lower bound: some calls unpriced) |
| hc2 | 1 | 0.81 | 207282 | 28 | 362 | gateway ledger by tag (lower bound: some calls unpriced) |
| hc2 | 2 | 2.05 | 480560 | 76 | 600 | gateway ledger by tag (lower bound: some calls unpriced) |

