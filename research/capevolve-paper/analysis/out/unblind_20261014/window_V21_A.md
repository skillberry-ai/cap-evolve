# Window V21/A: per-arm tables (user-directed early unblinding, erratum 36)

Task set: 70 tasks, 70 families (cluster = family; split filter ('',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 2 | 0.386 | 0.386 | [0.274, 0.497] | - | - | 0 | 0.386 |
| seed-check | 1 | 1 | 0.414 | 0.414 | [0.296, 0.533] | - | - | 0 | 0.414 |
| ao21 | 3 | 1 | 0.400 | 0.400 | [0.294, 0.506] | s0:0.429, s1:0.357, s2:0.414 | 0/3 | 0 | 0.400 |
| gepa | 3 | 1 | 0.519 | 0.519 | [0.407, 0.631] | s0:0.529, s1:0.500, s2:0.529 | 0/3 | 0 | 0.519 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: -0.065 (SE 0.031, n=23); 1: +0.000 (SE 0.019, n=60); 2: +0.023 (SE 0.022, n=43); 3: +0.036 (SE 0.039, n=14). Range 0.101, SE of difference 0.041, drift flag (>2 SE): True.

Seed-check minus seed (empirical null of window noise, 9D(ii)): +0.029, 95% CI [-0.050, 0.107], p 0.469.

**5I block-adjusted headline (seed drift > 2 SE): delta vs seed after subtracting the seed's task-demeaned block effects from every trial (block effects {0: -0.065, 1: 0.0, 2: 0.023, 3: 0.036})**

| arm | block-adjusted delta vs seed | 95% CI (artifact, CR1) | per-seed |
|---|---|---|---|
| ao21 | +0.015 | [-0.057, 0.087] | +0.04, -0.02, +0.02 |
| gepa | +0.133 | [0.051, 0.214] | +0.14, +0.11, +0.14 |

**v2.1-AO2 (erratum 43 champions)**: the P2-accepted candidates whose commit was voided by the pooled-mode defect; secondary version (11D). Literal-final-state reading beside it: all three champions = the seed, delta 0 by construction (no scoring needed).

**v2.1 window Suite A: AO-2 v2.1 (erratum 43; secondary under 11D, own Holm m = 2)** (Holm m = 2; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|
| ao21 vs seed | +0.014 | [-0.058, 0.087] | [-0.168, 0.197] | 0.695 | 0.695 | n.s. | +0.014 (0.695) | a 0/3, b 0/1 | +0.04, -0.03, +0.03 |
| ao21 vs gepa | -0.119 | [-0.181, -0.057] | [-0.283, 0.044] | <0.001 | <0.001 | inferior | -0.119 (<0.001) | a 0/3, b 0/3 | -0.09, -0.16, -0.10 |

Scored champion ao21 s0 alone (descriptive; the family row above averages it with the seeds that returned the seed): vs in-window seed: +0.043 [-0.040, 0.126], p 0.307; vs seed-check (same artifact, n as the arms): +0.014 [-0.089, 0.118], p 0.784.
Scored champion ao21 s1 alone (descriptive; the family row above averages it with the seeds that returned the seed): vs in-window seed: -0.029 [-0.112, 0.055], p 0.497; vs seed-check (same artifact, n as the arms): -0.057 [-0.156, 0.041], p 0.251.
Scored champion ao21 s2 alone (descriptive; the family row above averages it with the seeds that returned the seed): vs in-window seed: +0.029 [-0.069, 0.126], p 0.559; vs seed-check (same artifact, n as the arms): +0.000 [-0.115, 0.115], p 1.000.

Infrastructure and missing cells (per_arm_report.json of THIS window; counts only; key prefix is the scoring mode):

| mode\|arm (mode B = matched-checkpoint artifacts; it is NOT the suite letter) | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| TOTAL | 630 | 630 | 0 | 0 | 0 | 0 | 0 | 16 | 40 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| ao21 | 210 | 606 | 476 | 180883 | 17.4 |
| gepa | 210 | 328 | 112 | 91200 | 9.0 |
| seed | 140 | 436 | 163 | 125128 | 14.6 |
| seed-check | 70 | 407 | 136 | 128442 | 14.3 |

