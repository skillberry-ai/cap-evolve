# sim_promotion: one-stage gate vs two-stage promote-with-fresh-confirmation (rule P)

reps ~3360/cell, n=5 trials, mu=0.55 kappa=1.5, 10 iterations. Screen = paired gate k_se=1.

## False promotion of null edits

| setting | P(>=1 false promote in 10) | mean false promotes | extra confirm cost per iteration (units of one screening eval) |
|---|---|---|---|
| T=40 one-stage k=1 | 0.570 | 0.61 | 0.00 |
| T=40 P(z=1.645,dmin=0.02,n_conf=5) | 0.089 | 0.09 | 0.31 |
| T=40 P(z=1.645,dmin=0.02,n_conf=10) | 0.077 | 0.08 | 0.58 |
| T=40 P(z=2.0,dmin=0.02,n_conf=10) | 0.037 | 0.04 | 0.63 |
| T=40 P(z=1.645,dmin=0,n_conf=10) | 0.077 | 0.08 | 0.57 |
| T=100 one-stage k=1 | 0.530 | 0.57 | 0.00 |
| T=100 P(z=1.645,dmin=0.02,n_conf=5) | 0.072 | 0.07 | 0.30 |
| T=100 P(z=1.645,dmin=0.02,n_conf=10) | 0.073 | 0.07 | 0.56 |
| T=100 P(z=2.0,dmin=0.02,n_conf=10) | 0.035 | 0.03 | 0.62 |
| T=100 P(z=1.645,dmin=0,n_conf=10) | 0.070 | 0.07 | 0.60 |

## Power (T=40, n=5)

| scenario | d=0.02 | d=0.04 | d=0.06 | d=0.08 | d=0.1 |
|---|---|---|---|---|---|
| diffuse one-stage k=1 | 0.31 | 0.50 | 0.69 | 0.85 | 0.92 |
| diffuse P(z=1.645,dmin=0.02,n_conf=5) | 0.04 | 0.14 | 0.30 | 0.54 | 0.73 |
| diffuse P(z=1.645,dmin=0.02,n_conf=10) | 0.05 | 0.20 | 0.50 | 0.73 | 0.90 |
| diffuse P(z=2.0,dmin=0.02,n_conf=10) | 0.03 | 0.15 | 0.38 | 0.68 | 0.87 |
| diffuse P(z=1.645,dmin=0,n_conf=10) | 0.06 | 0.20 | 0.49 | 0.74 | 0.89 |
| sparse25 one-stage k=1 | 0.30 | 0.49 | 0.69 | 0.80 | 0.90 |
| sparse25 P(z=1.645,dmin=0.02,n_conf=5) | 0.05 | 0.12 | 0.25 | 0.45 | 0.63 |
| sparse25 P(z=1.645,dmin=0.02,n_conf=10) | 0.06 | 0.18 | 0.39 | 0.61 | 0.80 |
| sparse25 P(z=2.0,dmin=0.02,n_conf=10) | 0.03 | 0.12 | 0.28 | 0.48 | 0.69 |
| sparse25 P(z=1.645,dmin=0,n_conf=10) | 0.05 | 0.19 | 0.39 | 0.63 | 0.78 |

## Mixed search (60% null / 25% +1..6pt / 15% -1..6pt population-mean edits, idiosyncratic per-task effects)

| rule | mean promotes | reported gain (champion - seed measured) | true gain, val tasks | true gain, new tasks |
|---|---|---|---|---|
| one-stage k=1 | 0.89 | +0.0547 | +0.0239 | +0.0144 |
| P(z=1.645,dmin=0.02,n_conf=5) | 0.23 | +0.0179 | +0.0093 | +0.0059 |
| P(z=1.645,dmin=0.02,n_conf=10) | 0.30 | +0.0210 | +0.0130 | +0.0076 |
| P(z=2.0,dmin=0.02,n_conf=10) | 0.21 | +0.0164 | +0.0097 | +0.0058 |
| P(z=1.645,dmin=0,n_conf=10) | 0.33 | +0.0225 | +0.0140 | +0.0084 |