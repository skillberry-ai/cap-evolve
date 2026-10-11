# sim_budget_B_sel25: Suite B_sel25 observed difficulty: 550 rollouts/search, screen set of 25 tasks, screen n=1, task-difficulty Beta(mu=0.600, kappa=0.54) (~22400 searches/cell)

## 10 candidates per search

| option | P(>=1 false promotion), all-null search | P(>=1 false promotion), mixed search | mean promotions | E true gain new tasks | E true gain val tasks | E rollouts used | E candidates screened |
|---|---|---|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.022 | 0.013 | 0.04 | +0.0004 | +0.0011 | 379 | 9.0 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.048 | 0.029 | 0.07 | +0.0007 | +0.0021 | 377 | 9.1 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.086 | 0.052 | 0.12 | +0.0009 | +0.0030 | 379 | 9.1 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.029 | 0.018 | 0.05 | +0.0005 | +0.0016 | 371 | 8.3 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.105 | 0.062 | 0.14 | +0.0010 | +0.0031 | 364 | 9.6 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.130 | 0.080 | 0.18 | +0.0013 | +0.0042 | 378 | 9.2 |
| f: one-stage k=1 | 0.494 | 0.332 | 0.56 | +0.0011 | +0.0057 | 275 | 10.0 |
| g: one-stage k=1.645 | 0.300 | 0.191 | 0.32 | +0.0007 | +0.0039 | 275 | 10.0 |

## Power (single candidate, diffuse true edit)

| option | +0.04 | +0.06 | +0.08 | +0.10 |
|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.03 | 0.08 | 0.14 | 0.22 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.06 | 0.11 | 0.20 | 0.30 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.09 | 0.16 | 0.25 | 0.37 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.08 | 0.16 | 0.26 | 0.39 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.07 | 0.13 | 0.21 | 0.30 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.12 | 0.20 | 0.30 | 0.41 |
| f: one-stage k=1 | 0.27 | 0.34 | 0.42 | 0.51 |
| g: one-stage k=1.645 | 0.14 | 0.20 | 0.26 | 0.33 |