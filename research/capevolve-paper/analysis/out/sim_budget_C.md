# sim_budget_C: Suite C observed difficulty: 550 rollouts/search, screen set of 20 tasks, screen n=1, task-difficulty Beta(mu=0.506, kappa=0.87) (~22400 searches/cell)

## 10 candidates per search

| option | P(>=1 false promotion), all-null search | P(>=1 false promotion), mixed search | mean promotions | E true gain new tasks | E true gain val tasks | E rollouts used | E candidates screened |
|---|---|---|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.034 | 0.026 | 0.06 | +0.0010 | +0.0022 | 342 | 9.3 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.063 | 0.048 | 0.11 | +0.0016 | +0.0036 | 340 | 9.3 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.113 | 0.085 | 0.17 | +0.0024 | +0.0055 | 338 | 9.4 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.046 | 0.038 | 0.09 | +0.0015 | +0.0034 | 356 | 8.5 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.133 | 0.100 | 0.20 | +0.0026 | +0.0058 | 314 | 9.8 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.171 | 0.127 | 0.25 | +0.0033 | +0.0075 | 337 | 9.5 |
| f: one-stage k=1 | 0.550 | 0.388 | 0.66 | +0.0051 | +0.0105 | 220 | 10.0 |
| g: one-stage k=1.645 | 0.302 | 0.216 | 0.35 | +0.0030 | +0.0063 | 220 | 10.0 |

## Power (single candidate, diffuse true edit)

| option | +0.04 | +0.06 | +0.08 | +0.10 |
|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.03 | 0.05 | 0.08 | 0.14 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.04 | 0.07 | 0.12 | 0.19 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.07 | 0.11 | 0.17 | 0.25 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.05 | 0.10 | 0.17 | 0.26 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.06 | 0.10 | 0.15 | 0.21 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.09 | 0.14 | 0.21 | 0.29 |
| f: one-stage k=1 | 0.25 | 0.30 | 0.36 | 0.42 |
| g: one-stage k=1.645 | 0.12 | 0.16 | 0.20 | 0.25 |