# v1 versus v2 (descriptive; user-directed early unblinding)

Each delta is measured inside its own window against that window's own in-window seed (n = 10 trials per task on D and E). Windows are different time blocks and are never pooled. Rows are DESCRIPTIVE unless marked; the registered v2 confirmatory rows are family V2 (11G) in the v2 window files. Inert artifacts (champion = seed) enter at the seed score, delta 0.

## Suite A (SpreadsheetBench, T = 70, seed n = 2)

v2 A started from the v1 seed + empty helper scaffold + 3 prompt lines (erratum 40); every helper script is CapEvolve-written. The A v2.1-AO2 runs have no scored cell.

| arm (window) | delta vs in-window seed | 95% CI (artifact, CR1) | 95% CI (pipeline, t2) | inert seeds | per-seed delta (seed 0, 1, 2) |
|---|---|---|---|---|---|
| v1 hc (rule P hill-climb) (A) | +0.029 | [-0.025, 0.082] | [-0.107, 0.164] | 1/3 | +0.029, +0.057, +0.000 |
| v1 hcstock (stock-gate hill-climb) (A) | +0.105 | [0.025, 0.185] | [-0.099, 0.309] | 0/3 | +0.057, +0.143, +0.114 |
| v1 ao (agent-optimize, inert) (A) | +0.000 | [0.000, 0.000] | [0.000, 0.000] | 3/3 | +0.000, +0.000, +0.000 |
| v2.0 HC-2 (V2/A) | +0.140 | [0.045, 0.236] | [-0.093, 0.374] | 0/3 | +0.093, +0.179, +0.150 |
| v2.0 AO-2 (= v2 start: scaffold effect; not inert) (V2/A) | +0.007 | [-0.045, 0.059] | [-0.111, 0.125] | 0/3 | +0.021, +0.007, -0.007 |

Window-shift controls (same GEPA artifact scored in both windows when the tree hashes match): GEPA delta vs seed v1 window +0.138 [0.064, 0.212], v2 window +0.140 [0.048, 0.233]. Seed mean v1 0.357 vs v2 0.364; GEPA mean v1 0.495 vs v2 0.505.
GEPA artifact tree hashes identical across windows: True.

Difference of deltas (v2 arm minus v1 arm, each against its own window's seed; task-paired CR1 on the per-task difference of seed-averaged deltas; descriptive):

| v2 arm | v1 arm | v2 minus v1 | 95% CI |
|---|---|---|---|
| v2.0 HC-2 | v1 hc (rule P hill-climb) | +0.112 | [0.024, 0.200] |
| v2.0 HC-2 | v1 hcstock (stock-gate hill-climb) | +0.036 | [-0.060, 0.132] |
| v2.0 HC-2 | v1 ao (agent-optimize, inert) | +0.140 | [0.045, 0.236] |
| v2.0 AO-2 (= v2 start: scaffold effect; not inert) | v1 hc (rule P hill-climb) | -0.021 | [-0.089, 0.046] |
| v2.0 AO-2 (= v2 start: scaffold effect; not inert) | v1 hcstock (stock-gate hill-climb) | -0.098 | [-0.188, -0.007] |
| v2.0 AO-2 (= v2 start: scaffold effect; not inert) | v1 ao (agent-optimize, inert) | +0.007 | [-0.045, 0.059] |

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

