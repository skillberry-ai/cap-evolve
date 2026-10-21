# ABL-W1: 12 ablation champions on the held-out test-20 (exploratory; designed after the V3 B1 results were seen)

Task set: 20 tasks, 20 families; k = 10 trials per task per champion; seed n = 20; seed-check k = 10; HC-stock-s0-ref = the main-window HC-stock seed-0 champion re-scored in this window. One search seed per arm: no pipeline-level interval, no claim about a component's general importance; raw p only, no family claim, no Holm decision (addendum 6).

Infrastructure (per_arm_report.json): {'jobs': 3200, 'done': 3200, 'infra_attempts': 0, 'infra_final': 0, 'hangs': 0, 'candidate_errors': 0, 'missing_hang': 0, 'empty_output': 0, 'raw_tool_text_last': 0}

## Window checks

- seed 0.485 (n = 20), seed-check 0.475 (k = 10); seed-check minus seed -0.010 [-0.065, 0.045], p 0.708
- drift (5I, in-window seed, task-demeaned, hour blocks): 0: -0.007 (SE 0.023, n=180); 1: +0.038 (SE 0.026, n=149); 2: -0.062 (SE 0.037, n=71). Range 0.100, SE of difference 0.041, flag (>2 SE): True.
- The drift FLAGS: the BLOCK-ADJUSTED deltas (the seed's block effects subtracted from every trial) are the headline columns below; the unadjusted ones are shown beside them.
- HC-stock-s0-ref: mean 0.615; delta over the in-window seed +0.130 [0.022, 0.238], p 0.0206; block-adjusted +0.128 [0.019, 0.237], p 0.0242 (main window: +0.131 over a seed of 0.498; the same artifact, a different time block)

## Per arm

| arm | mean | delta over seed | 95% CI | raw p | block-adjusted delta [CI] p | difference to HC-stock-s0-ref | 95% CI | raw p |
|---|---|---|---|---|---|---|---|---|
| ABL-CAP-P | 0.640 | +0.155 | [0.043, 0.267] | 0.009 | +0.153 [0.043, 0.263] p 0.009 | +0.025 | [-0.053, 0.102] | 0.516 |
| ABL-CAP-TC | 0.595 | +0.110 | [-0.017, 0.237] | 0.085 | +0.111 [-0.017, 0.238] p 0.086 | -0.017 | [-0.079, 0.044] | 0.560 |
| ABL-CAP-TD | 0.505 | +0.020 | [-0.099, 0.139] | 0.730 | +0.021 [-0.098, 0.141] p 0.715 | -0.107 | [-0.219, 0.005] | 0.061 |
| ABL-GATE-DISJOINT | 0.615 | +0.130 | [-0.015, 0.275] | 0.076 | +0.128 [-0.018, 0.274] p 0.082 | -0.000 | [-0.094, 0.094] | 0.997 |
| ABL-GATE-K0.5 | 0.570 | +0.085 | [-0.045, 0.215] | 0.186 | +0.080 [-0.050, 0.209] p 0.213 | -0.048 | [-0.184, 0.088] | 0.465 |
| ABL-GATE-K2 | 0.630 | +0.145 | [0.005, 0.285] | 0.043 | +0.141 [-0.001, 0.282] p 0.051 | +0.013 | [-0.068, 0.094] | 0.748 |
| ABL-GATE-NONE | 0.640 | +0.155 | [0.010, 0.300] | 0.037 | +0.155 [0.011, 0.300] p 0.037 | +0.027 | [-0.065, 0.120] | 0.545 |
| ABL-HIST-NONE | 0.630 | +0.145 | [0.031, 0.259] | 0.015 | +0.141 [0.028, 0.255] p 0.018 | +0.013 | [-0.066, 0.093] | 0.735 |
| ABL-HIST-STATE | 0.565 | +0.080 | [-0.012, 0.172] | 0.085 | +0.074 [-0.020, 0.167] p 0.115 | -0.054 | [-0.168, 0.059] | 0.329 |
| ABL-INFO-EVAL | 0.540 | +0.055 | [-0.010, 0.120] | 0.092 | +0.052 [-0.011, 0.115] p 0.101 | -0.076 | [-0.145, -0.007] | 0.032 |
| ABL-INFO-FAIL | 0.575 | +0.090 | [-0.019, 0.199] | 0.101 | +0.086 [-0.026, 0.198] p 0.124 | -0.042 | [-0.158, 0.075] | 0.463 |
| ABL-INFO-REWARD | 0.580 | +0.095 | [-0.008, 0.198] | 0.069 | +0.093 [-0.011, 0.197] p 0.076 | -0.035 | [-0.080, 0.010] | 0.121 |

The 'difference to HC-stock-s0-ref' column uses the block-adjusted scores (drift flagged).

Count of arms with a positive delta over the seed: 12 of 12; with the CI excluding 0 upward: 4; arms whose delta exceeds HC-stock-s0-ref's: 4; with the difference CI excluding 0: 1.
