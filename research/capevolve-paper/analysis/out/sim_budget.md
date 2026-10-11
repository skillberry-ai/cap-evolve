# sim_budget: rule P operating points, 600 rollouts/search, val-40, screen n=1 (~22400 searches/cell)

## 6 candidates per search

| option | P(>=1 false promotion), all-null search | P(>=1 false promotion), mixed search | mean promotions | E true gain new tasks | E true gain val tasks | E rollouts used |
|---|---|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.013 | 0.009 | 0.03 | +0.0007 | +0.0012 | 385 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.026 | 0.019 | 0.05 | +0.0011 | +0.0018 | 385 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.050 | 0.035 | 0.09 | +0.0015 | +0.0026 | 384 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.018 | 0.014 | 0.05 | +0.0010 | +0.0016 | 394 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.067 | 0.045 | 0.11 | +0.0017 | +0.0029 | 385 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.079 | 0.054 | 0.13 | +0.0021 | +0.0036 | 385 |
| i: P n_conf=3 z=0.842 dmin=0 | 0.104 | 0.065 | 0.15 | +0.0025 | +0.0041 | 386 |
| j: P n_conf=4 z=1.282 dmin=0 | 0.046 | 0.030 | 0.09 | +0.0016 | +0.0028 | 408 |
| f: one-stage k=1 | 0.434 | 0.291 | 0.51 | +0.0043 | +0.0072 | 280 |
| g: one-stage k=1.645 | 0.199 | 0.123 | 0.22 | +0.0022 | +0.0037 | 280 |

## 12 candidates per search

| option | P(>=1 false promotion), all-null search | P(>=1 false promotion), mixed search | mean promotions | E true gain new tasks | E true gain val tasks | E rollouts used |
|---|---|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.014 | 0.009 | 0.03 | +0.0007 | +0.0012 | 529 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.030 | 0.020 | 0.06 | +0.0011 | +0.0018 | 529 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.055 | 0.038 | 0.10 | +0.0019 | +0.0031 | 530 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.019 | 0.013 | 0.04 | +0.0010 | +0.0016 | 507 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.078 | 0.053 | 0.13 | +0.0021 | +0.0036 | 551 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.091 | 0.059 | 0.14 | +0.0024 | +0.0040 | 530 |
| i: P n_conf=3 z=0.842 dmin=0 | 0.110 | 0.074 | 0.17 | +0.0027 | +0.0045 | 531 |
| j: P n_conf=4 z=1.282 dmin=0 | 0.046 | 0.031 | 0.08 | +0.0016 | +0.0027 | 522 |
| f: one-stage k=1 | 0.565 | 0.372 | 0.67 | +0.0058 | +0.0100 | 520 |
| g: one-stage k=1.645 | 0.297 | 0.181 | 0.33 | +0.0035 | +0.0058 | 520 |

## Power (single candidate, diffuse true edit)

| option | +0.04 | +0.06 | +0.08 | +0.10 |
|---|---|---|---|---|
| a: P n_conf=3 z=2.0 dmin=.02 | 0.03 | 0.08 | 0.15 | 0.26 |
| b: P n_conf=3 z=1.645 dmin=0 | 0.06 | 0.12 | 0.21 | 0.33 |
| c: P n_conf=3 z=1.282 dmin=0 | 0.09 | 0.17 | 0.27 | 0.41 |
| d: P n_conf=5 z=1.645 dmin=0 | 0.08 | 0.16 | 0.29 | 0.42 |
| e: P n_conf=2 z=1.282 dmin=0 (fresh only) | 0.08 | 0.14 | 0.23 | 0.33 |
| h: P n_conf=3 z=1.0 dmin=0 | 0.12 | 0.21 | 0.32 | 0.44 |
| i: P n_conf=3 z=0.842 dmin=0 | 0.14 | 0.23 | 0.34 | 0.46 |
| j: P n_conf=4 z=1.282 dmin=0 | 0.10 | 0.19 | 0.31 | 0.44 |
| f: one-stage k=1 | 0.29 | 0.37 | 0.45 | 0.54 |
| g: one-stage k=1.645 | 0.12 | 0.17 | 0.23 | 0.29 |