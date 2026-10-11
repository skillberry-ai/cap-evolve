# sim_budget_A: Suite A observed difficulty: 600 rollouts/search, screen set of 40 tasks, screen n=1, task-difficulty Beta(mu=0.567, kappa=0.51) (~22400 searches/cell)

## 10 candidates per search

| option | P(>=1 false promotion), all-null search | P(>=1 false promotion), mixed search | mean promotions | E true gain new tasks | E true gain val tasks | E rollouts used | E candidates screened |
|---|---|---|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.015 | 0.010 | 0.03 | +0.0005 | +0.0010 | 498 | 7.4 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.033 | 0.021 | 0.06 | +0.0008 | +0.0017 | 499 | 7.5 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.068 | 0.039 | 0.11 | +0.0014 | +0.0027 | 500 | 7.6 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.021 | 0.014 | 0.05 | +0.0007 | +0.0014 | 477 | 6.4 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.089 | 0.053 | 0.13 | +0.0016 | +0.0032 | 522 | 8.5 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.103 | 0.059 | 0.15 | +0.0017 | +0.0035 | 500 | 7.6 |
| f: one-stage k=1 | 0.578 | 0.383 | 0.69 | +0.0034 | +0.0074 | 440 | 10.0 |
| g: one-stage k=1.645 | 0.304 | 0.189 | 0.35 | +0.0023 | +0.0049 | 440 | 10.0 |

## Power (single candidate, diffuse true edit)

| option | +0.04 | +0.06 | +0.08 | +0.10 |
|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.06 | 0.13 | 0.26 | 0.40 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.09 | 0.19 | 0.33 | 0.49 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.14 | 0.26 | 0.40 | 0.55 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.13 | 0.27 | 0.43 | 0.59 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.12 | 0.21 | 0.33 | 0.48 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.18 | 0.31 | 0.45 | 0.58 |
| f: one-stage k=1 | 0.34 | 0.44 | 0.53 | 0.64 |
| g: one-stage k=1.645 | 0.17 | 0.25 | 0.32 | 0.41 |