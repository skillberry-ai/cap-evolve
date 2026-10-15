# Window V21/D: per-arm tables (user-directed early unblinding, erratum 36)

Task set: 40 tasks, 40 families (cluster = family; split filter ('test',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 10 | 0.590 | 0.590 | [0.476, 0.704] | - | - | 0 | 0.590 |
| seed-check | 1 | 5 | 0.635 | 0.635 | [0.532, 0.738] | - | - | 0 | 0.635 |
| ao21 | 3 | 5 | 0.610 | 0.597 | [0.491, 0.702] | s0:0.610, s1:inert(not rescored), s2:inert(not rescored) | 2/3 | 0 | 0.597 |
| gepa | 3 | 5 | 0.668 | 0.668 | [0.561, 0.776] | s0:0.710, s1:0.655, s2:0.640 | 0/3 | 0 | 0.668 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: -0.000 (SE 0.017, n=400). Range 0.000, SE of difference 0.024, drift flag (>2 SE): False.

Seed-check minus seed (empirical null of window noise, 9D(ii)): +0.045, 95% CI [-0.020, 0.110], p 0.168.

**v2.1-AO2 (erratum 43 champions)**: the P2-accepted candidates whose commit was voided by the pooled-mode defect; secondary version (11D). Literal-final-state reading beside it: all three champions = the seed, delta 0 by construction (no scoring needed).

**v2.1 window Suite D: AO-2 v2.1 (erratum 43; secondary under 11D, own Holm m = 2)** (Holm m = 2; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| ao21 vs seed | +0.007 | [-0.015, 0.028] | [-0.048, 0.061] | 0.539 | 0.539 | - | n.s. | +0.007 (0.539) | a 2/3, b 0/1 | +0.02, +0.00, +0.00 |
| ao21 vs gepa | -0.072 | [-0.138, -0.006] | [-0.215, 0.071] | 0.034 | 0.068 | - | n.s. | -0.072 (0.068) | a 2/3, b 0/3 | -0.06, -0.08, -0.08 |

Scored champion ao21 s0 alone (descriptive; the family row above averages it with the seeds that returned the seed): vs in-window seed: +0.020 [-0.045, 0.085], p 0.539; vs seed-check (same artifact, n as the arms): -0.025 [-0.101, 0.051], p 0.507.

Infrastructure and missing cells (per_arm_report.json of THIS window; counts only; key prefix is the scoring mode):

| mode\|arm (mode B = matched-checkpoint artifacts; it is NOT the suite letter) | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| B|ao21 | 200 | 200 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|gepa | 600 | 600 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|seed | 400 | 400 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| B|seed-check | 200 | 200 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| TOTAL | 1400 | 1400 | 11 | 0 | 0 | 0 | 0 | 0 | 0 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| ao21 | 200 | 166 | 150 | 87511 | 12.8 |
| gepa | 600 | 168 | 148 | 91896 | 13.3 |
| seed | 400 | 171 | 146 | 67495 | 12.6 |
| seed-check | 200 | 167 | 142 | 68148 | 12.8 |

