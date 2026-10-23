# MERGED window (addenda 12, 13, 14, 15; exploratory except where a family is stated)

Task set: 20 test tasks / 20 families; k = 10 trials per task per champion; seed n = 20; seed-check k = 10. Paper labels: search 1 = GATE-K2 s0, search 2 = s1, search 3 = s3 (seed 2 is a run ID with no paper label). Run IDs are used below.

Infrastructure (per_arm_report.json): {'jobs': 8600, 'done': 8600, 'infra_attempts': 1, 'infra_final': 0, 'hangs': 0, 'candidate_errors': 0, 'missing_hang': 0, 'empty_output': 0}

## Window checks

- seed 0.500 (n = 20), seed-check 0.465 (k = 10); seed-check minus seed -0.035 [-0.096, 0.026], p 0.243
- drift (5I, in-window seed, task-demeaned, hour blocks): 0: -0.009 (SE 0.042, n=65); 1: -0.020 (SE 0.043, n=61); 2: +0.060 (SE 0.049, n=47); 3: -0.062 (SE 0.040, n=72); 4: +0.013 (SE 0.047, n=52); 5: +0.079 (SE 0.042, n=65); 6: -0.063 (SE 0.055, n=38). Range 0.142, SE of difference 0.065, flag (>2 SE): True.
- The drift FLAGS: block-adjusted estimates are printed beside the plain ones; where the two disagree on CI exclusion of 0 for the primary, both are reported and the block-adjusted one is the headline (5I).

## Primary (m = 1): GATE-K2 seeds 0, 1, 3 (paper searches 1 to 3) minus the in-window seed

| estimate | seeds | delta | 95% CI (artifact, CR1 t19) | raw p | 95% CI (pipeline, t S-1) | per-seed delta | block-adjusted delta [CI] |
|---|---|---|---|---|---|---|---|
| PRIMARY | 0,1,3 | +0.133 | [0.041, 0.226] | 0.007 | [-0.059, 0.325] | +0.13, +0.14, +0.12 | +0.129 [0.038, 0.219] |
| four seeds (0,1,2,3) | 0,1,2,3 | +0.116 | [0.029, 0.203] | 0.012 | [-0.028, 0.260] | +0.13, +0.14, +0.07, +0.12 | +0.111 [0.026, 0.197] |
| seeds 0 and 1 only (no cut champion) | 0,1 | +0.138 | [0.039, 0.236] | 0.009 | [-0.471, 0.746] | +0.13, +0.14 | +0.133 [0.036, 0.231] |
| fresh seeds 1,2,3 (with seed 2) | 1,2,3 | +0.112 | [0.024, 0.200] | 0.016 | [-0.097, 0.320] | +0.14, +0.07, +0.12 | +0.107 [0.021, 0.193] |
| fresh seeds 1,3 (without seed 2) | 1,3 | +0.135 | [0.036, 0.234] | 0.010 | [-0.479, 0.749] | +0.14, +0.12 | +0.130 [0.034, 0.227] |

**FLAGS (sensitivity disagrees with the primary on CI exclusion of 0): none**

Per-seed K2 means (plain): s0 0.630, s1 0.645, s2 0.565, s3 0.625

## Secondary (own Holm, m = 11): GATE-K2 (seeds 0, 1, 3) minus each comparator, paired by task

| comparator | delta | 95% CI (artifact) | raw p | Holm p | 95% CI (pipeline; 3-seed comparators only) | verdict | block-adjusted delta [CI] p |
|---|---|---|---|---|---|---|---|
| evoskill | +0.077 | [0.003, 0.150] | 0.042 | 0.208 | [-0.077, 0.230] | inconclusive | +0.074 [0.001, 0.148] p 0.048 |
| gepa | +0.088 | [0.026, 0.150] | 0.008 | 0.068 | [-0.041, 0.218] | inconclusive | +0.086 [0.024, 0.148] p 0.009 |
| gepafull | +0.077 | [0.006, 0.148] | 0.035 | 0.208 | [-0.071, 0.225] | inconclusive | +0.075 [0.003, 0.147] p 0.042 |
| metaharness | +0.103 | [0.038, 0.169] | 0.004 | 0.041 | [-0.034, 0.241] | K2 higher | +0.102 [0.035, 0.168] p 0.005 |
| mipro | +0.127 | [0.038, 0.216] | 0.008 | 0.068 | [-0.058, 0.311] | inconclusive | +0.127 [0.040, 0.214] p 0.007 |
| skillopt | +0.062 | [-0.001, 0.124] | 0.053 | 0.208 | [-0.070, 0.193] | inconclusive | +0.061 [-0.003, 0.124] p 0.059 |
| trace2skill | +0.080 | [-0.004, 0.164] | 0.061 | 0.208 | [-0.095, 0.255] | inconclusive | +0.078 [-0.009, 0.164] p 0.075 |
| wikiskill | +0.113 | [0.028, 0.199] | 0.012 | 0.083 | [-0.064, 0.290] | inconclusive | +0.112 [0.027, 0.197] p 0.013 |
| ace | +0.095 | [0.008, 0.182] | 0.035 | 0.208 | [-0.087, 0.277] | inconclusive | +0.093 [0.005, 0.181] p 0.040 |
| hl-v0 | +0.128 | [0.047, 0.210] | 0.004 | 0.041 | n/a (one artifact or single seed) | K2 higher | +0.129 [0.046, 0.211] p 0.004 |
| NC-LOOP | +0.013 | [-0.049, 0.076] | 0.659 | 0.659 | n/a (one artifact or single seed) | inconclusive | +0.009 [-0.056, 0.073] p 0.785 |

Each comparator with three seeds is averaged over its seeds; hl-v0 and NC-LOOP are single artifacts (artifact-level only). K2 vs a comparator compares whole methods (templates, code versions, budgets and protocols differ): not an effect of any component.

## Cell means (plain; seeds averaged)

| cell | mean | seeds | per-seed means |
|---|---|---|---|
| seed (n=20) | 0.500 | 1 | 0.500 |
| seed-check | 0.465 | 1 | 0.465 |
| evoskill | 0.557 | 3 | 0.565, 0.555, 0.550 |
| gepa | 0.545 | 3 | 0.505, 0.580, 0.550 |
| gepafull | 0.557 | 3 | 0.575, 0.565, 0.530 |
| metaharness | 0.530 | 3 | 0.555, 0.500, 0.535 |
| mipro | 0.507 | 3 | 0.520, 0.525, 0.475 |
| skillopt | 0.572 | 3 | 0.630, 0.505, 0.580 |
| trace2skill | 0.553 | 3 | 0.550, 0.565, 0.545 |
| wikiskill | 0.520 | 3 | 0.560, 0.510, 0.490 |
| ace | 0.538 | 3 | 0.525, 0.560, 0.530 |
| hl-v0 | 0.505 | 1 | 0.505 |
| NC-LOOP | 0.620 | 1 | 0.620 |
| V2-A1a | 0.545 | 1 | 0.545 |
| V2-A1b | 0.535 | 1 | 0.535 |
| V2-A2a | 0.540 | 1 | 0.540 |
| V2-A2b | 0.535 | 1 | 0.535 |
| V2-A3a | 0.655 | 1 | 0.655 |
| V2-A3b | 0.540 | 1 | 0.540 |

## Ablation arms (exploratory; raw p; no family; one search seed each): seed-0 champion

| arm | mean | delta vs in-window seed [95% CI] raw p | delta vs K2 s0 (same-window) [95% CI] raw p | block-adjusted vs seed | block-adjusted vs K2 s0 |
|---|---|---|---|---|---|
| V2-A1a | 0.545 | +0.045 [-0.070, 0.160] p 0.424 | -0.085 [-0.200, 0.030] p 0.138 | +0.043 [-0.072, 0.159] p 0.443 | -0.082 [-0.197, 0.033] p 0.154 |
| V2-A1b | 0.535 | +0.035 [-0.066, 0.136] p 0.476 | -0.095 [-0.185, -0.005] p 0.040 | +0.031 [-0.070, 0.132] p 0.531 | -0.094 [-0.190, 0.002] p 0.054 |
| V2-A2a | 0.540 | +0.040 [-0.051, 0.131] p 0.367 | -0.090 [-0.192, 0.012] p 0.080 | +0.031 [-0.062, 0.125] p 0.491 | -0.094 [-0.196, 0.009] p 0.072 |
| V2-A2b | 0.535 | +0.035 [-0.078, 0.148] p 0.525 | -0.095 [-0.188, -0.002] p 0.046 | +0.029 [-0.087, 0.145] p 0.610 | -0.096 [-0.195, 0.003] p 0.056 |
| V2-A3a | 0.655 | +0.155 [0.049, 0.261] p 0.006 | +0.025 [-0.057, 0.107] p 0.529 | +0.151 [0.044, 0.257] p 0.008 | +0.026 [-0.056, 0.108] p 0.513 |
| V2-A3b | 0.540 | +0.040 [-0.056, 0.136] p 0.395 | -0.090 [-0.206, 0.026] p 0.119 | +0.036 [-0.060, 0.131] p 0.443 | -0.089 [-0.204, 0.026] p 0.123 |

With ten-ish raw p-values, one or two below 0.05 are expected by chance; planning MDE for a single champion against a single champion is 0.158. A1a and A1b differ from K2 in more than one way (single Claude Code session, no loop or gate). A2a is stricter than K2 on docstrings (surface and lint together).
