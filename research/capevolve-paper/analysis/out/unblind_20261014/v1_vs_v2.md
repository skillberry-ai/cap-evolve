# v1 versus v2 (descriptive; user-directed early unblinding)

Each delta is measured inside its own window against that window's own in-window seed (n = 10 trials per task on D and E). Windows are different time blocks and are never pooled. Rows are DESCRIPTIVE unless marked; the registered v2 confirmatory rows are family V2 (11G) in the v2 window files. Inert artifacts (champion = seed) enter at the seed score, delta 0.

## Suite D (tau2 retail, test 40)

| arm (window) | delta vs in-window seed | 95% CI (artifact, CR1) | 95% CI (pipeline, t2) | inert seeds | per-seed delta (seed 0, 1, 2) |
|---|---|---|---|---|---|
| v1 pt (stock-gate hill-climb, reference) (D) | +0.115 | [0.028, 0.202] | [-0.082, 0.312] | 0/3 | +0.095, +0.145, +0.105 |
| v1 rulep (rule P hill-climb) (D) | +0.118 | [0.057, 0.180] | [-0.043, 0.279] | 0/3 | +0.135, +0.075, +0.145 |
| v2.0 HC-2 (V2/D) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |
| v2.0 AO-2 (V2/D) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |
| v2.1 AO-2 (inert by construction) (V2/D) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |

Window-shift controls (same GEPA artifact scored in both windows when the tree hashes match): GEPA delta vs seed v1 window +0.058 [-0.000, 0.117], v2 window +0.040 [-0.026, 0.106]. Seed mean v1 0.650 vs v2 0.630; GEPA mean v1 0.708 vs v2 0.670.
GEPA artifact tree hashes identical across windows: True.

Difference of deltas (v2 arm minus v1 arm, each against its own window's seed; task-paired CR1 on the per-task difference of seed-averaged deltas; descriptive):

| v2 arm | v1 arm | v2 minus v1 | 95% CI |
|---|---|---|---|
| v2.0 HC-2 | v1 pt (stock-gate hill-climb, reference) | -0.115 | [-0.202, -0.028] |
| v2.0 HC-2 | v1 rulep (rule P hill-climb) | -0.118 | [-0.180, -0.057] |
| v2.0 AO-2 | v1 pt (stock-gate hill-climb, reference) | -0.115 | [-0.202, -0.028] |
| v2.0 AO-2 | v1 rulep (rule P hill-climb) | -0.118 | [-0.180, -0.057] |
| v2.1 AO-2 (inert by construction) | v1 pt (stock-gate hill-climb, reference) | -0.115 | [-0.202, -0.028] |
| v2.1 AO-2 (inert by construction) | v1 rulep (rule P hill-climb) | -0.118 | [-0.180, -0.057] |

## Suite E (tau2 airline, test 20)

| arm (window) | delta vs in-window seed | 95% CI (artifact, CR1) | 95% CI (pipeline, t2) | inert seeds | per-seed delta (seed 0, 1, 2) |
|---|---|---|---|---|---|
| v1 pt (stock-gate hill-climb, reference) (E) | +0.130 | [0.044, 0.216] | [-0.219, 0.479] | 1/3 | +0.150, +0.240, +0.000 |
| v1 rulep (rule P hill-climb) (E) | +0.247 | [0.102, 0.391] | [-0.073, 0.566] | 0/3 | +0.210, +0.300, +0.230 |
| v1 ao (agent-optimize, dagger) (E) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |
| v2.0 HC-2 (V2/E) | +0.100 | [0.023, 0.177] | [-0.189, 0.389] | 1/3 | +0.000, +0.105, +0.195 |
| v2.0 AO-2 (V2/E) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |
| v2.1 AO-2 (inert by construction) (V2/E) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |

Window-shift controls (same GEPA artifact scored in both windows when the tree hashes match): GEPA delta vs seed v1 window +0.127 [-0.028, 0.281], v2 window +0.155 [0.048, 0.262]. Seed mean v1 0.480 vs v2 0.425; GEPA mean v1 0.607 vs v2 0.580.
GEPA artifact tree hashes identical across windows: True.

Difference of deltas (v2 arm minus v1 arm, each against its own window's seed; task-paired CR1 on the per-task difference of seed-averaged deltas; descriptive):

| v2 arm | v1 arm | v2 minus v1 | 95% CI |
|---|---|---|---|
| v2.0 HC-2 | v1 pt (stock-gate hill-climb, reference) | -0.030 | [-0.120, 0.060] |
| v2.0 HC-2 | v1 rulep (rule P hill-climb) | -0.147 | [-0.271, -0.023] |
| v2.0 HC-2 | v1 ao (agent-optimize, dagger) | +0.100 | [0.023, 0.177] |
| v2.0 AO-2 | v1 pt (stock-gate hill-climb, reference) | -0.130 | [-0.216, -0.044] |
| v2.0 AO-2 | v1 rulep (rule P hill-climb) | -0.247 | [-0.391, -0.102] |
| v2.0 AO-2 | v1 ao (agent-optimize, dagger) | +0.000 | [-0.000, 0.000] |
| v2.1 AO-2 (inert by construction) | v1 pt (stock-gate hill-climb, reference) | -0.130 | [-0.216, -0.044] |
| v2.1 AO-2 (inert by construction) | v1 rulep (rule P hill-climb) | -0.247 | [-0.391, -0.102] |
| v2.1 AO-2 (inert by construction) | v1 ao (agent-optimize, dagger) | +0.000 | [-0.000, 0.000] |

