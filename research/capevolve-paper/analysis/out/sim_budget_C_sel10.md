# sim_budget_C_sel10: Suite C_sel10 observed difficulty: 550 rollouts/search, screen set of 10 tasks, screen n=1, task-difficulty Beta(mu=0.506, kappa=0.87) (~22400 searches/cell)

## 10 candidates per search

| option | P(>=1 false promotion), all-null search | P(>=1 false promotion), mixed search | mean promotions | E true gain new tasks | E true gain val tasks | E rollouts used | E candidates screened |
|---|---|---|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.033 | 0.028 | 0.05 | +0.0006 | +0.0023 | 182 | 10.0 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.068 | 0.056 | 0.10 | +0.0012 | +0.0040 | 179 | 10.0 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.125 | 0.098 | 0.18 | +0.0019 | +0.0065 | 174 | 10.0 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.059 | 0.055 | 0.11 | +0.0013 | +0.0048 | 216 | 9.8 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.125 | 0.099 | 0.17 | +0.0017 | +0.0059 | 153 | 10.0 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.184 | 0.141 | 0.26 | +0.0026 | +0.0088 | 172 | 10.0 |
| f: one-stage k=1 | 0.449 | 0.335 | 0.53 | +0.0035 | +0.0103 | 110 | 10.0 |
| g: one-stage k=1.645 | 0.202 | 0.151 | 0.23 | +0.0018 | +0.0056 | 110 | 10.0 |

## Power (single candidate, diffuse true edit)

| option | +0.04 | +0.06 | +0.08 | +0.10 |
|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.01 | 0.02 | 0.04 | 0.05 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.02 | 0.04 | 0.06 | 0.08 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.04 | 0.06 | 0.10 | 0.13 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.03 | 0.05 | 0.08 | 0.12 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.04 | 0.06 | 0.09 | 0.11 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.06 | 0.09 | 0.12 | 0.16 |
| f: one-stage k=1 | 0.18 | 0.21 | 0.26 | 0.29 |
| g: one-stage k=1.645 | 0.07 | 0.09 | 0.11 | 0.15 |