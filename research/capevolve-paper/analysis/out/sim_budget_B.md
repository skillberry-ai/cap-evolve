# sim_budget_B: Suite B observed difficulty: 550 rollouts/search, screen set of 49 tasks, screen n=1, task-difficulty Beta(mu=0.597, kappa=1.53) (~22400 searches/cell)

## 10 candidates per search

| option | P(>=1 false promotion), all-null search | P(>=1 false promotion), mixed search | mean promotions | E true gain new tasks | E true gain val tasks | E rollouts used | E candidates screened |
|---|---|---|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.010 | 0.005 | 0.02 | +0.0004 | +0.0007 | 505 | 6.7 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.018 | 0.012 | 0.04 | +0.0008 | +0.0012 | 506 | 6.8 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.040 | 0.022 | 0.06 | +0.0011 | +0.0017 | 506 | 6.7 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.000 | 0.000 | 0.00 | +0.0000 | +0.0000 | 367 | 5.9 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.050 | 0.029 | 0.08 | +0.0012 | +0.0020 | 517 | 7.3 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.060 | 0.035 | 0.09 | +0.0014 | +0.0024 | 507 | 6.8 |
| f: one-stage k=1 | 0.524 | 0.334 | 0.61 | +0.0046 | +0.0078 | 539 | 10.0 |
| g: one-stage k=1.645 | 0.256 | 0.147 | 0.28 | +0.0026 | +0.0044 | 539 | 10.0 |

## Power (single candidate, diffuse true edit)

| option | +0.04 | +0.06 | +0.08 | +0.10 |
|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.04 | 0.10 | 0.20 | 0.34 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.07 | 0.15 | 0.27 | 0.41 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.11 | 0.20 | 0.33 | 0.48 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.00 | 0.00 | 0.00 | 0.00 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.09 | 0.17 | 0.28 | 0.41 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.14 | 0.25 | 0.38 | 0.53 |
| f: one-stage k=1 | 0.30 | 0.40 | 0.49 | 0.59 |
| g: one-stage k=1.645 | 0.13 | 0.18 | 0.26 | 0.34 |