# Window V3B1LATE/main: per-arm tables (released under the V3 B1 LATE freeze declaration, amendment 12 erratum 13)

Task set: 20 tasks, 20 families (cluster = family; split filter ('test',)). Primary basis infra_final = failure; sensitivity infra_final = missing. Mean (as measured) includes the physical re-score of inert artifacts; mean (inert -> seed) is the contrast basis.

| arm | seeds | trials/task | mean reward (as measured) | mean (inert -> seed) | 95% CI (CR1, artifact-level) | per-seed mean (as measured) | inert seeds | infra_final cells | mean, infra_final missing |
|---|---|---|---|---|---|---|---|---|---|
| seed | 1 | 20 | 0.485 | 0.485 | [0.323, 0.647] | - | - | 0 | 0.485 |
| seed-check | 1 | 10 | 0.495 | 0.495 | [0.314, 0.676] | - | - | 0 | 0.495 |
| ace | 3 | 10 | 0.518 | 0.518 | [0.349, 0.687] | s0:0.535, s1:0.470, s2:0.550 | 0/3 | 0 | 0.518 |
| ao22 | 3 | 10 | 0.530 | 0.530 | [0.370, 0.690] | s0:0.595, s1:0.495, s2:0.500 | 0/3 | 0 | 0.530 |
| hc3 | 3 | 10 | 0.540 | 0.540 | [0.359, 0.721] | s0:0.570, s1:0.520, s2:0.530 | 0/3 | 0 | 0.540 |
| hcstock | 3 | 10 | 0.620 | 0.620 | [0.440, 0.800] | s0:0.630, s1:0.620, s2:0.610 | 0/3 | 0 | 0.620 |

**Window-to-window noise check (descriptive; the same frozen artifacts scored in the main window and again here; difference = this window minus main window; task-paired CR1 on the per-task difference of seed-averaged scores; hl-v0 and ACE have no main-window cell). It is a measure of how much the same artifact moves between time blocks and enters no test.**

| cell | main window mean | this window mean | difference | 95% CI | per-seed difference |
|---|---|---|---|---|---|
| seed | 0.498 | 0.485 | -0.013 | [-0.069, 0.044] |  |
| seed-check | 0.480 | 0.495 | +0.015 | [-0.061, 0.091] |  |
| hcstock | 0.628 | 0.620 | -0.008 | [-0.052, 0.035] | +0.015, -0.025, -0.015 |
| hc3 | 0.548 | 0.540 | -0.008 | [-0.042, 0.025] | -0.015, -0.040, +0.030 |
| ao22 | 0.592 | 0.530 | -0.062 | [-0.114, -0.009] | -0.065, -0.060, -0.060 |

Seed drift (5I, in-window seed, task-demeaned): blocks (index, mean, SE, n) = 0: -0.000 (SE 0.018, n=400). Range 0.000, SE of difference 0.026, drift flag (>2 SE): False.

Seed-check minus seed (empirical null of window noise, 9D(ii)): +0.010, 95% CI [-0.043, 0.063], p 0.697.

**LC-ACE: each CapEvolve arm vs ACE (Holm m = 3; secondary, own family)** (Holm m = 3; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| hcstock vs ace | +0.102 | [0.035, 0.169] | [-0.038, 0.242] | 0.005 | 0.015 | - | superior | +0.102 (0.015) | a 0/3, b 0/3 | +0.11, +0.10, +0.09 |
| hc3 vs ace | +0.022 | [-0.045, 0.088] | [-0.130, 0.174] | 0.504 | 1.000 | - | n.s. | +0.022 (1.000) | a 0/3, b 0/3 | +0.05, +0.00, +0.01 |
| ao22 vs ace | +0.012 | [-0.047, 0.071] | [-0.173, 0.197] | 0.683 | 1.000 | - | n.s. | +0.012 (1.000) | a 0/3, b 0/3 | +0.08, -0.02, -0.02 |

**LC-HL: each CapEvolve arm vs hl-v0 (Holm m = 3; secondary; ARTIFACT-LEVEL ONLY: hl-v0 is one artifact standing for the 3 HarnessLens seeds)** (Holm m = 3; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| hcstock vs hl-v0 | +0.125 | [0.049, 0.201] | n/a | 0.003 | 0.008 | - | superior | +0.125 (0.008) | a 0/3, b 0/1 | +0.14, +0.12, +0.11 |
| hc3 vs hl-v0 | +0.045 | [-0.039, 0.129] | n/a | 0.276 | 0.535 | - | n.s. | +0.045 (0.535) | a 0/3, b 0/1 | +0.07, +0.02, +0.03 |
| ao22 vs hl-v0 | +0.035 | [-0.029, 0.099] | n/a | 0.267 | 0.535 | - | n.s. | +0.035 (0.535) | a 0/3, b 0/1 | +0.10, +0.00, +0.01 |

**Descriptive rows in this window (no Holm claim): late competitors and CapEvolve arms vs the in-window seed** (Holm m = 5; delta = arm minus comparator; artifact-level CR1 t(C-1) with Holm, pipeline-level t(S-1) beside it; sens = infra_final treated as missing, raw p / Holm)

| row | delta | 95% CI (artifact) | 95% CI (pipeline) | p | Holm p | full-family Holm p | verdict | sens delta (Holm) | inert a/b | per-seed delta |
|---|---|---|---|---|---|---|---|---|---|---|
| ace vs seed | +0.033 | [-0.047, 0.113] | [-0.162, 0.229] | 0.395 | 0.887 | - | n.s. | +0.033 (0.887) | a 0/3, b 0/1 | +0.05, -0.01, +0.06 |
| hl-v0 vs seed | +0.010 | [-0.063, 0.083] | n/a | 0.778 | 0.887 | - | n.s. | +0.010 (0.887) | a 0/1, b 0/1 | +0.01 |
| hcstock vs seed | +0.135 | [0.043, 0.227] | [-0.055, 0.325] | 0.006 | 0.031 | - | superior | +0.135 (0.031) | a 0/3, b 0/1 | +0.15, +0.14, +0.12 |
| hc3 vs seed | +0.055 | [-0.050, 0.160] | [-0.171, 0.281] | 0.287 | 0.887 | - | n.s. | +0.055 (0.887) | a 0/3, b 0/1 | +0.09, +0.04, +0.05 |
| ao22 vs seed | +0.045 | [-0.030, 0.120] | [-0.163, 0.253] | 0.222 | 0.887 | - | n.s. | +0.045 (0.887) | a 0/3, b 0/1 | +0.11, +0.01, +0.02 |

Infrastructure and missing cells (per_arm_report.json of THIS window; counts only; key prefix is the scoring mode):

| mode\|arm (mode B = matched-checkpoint artifacts; it is NOT the suite letter) | jobs | done | infra attempts | infra_final | hangs | missing hang | candidate errors | empty output | raw tool text |
|---|---|---|---|---|---|---|---|---|---|
| B|hl-v0 | 400 | 400 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| TOTAL | 3400 | 3400 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
(rows with all-zero infra, missing and candidate-error counts omitted)

Target latency and tokens per final rollout (wall seconds from results_trials t_start to t_end of the final attempt; tokens = raw `tokens` field per logged attempt, semantics as recorded by the runner, not re-derived):

| arm | trials | mean wall s | median wall s | mean tokens/attempt | mean LLM calls/attempt |
|---|---|---|---|---|---|
| ace | 600 | 93 | 77 | 367231 | 12.4 |
| ao22 | 600 | 75 | 58 | 130412 | 12.9 |
| hc3 | 600 | 71 | 56 | 115558 | 12.4 |
| hcstock | 600 | 64 | 53 | 161461 | 10.8 |
| hl-v0 | 400 | 126 | 102 | n/a | 15.2 |
| seed | 400 | 58 | 44 | 61742 | 11.1 |
| seed-check | 200 | 60 | 45 | 72328 | 11.9 |

